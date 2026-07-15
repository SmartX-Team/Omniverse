"""Cluster GPU view (domain layer).

Reports what GPUs Kubernetes recognizes (device-plugin nodes only), how many are in
use, and how many the user can still launch. Pure Kubernetes API - no Prometheus yet
(that is the planned (b) step for exact per-device utilization).
"""
from . import config, policy
from .k8s import K8sClient


def nvenc_capable(product):
    # A100 has no NVENC hardware encoder -> cannot serve WebRTC streaming.
    return "A100" not in (product or "")


class GpuService:
    def __init__(self, client=None, policy_svc=None):
        self.k = client or K8sClient()
        self.policy = policy_svc or policy.PolicyService(client=self.k)

    def _used_by_node(self):
        """Sum nvidia.com/gpu requests across ALL pods per node.
        Returns (used_map, ok); ok=False when the SA lacks cluster pods:list."""
        r = self.k.get("/api/v1/pods")
        if not self.k.ok(r):
            return {}, False
        used = {}
        for p in self.k.items(r):
            if p.get("status", {}).get("phase") in ("Succeeded", "Failed"):
                continue
            node = p.get("spec", {}).get("nodeName")
            if not node:
                continue
            tot = 0
            for c in p.get("spec", {}).get("containers", []):
                res = c.get("resources", {}) or {}
                v = (res.get("limits", {}) or {}).get("nvidia.com/gpu") \
                    or (res.get("requests", {}) or {}).get("nvidia.com/gpu") or 0
                try:
                    tot += int(v)
                except (TypeError, ValueError):
                    pass
            if tot:
                used[node] = used.get(node, 0) + tot
        return used, True

    def _dra_alloc_owner(self):
        """Which DRA device is allocated to whom, from ResourceClaims.
        Returns (owner, ok): owner maps (node, device_name) -> "ui" | "ext".
        "ui" = a claim this UI created for its own instances (our namespace +
        PREFIX-named); "ext" = any other tenant's DRA claim. The device name lets
        us fold MIG partitions onto their parent physical GPU when counting.
        ok=False when the SA can't list resourceclaims."""
        if not config.DRA_ENABLED:
            return {}, True
        r = self.k.get(f"/apis/{config.DRA_API_VERSION}/resourceclaims")
        if not self.k.ok(r):
            return {}, False
        owner = {}
        for c in self.k.items(r):
            md = c.get("metadata", {}) or {}
            mine = (md.get("namespace") == config.NAMESPACE
                    and str(md.get("name", "")).startswith(config.PREFIX))
            who = "ui" if mine else "ext"
            alloc = (c.get("status", {}) or {}).get("allocation") or {}
            for d in (alloc.get("devices", {}) or {}).get("results", []) or []:
                drv = d.get("driver", "")
                if drv and config.DRA_DRIVER not in drv:
                    continue
                node, dev = d.get("pool"), d.get("device")
                if node and dev is not None:
                    # a UI claim wins the label if a device somehow appears twice
                    if owner.get((node, dev)) != "ui":
                        owner[(node, dev)] = who
        return owner, True

    def overview(self):
        nodes = self.k.items(self.k.get("/api/v1/nodes"))
        pod_used, ok = self._used_by_node()      # device-plugin pods = other tenants' workloads
        alloc_owner, _ = self._dra_alloc_owner()  # (node,device) -> "ui"|"ext"
        bans, bans_ok = self.policy.list()
        banned_uuids = set(policy.banned_gpu_uuids(bans))
        # DRA per-GPU ground truth per node - node labels lie on mixed nodes
        # (e.g. sv4000-1 = A6000x2 + A100x1, label says A100). {} -> legacy.
        slices = policy.node_gpu_devices(self.k) if config.DRA_ENABLED else {}
        out = []
        for n in nodes:
            nm = n["metadata"]["name"]
            alloc = n.get("status", {}).get("allocatable", {}) or {}
            cap = n.get("status", {}).get("capacity", {}) or {}
            dp_total = int(alloc.get("nvidia.com/gpu", cap.get("nvidia.com/gpu", 0)) or 0)
            devices = slices.get(nm)
            # DRA ResourceSlices are the source of truth for how many PHYSICAL GPUs
            # exist (MIG partitions already folded into parents); the device-plugin
            # count is only a fallback (and 0 on DRA-only nodes).
            total = len(devices) if devices else dp_total
            if total <= 0:
                continue  # only nodes the cluster actually recognizes as GPU nodes
            label_product = n["metadata"].get("labels", {}).get("nvidia.com/gpu.product", "GPU")
            # UI product-bans (kind=product) stay label-matched: enforced through
            # nodeAffinity (node granularity), unlike INSTANCE_DENY_PRODUCTS which is
            # per-GPU via the claim CEL.
            fl = policy.flags_for(nm, label_product, bans)
            banned = fl["nodeBanned"] or fl["productBanned"]
            dev_json = []
            if devices:
                # product string + nvenc from per-GPU DRA attributes, not node label
                prods = [d["product"] for d in devices if d["product"]]
                uniq = list(dict.fromkeys(prods))
                product = " + ".join(uniq) if uniq else label_product
                nvenc = any(nvenc_capable(p) for p in prods) if prods \
                    else nvenc_capable(label_product)
                # physical-GPU accounting: each GPU falls into exactly one bucket.
                # A GPU counts as used if the parent OR any MIG partition is allocated.
                ui_u = ext_u = ban_used = denied_gpus = free = 0
                for d in devices:
                    owners = [alloc_owner.get((nm, x["name"]))
                              for x in ([d] + d["mig"])]
                    owners = [o for o in owners if o]
                    is_ban = d["uuid"] in banned_uuids
                    is_den = policy.product_denied(d["product"])
                    if owners:
                        if any(o == "ui" for o in owners):
                            ui_u += 1; state = "ui"
                        else:
                            ext_u += 1; state = "ext"
                    elif is_ban:
                        ban_used += 1; state = "banned"
                    elif is_den:
                        denied_gpus += 1; state = "denied"
                    else:
                        free += 1; state = "free"
                    dev_json.append({
                        "name": d["name"], "uuid": d["uuid"], "product": d["product"],
                        "banned": is_ban, "denied": is_den, "state": state,
                        "mig": [{"name": m["name"], "uuid": m["uuid"],
                                 "product": m["product"],
                                 "used": (nm, m["name"]) in alloc_owner,
                                 "owner": alloc_owner.get((nm, m["name"]), "")}
                                for m in d["mig"]]})
                u = ui_u + ext_u
                denied = denied_gpus >= len(devices)   # whole node incompatible
            else:
                # legacy node-label granularity (DRA off or slices unreadable)
                product = label_product
                nvenc = nvenc_capable(label_product)
                u = min(pod_used.get(nm, 0), total) if ok else 0
                ui_u, ext_u = 0, u
                ban_used = len(fl["gpuBans"]) if (config.GPU_BAN_AS_USED or
                                                  config.DRA_ENABLED) else fl["pendingGpuBans"]
                denied_gpus = 0
                denied = policy.product_denied(product)   # permanent hardware exclusion
                free = max(total - u - ban_used - denied_gpus, 0)
            out.append({"node": nm, "product": product, "nvenc": nvenc,
                        "total": total, "used": u, "free": free,
                        "uiUsed": ui_u, "extUsed": ext_u,
                        "devices": dev_json,
                        "allowed": nm in config.NODES,
                        "banned": banned, "banReasons": fl["banReasons"],
                        "gpuBans": fl["gpuBans"],
                        "denied": denied, "deniedGpus": denied_gpus,
                        "draExact": bool(devices),
                        "deniedReason": "instances disabled · incompatible product "
                                        "(INSTANCE_DENY_PRODUCTS)" if denied else ""})
        out.sort(key=lambda r: r["node"])
        totals = {"total": sum(x["total"] for x in out),
                  "used": sum(x["used"] for x in out),
                  "free": sum(x["free"] for x in out)}
        byprod = {}
        for x in out:
            b = byprod.setdefault(x["product"], {"total": 0, "used": 0, "free": 0})
            b["total"] += x["total"]; b["used"] += x["used"]; b["free"] += x["free"]
        # Launchable = free GPUs on instance-set nodes that aren't node/product-banned.
        # DRA-exact rows already subtracted denied/banned GPUs (and the per-GPU CEL
        # enforces them), so the node-level nvenc/denied gates only apply to legacy
        # rows - otherwise a mixed node's A100 label would hide its good GPUs.
        launchable = sum(x["free"] for x in out
                         if x["allowed"] and not x["banned"]
                         and (x["draExact"] or (x["nvenc"] and not x["denied"]))
                         ) if ok else 0
        return {"nodes": out, "totals": totals, "byProduct": byprod,
                "launchable": launchable, "usageKnown": ok, "allowedNodes": config.NODES,
                "bans": bans, "bansOk": bans_ok, "banAsUsed": config.GPU_BAN_AS_USED,
                "draEnabled": config.DRA_ENABLED,
                "banStore": getattr(self.policy.store, "name", "?")}
