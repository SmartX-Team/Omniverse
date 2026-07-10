"""Per-instance metrics, read from the cluster Prometheus (range queries).

Pure read path: queries the monitoring-ns Prometheus over in-cluster HTTP and shapes
the result for the UI dashboard. **Fails soft** - if Prometheus is unreachable, errors,
or has no data, it returns ``available: False`` (or an empty instance list) and the UI
shows an empty state. Nothing here can take the instance pods or the UI down.

Network metrics come from each instance's OTel Collector sidecar (hostmetrics:network),
scraped by Prometheus with the pod's ``app``/``owner`` labels attached. GPU metrics come
from the cluster's existing DCGM exporter (gpu-operator) - no per-instance sidecar needed;
they carry a ``modelName`` label (per-GPU, so mixed nodes are exact) and a ``pod`` label
(pod-resources mapping) so we can break them down by GPU model AND by instance.
"""
import json
import time
import urllib.parse
import urllib.request

from . import config

# DCGM exporter metric names (already scraped into the cluster Prometheus).
DCGM_UTIL = "DCGM_FI_DEV_GPU_UTIL"      # GPU utilization %       (per physical GPU)
DCGM_ENC = "DCGM_FI_DEV_ENC_UTIL"       # NVENC encoder util %    (A100 has no NVENC -> ~0)
DCGM_FB_USED = "DCGM_FI_DEV_FB_USED"    # framebuffer used  (MiB)
DCGM_FB_FREE = "DCGM_FI_DEV_FB_FREE"    # framebuffer free  (MiB)


