"""GPU ban policy (domain layer).

Records and resolves scheduling bans at three granularities:
  kind=node     ban a whole node                         (node)
  kind=product  ban a GPU product family, e.g. A100/A10  (product, substring match
                against the node's nvidia.com/gpu.product label, case-insensitive)
  kind=gpu      ban one physical GPU on one node         (node + uuid, optional index)

Storage: Redis when REDIS_HOST is set (redis-py, single JSON blob under one key),
otherwise a ConfigMap in the namespace - so the feature works before any DB is
deployed. Long-term home is PostgreSQL (see k8s/db/): add a PostgresStore class here
and nothing above this module changes.

ENFORCEMENT REALITY (important):
- node / product bans are fully enforced by this app: banned nodes are removed from
  the nodeAffinity of every new instance.
- gpu (UUID) bans are enforced via DRA when DRA_ENABLED: banned_gpu_uuids() feeds the
  per-instance ResourceClaimTemplate's CEL deny-list (see resources.py). Without DRA
  the NVIDIA device plugin assigns GPUs opaquely, so this app can only do best effort:
    * subtracts un-applied UUID bans from the node's free count,
    * excludes the node entirely from new-instance affinity when ALL of its GPUs
      are UUID-banned,
    * shows the ban prominently in the UI.
"""
import datetime
import json
import uuid as uuidlib

import redis

from . import config
from .k8s import K8sClient

KINDS = ("node", "product", "gpu")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- stores
class RedisStore:
    name = "redis"

    def __init__(self, host=None, port=None, key=None):
        self._key = key or config.REDIS_KEY
        self._r = redis.Redis(host=host or config.REDIS_HOST,
                              port=int(port or config.REDIS_PORT),
                              decode_responses=True,
                              socket_timeout=3, socket_connect_timeout=3)

    def load(self):
        v = self._r.get(self._key)
        return json.loads(v) if v else []

    def save(self, bans):
        self._r.set(self._key, json.dumps(bans, ensure_ascii=False))


class ConfigMapStore:
    """Bans as JSON in a namespace ConfigMap (no extra infra; default store)."""

    name = "configmap"

    def __init__(self, client=None):
        self.k = client or K8sClient()
        self._path = f"/api/v1/namespaces/{config.NAMESPACE}/configmaps/{config.POLICY_CM}"

    def load(self):
        r = self.k.get(self._path)
        if not self.k.ok(r):
            if r.get("_error") == 404:
                return []
            raise RuntimeError(f"configmap read failed: {r.get('_msg', '')[:120]}")
        return json.loads((r.get("data", {}) or {}).get("bans", "[]") or "[]")

    def save(self, bans):
        body = {"data": {"bans": json.dumps(bans, ensure_ascii=False)}}
        r = self.k.patch(self._path, body, ctype="application/merge-patch+json")
        if not self.k.ok(r) and r.get("_error") == 404:
            r = self.k.post(f"/api/v1/namespaces/{config.NAMESPACE}/configmaps",
                            {"apiVersion": "v1", "kind": "ConfigMap",
                             "metadata": {"name": config.POLICY_CM, "namespace": config.NAMESPACE},
                             **body})
        if not self.k.ok(r):
            raise RuntimeError(f"configmap write failed: {r.get('_msg', '')[:120]}")


