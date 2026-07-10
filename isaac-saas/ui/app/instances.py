"""Instance lifecycle service (domain layer).

Orchestrates Kubernetes (via K8sClient), object specs (via resources) and tracking
metadata (via the tracking seam). Returns plain dicts (DTOs) for the web layer to
serialize. The K8sClient is injected, so this is unit-testable with a fake client.
"""
import re
import secrets
import time
import urllib.parse

from . import config, policy, resources, tracking
from .k8s import K8sClient


def _clean(name):
    return re.sub(r"[^a-z0-9-]", "", (name or "").lower())


class InstanceService:
    def __init__(self, client=None, policy_svc=None):
        self.k = client or K8sClient()
        self.policy = policy_svc or policy.PolicyService(client=self.k)

    # ---------- read ----------
    def _gpu_by_node(self):
        nodes = self.k.items(self.k.get("/api/v1/nodes"))
        return {n["metadata"]["name"]: n["metadata"].get("labels", {}).get("nvidia.com/gpu.product", "-")
                for n in nodes}

    def list(self):
        ns = config.NAMESPACE
        sel = urllib.parse.quote(f"group={config.GROUP}")
        deps = self.k.items(self.k.get(f"/apis/apps/v1/namespaces/{ns}/deployments?labelSelector={sel}"))
        pods = self.k.items(self.k.get(f"/api/v1/namespaces/{ns}/pods?labelSelector={sel}"))
        svcs = self.k.items(self.k.get(f"/api/v1/namespaces/{ns}/services?labelSelector={sel}"))
        gpu = self._gpu_by_node()
        claims = self._claim_alloc_map()      # DRA: real per-instance device (bulk)
        devices = self._dra_device_map()
        pod_by_app = {p["metadata"].get("labels", {}).get("app"): p for p in pods}
        svc_by_app = {s["metadata"].get("labels", {}).get("app"): s for s in svcs}
        rows = []
        for d in deps:
            app = d["metadata"]["name"]
            name = app[len(config.PREFIX):] if app.startswith(config.PREFIX) else app
            t = tracking.read(d["metadata"])
            p = pod_by_app.get(app, {})
            node = p.get("spec", {}).get("nodeName", "-")
            cs = p.get("status", {}).get("containerStatuses", [])
            svc = svc_by_app.get(app)
            ip = resources.lb_ip(svc) or "-"
            cs_on = any(x.get("name") == "code-server"
                        for x in d["spec"]["template"]["spec"]["containers"])
            rows.append({
                "name": name, "node": node,
                "gpu": (self._gpu_device_for_pod(p, claims, devices)[1]
                        or gpu.get(node, "-")),
                "phase": p.get("status", {}).get("phase", "-"),
                "ready": bool(cs) and all(c.get("ready") for c in cs),
                "restarts": sum(c.get("restartCount", 0) for c in cs),
                "ip": ip,
                "adv": resources.advertised_ip(d),
                "vscode": resources.code_server_url(ip) if (cs_on and ip != "-") else "",
                "owner": t["owner"], "description": t["description"],
                "created": d["metadata"].get("creationTimestamp", ""),
                "age": resources.age(d["metadata"].get("creationTimestamp", "")),
            })
        rows.sort(key=lambda r: r["name"])
        return rows

    def detail(self, name):
        ns = config.NAMESPACE
        name = _clean(name)
        app = config.PREFIX + name
        d = self.k.get(f"/apis/apps/v1/namespaces/{ns}/deployments/{app}")
        if not self.k.ok(d):
            return {"_error": d.get("_error"), "_msg": d.get("_msg", "not found")}
        s = self.k.get(f"/api/v1/namespaces/{ns}/services/{app}-stream")
        pods = self.k.items(self.k.get(
            f"/api/v1/namespaces/{ns}/pods?labelSelector={urllib.parse.quote('app=' + app)}"))
        p = pods[0] if pods else {}
        t = tracking.read(d["metadata"])
        c = d["spec"]["template"]["spec"]["containers"][0]
        cs = p.get("status", {}).get("containerStatuses", [])
        pod_name = p.get("metadata", {}).get("name", "")
        node = p.get("spec", {}).get("nodeName", "")
        ann = d["metadata"].get("annotations", {}) or {}
        cs_on = any(x.get("name") == "code-server"
                    for x in d["spec"]["template"]["spec"]["containers"])
        stream_ip = resources.lb_ip(s) if self.k.ok(s) else ""
        um = self._gpu_device_for_pod(p)  # (uuid, product) actually allocated
        return {
            "name": name,
            "created": d["metadata"].get("creationTimestamp", ""),
            "age": resources.age(d["metadata"].get("creationTimestamp", "")),
            "owner": t["owner"], "description": t["description"],
            "createdBy": t["createdBy"], "tracking": t["tracking"],
            "image": c.get("image", ""),
            "node": node or "-",
            "gpu": (lambda u_m: u_m[1] or self._gpu_by_node().get(node, "-"))(um),
            "gpuUUID": um[0],
            "phase": p.get("status", {}).get("phase", "-"),
            "ready": bool(cs) and all(x.get("ready") for x in cs),
            "restarts": sum(x.get("restartCount", 0) for x in cs),
            "podName": pod_name, "podIP": p.get("status", {}).get("podIP", ""),
            "streamIP": stream_ip,
            "advertised": resources.advertised_ip(d),
            "ports": [{"name": pt["name"], "port": pt["port"], "protocol": pt["protocol"]}
                      for pt in (s.get("spec", {}).get("ports", []) if self.k.ok(s) else [])],
            "codeServerURL": resources.code_server_url(stream_ip) if cs_on else "",
            "codeServerPassword": ann.get(config.ANN_CODE_PW, "") if cs_on else "",
            "workspaceDir": config.WORKSPACE_DIR if cs_on else "",
            "events": self._events(pod_name),
        }

    @staticmethod
    def _find_uuid(o):  # schema-version tolerant: any "GPU-..." string
        if isinstance(o, str) and o.startswith("GPU-"):
            return o
        if isinstance(o, dict):
            for v in o.values():
                r = InstanceService._find_uuid(v)
                if r:
                    return r
        if isinstance(o, list):
            for v in o:
                r = InstanceService._find_uuid(v)
                if r:
                    return r
        return None

    @staticmethod
    def _find_product(dev):
        """productName attribute from a ResourceSlice device (schema tolerant)."""
        attrs = (dev.get("basic", {}) or {}).get("attributes") or dev.get("attributes") or {}
        for k, v in attrs.items():
            if "productname" in k.lower():
                if isinstance(v, dict):
                    for vv in v.values():
                        if isinstance(vv, str):
                            return vv
                elif isinstance(v, str):
                    return v
        return ""

    def _dra_device_map(self):
        """(pool, device) -> (uuid, product) from ResourceSlices. One API call."""
        out = {}
        sl = self.k.get(f"/apis/{config.DRA_API_VERSION}/resourceslices")
        if not self.k.ok(sl):
            return out
        for sli in self.k.items(sl):
            spec = sli.get("spec", {}) or {}
            pool = (spec.get("pool", {}) or {}).get("name")
            for d in spec.get("devices", []) or []:
                out[(pool, d.get("name"))] = (self._find_uuid(d) or "",
                                              self._find_product(d))
        return out

    def _claim_alloc_map(self):
        """claimName -> (pool, device) from ResourceClaims in our ns. One API call."""
        out = {}
        r = self.k.get(f"/apis/{config.DRA_API_VERSION}/namespaces/"
                       f"{config.NAMESPACE}/resourceclaims")
        if not self.k.ok(r):
            return out
        for c in self.k.items(r):
            res = (((c.get("status", {}) or {}).get("allocation", {}) or {})
                   .get("devices", {}) or {}).get("results", [])
            if res:
                out[c["metadata"]["name"]] = (res[0].get("pool"), res[0].get("device"))
        return out

    @staticmethod
    def _pod_claim_name(pod):
        rcs = (pod.get("status", {}) or {}).get("resourceClaimStatuses") or []
        return next((x.get("resourceClaimName") for x in rcs
                     if x.get("resourceClaimName")), None)

    def _gpu_device_for_pod(self, pod, claims=None, devices=None):
        """(uuid, product) actually allocated to this pod; ("", "") when unknown."""
        try:
            claim = self._pod_claim_name(pod)
            if not claim:
                return "", ""
            claims = claims if claims is not None else self._claim_alloc_map()
            devices = devices if devices is not None else self._dra_device_map()
            key = claims.get(claim)
            if not key:
                return "", ""
            return devices.get(key, ("", ""))
        except Exception:
            return "", ""

    def gpu_of(self, name):
        """(uuid, model, node) currently held by instance `name` - for scenes.py.
        ("", "", "") when the pod/allocation is not visible (fail-soft)."""
        try:
            ns = config.NAMESPACE
            app = config.PREFIX + _clean(name)
            pods = self.k.items(self.k.get(
                f"/api/v1/namespaces/{ns}/pods?labelSelector={urllib.parse.quote('app=' + app)}"))
            p = pods[0] if pods else {}
            uuid, model = self._gpu_device_for_pod(p)
            node = p.get("spec", {}).get("nodeName", "")
            if not model and node:
                model = self._gpu_by_node().get(node, "")
            return uuid, model, node
        except Exception:
            return "", "", ""

    def _events(self, pod_name):
        if not pod_name:
            return []
        ns = config.NAMESPACE
        fs = urllib.parse.quote("involvedObject.name=" + pod_name)
        ev = self.k.items(self.k.get(f"/api/v1/namespaces/{ns}/events?fieldSelector={fs}"))
        return [{"type": e.get("type", ""), "reason": e.get("reason", ""),
                 "message": e.get("message", ""),
                 "time": e.get("lastTimestamp") or e.get("eventTime") or ""}
                for e in ev[-8:]]

    # ---------- write ----------
    def reconcile(self, rows):
        """Ensure each instance advertises its current LoadBalancer IP."""
        ns = config.NAMESPACE
        for r in rows:
            if r["ip"] not in ("-", "") and r["adv"] != r["ip"]:
                patch = [{"op": "replace", "path": "/spec/template/spec/containers/0/args",
                          "value": [config.STREAM_CMD, config.PUBLIC_ADDR_FLAG + r["ip"]]}]
                self.k.patch(f"/apis/apps/v1/namespaces/{ns}/deployments/{config.PREFIX}{r['name']}", patch)

    def create(self, name, owner="", desc="", image=None):
        ns = config.NAMESPACE
        name = _clean(name)[:30].strip("-")
        if not name:
            return False, "invalid name (use a-z, 0-9, -)"
        if self.k.ok(self.k.get(f"/apis/apps/v1/namespaces/{ns}/deployments/{config.PREFIX}{name}")):
            return False, f"instance '{name}' already exists"
        # GPU ban policy: restrict this instance's nodeAffinity to non-banned nodes.
        # node/product bans -> dropped from nodeAffinity here; per-UUID bans -> enforced
        # by the DRA claim's CEL (below).
        bans, bans_ok = self.policy.list()
        sched_nodes = policy.eligible_nodes(self.k, bans) if bans_ok else config.NODES
        if not sched_nodes:
            return False, "no schedulable nodes: all instance nodes are banned"
        # DRA: per-instance ResourceClaimTemplate excluding banned GPU UUIDs AND
        # config-denied product families (real per-device enforcement - mixed nodes
        # keep compatible GPUs). Created before the Deployment so the pod resolves it.
        if config.DRA_ENABLED:
            uuids = policy.banned_gpu_uuids(bans) if bans_ok else []
            rct = f"/apis/{config.DRA_API_VERSION}/namespaces/{ns}/resourceclaimtemplates"
            r = self.k.post(rct, resources.resource_claim_template(
                name, uuids, config.INSTANCE_DENY_PRODUCTS))
            if not self.k.ok(r) and r.get("_error") != 409:  # 409 -> already exists
                return False, f"gpu claim template failed: {str(r.get('_msg', ''))[:200]}"
        # bundled VSCode: per-instance password + (optional) persistent workspace PVC
        code_pw = secrets.token_urlsafe(9) if config.CODE_SERVER_ENABLED else ""
        if config.CODE_SERVER_ENABLED and config.WORKSPACE_PERSIST:
            r = self.k.post(f"/api/v1/namespaces/{ns}/persistentvolumeclaims",
                            resources.workspace_pvc(name))
            if not self.k.ok(r):
                return False, f"workspace PVC failed: {str(r.get('_msg', ''))[:200]}"
        # service first, so the instance can self-discover its LB IP
        r = self.k.post(f"/api/v1/namespaces/{ns}/services", resources.service(name))
        if not self.k.ok(r):
            return False, f"service create failed: {str(r.get('_msg', ''))[:200]}"
        ip = None
        for _ in range(15):
            ip = resources.lb_ip(self.k.get(f"/api/v1/namespaces/{ns}/services/{config.PREFIX}{name}-stream"))
            if ip:
                break
            time.sleep(1)
        r = self.k.post(f"/apis/apps/v1/namespaces/{ns}/deployments",
                        resources.deployment(name, ip, owner, desc, nodes=sched_nodes,
                                             code_pw=code_pw, image=image))
        if not self.k.ok(r):
            return False, f"deploy failed: {str(r.get('_msg', ''))[:200]}"
        extra = (f" (IP {ip})" if ip else " (IP pending)")
        if config.CODE_SERVER_ENABLED:
            extra += " · VSCode bundled (see Details)"
        return True, f"created '{name}'" + extra

    def delete(self, name):
        ns = config.NAMESPACE
        name = _clean(name)
        self.k.delete(f"/apis/apps/v1/namespaces/{ns}/deployments/{config.PREFIX}{name}")
        self.k.delete(f"/api/v1/namespaces/{ns}/services/{config.PREFIX}{name}-stream")
        # workspace PVC (no-op/404 when persistence was off; deletes the user's edits)
        self.k.delete(f"/api/v1/namespaces/{ns}/persistentvolumeclaims/{config.PREFIX}{name}-workspace")
        # DRA claim template (no-op/404 when DRA was off or already gone)
        self.k.delete(f"/apis/{config.DRA_API_VERSION}/namespaces/{ns}/resourceclaimtemplates/{config.PREFIX}{name}-gpu")
        return True, f"deleted '{name}'"

    def prune(self):
        ns = config.NAMESPACE
        svcs = self.k.items(self.k.get(f"/api/v1/namespaces/{ns}/services"))
        deps = {d["metadata"]["name"]
                for d in self.k.items(self.k.get(f"/apis/apps/v1/namespaces/{ns}/deployments"))}
        n = 0
        for s in svcs:
            nm = s["metadata"]["name"]
            if nm.startswith(config.PREFIX) and nm.endswith("-stream") and nm[:-len("-stream")] not in deps:
                self.k.delete(f"/api/v1/namespaces/{ns}/services/{nm}")
                n += 1
        return True, f"pruned {n} orphan service(s)"