class MetricsService:
    def __init__(self, base_url=None, timeout=5):
        self.base = (base_url or config.PROMETHEUS_URL).rstrip("/")
        self.timeout = timeout

    def _query_range(self, query, start, end, step):
        qs = urllib.parse.urlencode({"query": query, "start": start,
                                     "end": end, "step": f"{step}s"})
        req = urllib.request.Request(f"{self.base}/api/v1/query_range?{qs}",
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("status") != "success":
            raise RuntimeError(data.get("error", "prometheus query failed"))
        return data["data"]["result"]

    def _query(self, query):
        """Instant query -> list of {metric, value:[ts, 'val']} (for real-time/verify)."""
        qs = urllib.parse.urlencode({"query": query})
        req = urllib.request.Request(f"{self.base}/api/v1/query?{qs}",
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("status") != "success":
            raise RuntimeError(data.get("error", "prometheus query failed"))
        return data["data"]["result"]

    def verify(self):
        """Per-pod collection health + live network rates (instant). For the in-UI
        verification panel: proves Prometheus is actually scraping each instance's
        collector and that network data is flowing - without Grafana. Fail-soft.

        Returns {available, ts, podsUp, podsTotal, pods:[{pod, app, owner, up,
        samples, txBps, rxBps}]} or {available: False, reason, promURL}."""
        g = config.GROUP
        pods = {}

        def row(m):
            pod = m.get("pod") or m.get("app", "?")
            return pods.setdefault(pod, {"pod": pod, "app": m.get("app", "?"),
                                         "owner": m.get("owner", ""), "up": None,
                                         "samples": None, "txBps": None, "rxBps": None,
                                         "gpuUtil": None, "gpuModel": ""})
        try:
            # scrape health (1/0) - is Prometheus successfully scraping the sidecar?
            for s in self._query(f'up{{group="{g}"}}'):
                row(s["metric"])["up"] = int(float(s["value"][1]))
            # samples scraped per target - is data actually flowing?
            for s in self._query(f'scrape_samples_scraped{{group="{g}"}}'):
                row(s["metric"])["samples"] = int(float(s["value"][1]))
            # live tx/rx rate per pod (bytes/s) over a short window
            for direction, key in (("transmit", "txBps"), ("receive", "rxBps")):
                q = ("sum by (pod, app, owner) (rate("
                     f'system_network_io_bytes_total{{group="{g}", '
                     f'direction="{direction}", device!="lo"}}[1m]))')
                for s in self._query(q):
                    row(s["metric"])[key] = round(float(s["value"][1]), 2)
            # live GPU utilization per instance pod (DCGM). The GPU-consuming pod lands in
            # `exported_pod` when Prometheus scrapes dcgm-exporter via the kubernetes-pods
            # job (label collision, honor_labels=false); fall back to `pod` otherwise.
            # Only updates pods we already know about - never creates GPU-only rows.
            for s in self._query(f"avg by (pod, exported_pod, modelName) ({DCGM_UTIL})"):
                m = s["metric"]
                r = pods.get(m.get("exported_pod") or m.get("pod"))
                if r:
                    r["gpuUtil"] = round(float(s["value"][1]), 1)
                    r["gpuModel"] = m.get("modelName", "")
        except Exception as e:
            return {"available": False, "reason": str(e)[:200], "promURL": self.base}
        rows = sorted(pods.values(), key=lambda x: (x["app"], x["pod"]))
        return {"available": True, "promURL": self.base, "ts": int(time.time()),
                "podsUp": sum(1 for r in rows if r["up"] == 1),
                "podsTotal": len(rows), "pods": rows}

    def series(self, window=3600, step=None):
        """TX/RX network bandwidth (bytes/s) per instance over the last ``window`` seconds.

        Returns {available, window, step, instances:[{app, owner, tx:[[ts,v]], rx:[...]}]}
        or {available: False, reason, promURL} on any failure."""
        window = int(window)
        end = int(time.time())
        start = end - window
        step = int(step or max(15, window // 120))   # ~120 points across the window
        g = config.GROUP
        out = {}
        try:
            for direction, key in (("transmit", "tx"), ("receive", "rx")):
                q = ("sum by (app, owner) (rate("
                     f'system_network_io_bytes_total{{group="{g}", '
                     f'direction="{direction}", device!="lo"}}[5m]))')
                for ser in self._query_range(q, start, end, step):
                    m = ser.get("metric", {})
                    app = m.get("app", "?")
                    row = out.setdefault(app, {"app": app, "owner": m.get("owner", ""),
                                               "tx": [], "rx": []})
                    if not row["owner"] and m.get("owner"):
                        row["owner"] = m["owner"]
                    row[key] = [[int(float(ts)), round(float(v), 2)]
                                for ts, v in ser.get("values", [])]
        except Exception as e:   # connection refused, timeout, DNS, bad JSON, etc.
            return {"available": False, "reason": str(e)[:200],
                    "promURL": self.base, "window": window}
        return {"available": True, "window": window, "step": step,
                "promURL": self.base,
                "instances": sorted(out.values(), key=lambda x: x["app"])}

    def gpu(self):
        """Cluster GPU telemetry from DCGM, broken down two ways (instant). Fail-soft.

        - byModel:    util/encoder/VRAM aggregated per GPU model (A10/A100/L40S/A6000...).
                      Uses the per-GPU ``modelName`` label, so mixed nodes are exact.
                      (A100 ENC_UTIL stays ~0 - it has no NVENC engine; this is the data
                      that justifies excluding A100 from streaming instances.)
        - instances:  util/encoder/VRAM for GPUs currently held by our instance pods,
                      joined via the DCGM ``exported_pod`` label (pod-resources mapping;
                      falls back to ``pod`` if Prometheus keeps the workload label there).

        Returns {available, ts, promURL, byModel:[...], instances:[...]} or
        {available: False, reason, promURL}."""
        models, insts = {}, {}

        def mrow(name):
            return models.setdefault(name, {"modelName": name, "gpus": None,
                                            "utilAvg": None, "encAvg": None,
                                            "fbUsedMiB": None, "fbFreeMiB": None})

        def irow(pod, m):
            return insts.setdefault(pod, {"pod": pod, "modelName": m.get("modelName", ""),
                                          "gpuUtil": None, "encUtil": None,
                                          "fbUsedMiB": None, "fbFreeMiB": None})
        try:
            # --- per GPU model (whole cluster) ---
            # Dedup by physical-GPU UUID first, THEN aggregate, so duplicate/MIG series for
            # one GPU are not double-counted. Count uses the same FB base as the VRAM sums,
            # so `gpus` and the totals always agree (fixes A100 FB > card capacity).
            for s in self._query(
                    f"count by (modelName) (max by (modelName, UUID) ({DCGM_FB_USED}))"):
                mrow(s["metric"].get("modelName", "?"))["gpus"] = int(float(s["value"][1]))
            for q, key in (
                    (f"avg by (modelName) (avg by (modelName, UUID) ({DCGM_UTIL}))", "utilAvg"),
                    (f"avg by (modelName) (avg by (modelName, UUID) ({DCGM_ENC}))", "encAvg"),
                    (f"sum by (modelName) (max by (modelName, UUID) ({DCGM_FB_USED}))", "fbUsedMiB"),
                    (f"sum by (modelName) (max by (modelName, UUID) ({DCGM_FB_FREE}))", "fbFreeMiB")):
                for s in self._query(q):
                    mrow(s["metric"].get("modelName", "?"))[key] = round(float(s["value"][1]), 1)
            # --- per instance pod (only GPUs our instances hold) ---
            # Consuming pod is in `exported_pod` (or `pod` w/ honor_labels); filter to our
            # instances in code. FB summed after a per-UUID dedup, as in byModel above.
            for q, key in (
                    (f"avg by (exported_pod, pod, modelName) ({DCGM_UTIL})", "gpuUtil"),
                    (f"avg by (exported_pod, pod, modelName) ({DCGM_ENC})", "encUtil"),
                    (f"sum by (exported_pod, pod, modelName) "
                     f"(max by (exported_pod, pod, modelName, UUID) ({DCGM_FB_USED}))", "fbUsedMiB"),
                    (f"sum by (exported_pod, pod, modelName) "
                     f"(max by (exported_pod, pod, modelName, UUID) ({DCGM_FB_FREE}))", "fbFreeMiB")):
                for s in self._query(q):
                    m = s["metric"]
                    pod = m.get("exported_pod") or m.get("pod") or ""
                    if pod.startswith(config.PREFIX):
                        irow(pod, m)[key] = round(float(s["value"][1]), 1)
        except Exception as e:
            return {"available": False, "reason": str(e)[:200], "promURL": self.base}
        return {"available": True, "ts": int(time.time()), "promURL": self.base,
                "byModel": sorted(models.values(), key=lambda x: x["modelName"]),
                "instances": sorted(insts.values(), key=lambda x: x["pod"])}

    def gpu_window_stats(self, uuid, start, end, warmup=120):
        """DCGM stats for ONE physical GPU (by UUID) over [start(+warmup), end].
        Used by scenes.py to grade how heavy a USD stage was on that GPU.
        Returns {utilAvg, utilP95, utilMax, encAvg, encMax, fbMaxMiB, samples}
        or None (fail-soft: prometheus down / no data / no uuid)."""
        try:
            start, end = int(start), int(end)
            if not uuid or end <= start:
                return None
            if end - start > 2 * warmup:      # skip load warm-up unless window is tiny
                start += warmup
            step = max(15, (end - start) // 120)
            frag = uuid.replace("GPU-", "")[:8]
            series = {}
            for key, metric in (("util", DCGM_UTIL), ("enc", DCGM_ENC),
                                ("fb", DCGM_FB_USED)):
                vals = []
                q = f'max by (UUID) ({metric}{{UUID=~".*{frag}.*"}})'
                for ser in self._query_range(q, start, end, step):
                    vals += [float(v) for _, v in ser.get("values", [])]
                series[key] = vals
            u = series["util"]
            if not u:
                return None
            su = sorted(u)
            p95 = su[max(0, min(len(su) - 1, int(0.95 * (len(su) - 1))))]
            out = {"utilAvg": round(sum(u) / len(u), 1), "utilP95": round(p95, 1),
                   "utilMax": round(max(u), 1), "samples": len(u)}
            if series["enc"]:
                e = series["enc"]
                out["encAvg"] = round(sum(e) / len(e), 1)
                out["encMax"] = round(max(e), 1)
            if series["fb"]:
                out["fbMaxMiB"] = round(max(series["fb"]), 0)
            return out
        except Exception:
            return None