# ---------------------------------------------------------------- service
class PolicyService:
    def __init__(self, store=None, client=None):
        if store is not None:
            self.store = store
        elif config.REDIS_HOST:
            self.store = RedisStore()
        else:
            self.store = ConfigMapStore(client)

    def list(self):
        """-> (bans, ok). On store failure returns ([], False) so callers degrade."""
        try:
            return self.store.load(), True
        except Exception:
            return [], False

    def add(self, kind, node="", product="", uuid="", index=None, reason="", by=""):
        kind = (kind or "").strip().lower()
        node, product, uuid = node.strip(), product.strip(), uuid.strip()
        if kind not in KINDS:
            return False, f"kind must be one of {KINDS}"
        if kind == "node" and not node:
            return False, "node ban needs a node name"
        if kind == "product" and not product:
            return False, "product ban needs a product string (e.g. A100)"
        if kind == "gpu" and not (node and uuid):
            return False, "gpu ban needs node + GPU UUID (nvidia-smi -L on the node)"
        try:
            bans = self.store.load()
        except Exception as e:
            return False, f"store unavailable: {e}"
        for b in bans:  # idempotency
            if (b.get("kind"), b.get("node"), b.get("product"), b.get("uuid")) == \
                    (kind, node, product, uuid):
                return False, "identical ban already exists"
        ban = {"id": "b-" + uuidlib.uuid4().hex[:12],
               "kind": kind, "node": node, "product": product, "uuid": uuid,
               "index": index, "reason": reason.strip(), "by": by.strip(),
               "at": _now_iso(), "applied": False}
        bans.append(ban)
        try:
            self.store.save(bans)
        except Exception as e:
            return False, f"store write failed: {e}"
        return True, f"banned {kind} " + (uuid or product or node)

    def remove(self, ban_id):
        try:
            bans = self.store.load()
            keep = [b for b in bans if b.get("id") != ban_id]
            if len(keep) == len(bans):
                return False, "ban not found"
            self.store.save(keep)
            return True, "ban removed"
        except Exception as e:
            return False, f"store error: {e}"

    def set_applied(self, ban_id, applied):
        """Mark a gpu-UUID ban as enforced node-side (device plugin exclusion done)."""
        try:
            bans = self.store.load()
            for b in bans:
                if b.get("id") == ban_id:
                    b["applied"] = bool(applied)
                    self.store.save(bans)
                    return True, ("marked applied" if applied else "marked pending")
            return False, "ban not found"
        except Exception as e:
            return False, f"store error: {e}"

    def seed_defaults(self):
        """Ensure the config default GPU bans (DEFAULT_GPU_BANS) exist in the store.
        Idempotent + fail-soft; called at startup so permanently-unusable GPUs are banned
        from the first load. A UI remove is undone on the next restart (intended for
        hardware that is always unusable)."""
        defaults = default_gpu_bans()
        if not defaults:
            return 0
        try:
            bans = self.store.load()
        except Exception:
            return 0
        have = {(b.get("kind"), b.get("node"), b.get("uuid")) for b in bans}
        added = 0
        for d in defaults:
            if ("gpu", d["node"], d["uuid"]) in have:
                continue
            bans.append({"id": "b-" + uuidlib.uuid4().hex[:12], "kind": "gpu",
                         "node": d["node"], "product": "", "uuid": d["uuid"], "index": None,
                         "reason": d.get("reason") or "default: permanently unusable GPU",
                         "by": "system", "at": _now_iso(), "applied": False, "default": True})
            added += 1
        if added:
            try:
                self.store.save(bans)
            except Exception:
                return 0
        return added


# ---------------------------------------------------------------- pure resolution
def flags_for(node_name, product, bans):
    """Resolve all bans hitting one node. Pure - trivial to unit-test."""
    node_b = [b for b in bans if b.get("kind") == "node" and b.get("node") == node_name]
    prod_b = [b for b in bans if b.get("kind") == "product"
              and b.get("product", "").upper() in (product or "").upper()]
    gpu_b = [b for b in bans if b.get("kind") == "gpu" and b.get("node") == node_name]
    reasons = [b.get("reason") or b.get("kind") for b in node_b + prod_b]
    return {
        "nodeBanned": bool(node_b),
        "productBanned": bool(prod_b),
        "banReasons": reasons,
        "gpuBans": [{"id": b["id"], "uuid": b.get("uuid", ""), "index": b.get("index"),
                     "applied": bool(b.get("applied")), "reason": b.get("reason", "")}
                    for b in gpu_b],
        "pendingGpuBans": sum(1 for b in gpu_b if not b.get("applied")),
    }


def banned_gpu_uuids(bans):
    """UUIDs of every kind=gpu ban (deduped, order-stable). Fed to the DRA claim's CEL
    deny-list so these physical GPUs are excluded from new instances at schedule time.
    Under DRA this is real enforcement; the old 'applied' flag - a device-plugin-era
    marker for node-side exclusion - no longer gates it."""
    seen, out = set(), []
    for b in bans:
        if b.get("kind") == "gpu":
            u = (b.get("uuid") or "").strip()
            if u and u not in seen:
                seen.add(u)
                out.append(u)
    return out


def default_gpu_bans():
    """Parse config.DEFAULT_GPU_BANS -> [{"node","uuid"}]. Items are "node:UUID",
    comma- or whitespace-separated (e.g. "l40s:GPU-812... l40s:GPU-e96...")."""
    out = []
    for tok in (config.DEFAULT_GPU_BANS or "").replace(",", " ").split():
        if ":" not in tok:
            continue
        node, uuid = tok.split(":", 1)
        node, uuid = node.strip(), uuid.strip()
        if node and uuid:
            out.append({"node": node, "uuid": uuid})
    return out


def product_denied(product):
    """True if this GPU product is config-denied for instances (permanent hardware
    constraint, e.g. no NVENC) - independent of the revocable ban system."""
    pu = (product or "").upper()
    return any(d.upper() in pu for d in config.INSTANCE_DENY_PRODUCTS)


def _mig_parent(name):
    """Parent physical-GPU device name for a MIG partition, else None.
    The NVIDIA DRA driver names MIG devices '<gpu>-mig-<profile>-<start>-<size>'
    (e.g. 'gpu-1-mig-19-0-1' belongs to 'gpu-1')."""
    return name.split("-mig-", 1)[0] if "-mig-" in (name or "") else None


def node_gpu_devices(k8s):
    """{node: [gpu, ...]} - the PHYSICAL GPUs the NVIDIA DRA driver advertises,
    from ResourceSlices. Each gpu is a dict:
        {"name","uuid","product","mig": [ {"name","uuid","product"}, ... ]}
    MIG partitions ('<gpu>-mig-...') are folded into their parent GPU's `mig`
    list rather than counted as separate physical GPUs - so a MIG-sliced A100 is
    still ONE GPU but its partitions stay visible as sub-devices. One API call;
    {} on failure or missing resourceslices:list RBAC (fail-soft).

    Only slices from the NVIDIA GPU driver (config.DRA_DRIVER) are read - slices
    from other DRA drivers (e.g. compute-domain.nvidia.com) or leftover hand-made
    test slices would otherwise inject phantom devices under a real node's name.
    Node = spec.nodeName when present, else the pool name (== node for this driver)."""
    out = {}
    r = k8s.get(f"/apis/{config.DRA_API_VERSION}/resourceslices")
    if not k8s.ok(r):
        return {}
    # local import: instances.py owns the schema-tolerant attribute walkers
    from .instances import InstanceService
    raw = {}   # node -> {"parents": {name: gpu}, "migs": [(parent_name, mig)]}
    for sli in k8s.items(r):
        spec = sli.get("spec", {}) or {}
        drv = spec.get("driver", "")
        if drv and config.DRA_DRIVER not in drv:
            continue    # not the NVIDIA GPU driver - ignore foreign/test slices
        node = spec.get("nodeName") or (spec.get("pool", {}) or {}).get("name")
        if not node:
            continue
        bucket = raw.setdefault(node, {"parents": {}, "migs": []})
        for d in spec.get("devices", []) or []:
            name = d.get("name") or ""
            gpu = {"name": name,
                   "uuid": InstanceService._find_uuid(d) or "",
                   "product": InstanceService._find_product(d),
                   "mig": []}
            parent = _mig_parent(name)
            if parent:
                bucket["migs"].append((parent, gpu))
            else:
                bucket["parents"][name] = gpu
    for node, bucket in raw.items():
        parents = bucket["parents"]
        for parent_name, mig in bucket["migs"]:
            p = parents.get(parent_name)
            if p is None:   # pure-MIG mode: full GPU not separately advertised
                p = {"name": parent_name, "uuid": "",
                     "product": mig["product"], "mig": []}
                parents[parent_name] = p
            p["mig"].append(mig)
        out[node] = list(parents.values())
    return out


def node_unavailable_count(devices, banned_uuids):
    """How many of a node's PHYSICAL GPUs are unusable for NEW instances: the UNION
    of UUID-banned and product-denied GPUs (a GPU that is both counts once)."""
    n = 0
    for d in devices:
        if d["uuid"] in banned_uuids or product_denied(d["product"]):
            n += 1
    return n


def eligible_nodes(k8s, bans):
    """config.NODES minus banned nodes/products minus config-denied products minus
    nodes with no allocatable GPU left. Builds the nodeAffinity of every NEW instance.

    DRA path (per-GPU exact): product denies and UUID bans are enforced inside the
    ResourceClaim's CEL, so a node is only excluded when EVERY GPU it advertises is
    unavailable (union of bans + denied products). Mixed nodes keep their
    compatible GPUs schedulable.
    Legacy path (no DRA / no slices): node-level - a product-denied node label
    excludes the whole node, and pending UUID bans count against the total."""
    banned_uuids = set(banned_gpu_uuids(bans))
    slices = node_gpu_devices(k8s) if config.DRA_ENABLED else {}
    out = []
    for n in k8s.items(k8s.get("/api/v1/nodes")):
        nm = n["metadata"]["name"]
        if nm not in config.NODES:
            continue
        product = n["metadata"].get("labels", {}).get("nvidia.com/gpu.product", "")
        fl = flags_for(nm, product, bans)
        if fl["nodeBanned"] or fl["productBanned"]:
            continue
        devices = slices.get(nm)
        if devices:
            # DRA exact accounting: exclude only when nothing on the node is usable
            if node_unavailable_count(devices, banned_uuids) >= len(devices):
                continue
        else:
            # legacy / slices unavailable: node-label granularity
            if product_denied(product):
                continue  # incompatible hardware - never schedule here
            alloc = n.get("status", {}).get("allocatable", {}) or {}
            total = int(alloc.get("nvidia.com/gpu", 0) or 0)
            if total > 0 and fl["pendingGpuBans"] >= total:
                continue  # every remaining GPU on this node is banned
        out.append(nm)
    return out
