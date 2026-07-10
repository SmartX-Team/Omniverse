"""Scene load history (domain layer).

Records WHICH USD stage was open in WHICH instance on WHICH physical GPU, and how
hard that GPU worked while the stage was open - so "this scene is fine on an L40S
but chokes an RTX A6000" stops being anecdote and becomes a queryable table.

Flow:
  1. The instance image (6.0+) runs /opt/experiment/stage_report.py inside Kit; on
     every stage OPENED/CLOSING it POSTs {instance, stage, event} to /api/stage-report.
  2. report() opens/closes a *session* per instance: {stage, instance, node,
     gpuUUID, gpuModel, start, end, stats}. The GPU identity is resolved at open
     time via InstanceService (DRA claim -> UUID, same source the Details view uses).
  3. On close, MetricsService.gpu_window_stats() pulls DCGM util/NVENC/VRAM for that
     UUID over the session window (warm-up trimmed) and stores the summary.
  4. list() serves raw sessions + per (stage x gpuModel) aggregates for the UI.

Storage: a namespace ConfigMap (SCENES_CM), same pattern as the ban store - newest
SCENES_MAX sessions kept. Everything fails soft; a broken Prometheus only means a
session without stats, never a failed instance or request.
"""
import datetime
import json
import uuid as uuidlib

from . import config
from .k8s import K8sClient


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(iso):
    try:
        return int(datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
                   .replace(tzinfo=datetime.timezone.utc).timestamp())
    except Exception:
        return 0


def _short(stage):
    """omniverse://host/Projects/OOS/scene.usd -> scene.usd (display aid)."""
    return (stage or "").rstrip("/").rsplit("/", 1)[-1] or stage or "?"


class SceneService:
    def __init__(self, client=None, metrics=None, instances=None):
        self.k = client or K8sClient()
        self.metrics = metrics        # MetricsService (gpu_window_stats) - may be None
        self.instances = instances    # InstanceService (gpu_of) - may be None

    # ------------------------------------------------------------------ store
    def _load(self):
        r = self.k.get(f"/api/v1/namespaces/{config.NAMESPACE}/configmaps/{config.SCENES_CM}")
        if not self.k.ok(r):
            return []
        try:
            return json.loads((r.get("data", {}) or {}).get("sessions", "[]") or "[]")
        except Exception:
            return []

    def _save(self, sessions):
        sessions = sessions[-config.SCENES_MAX:]
        self.k.apply_configmap(config.SCENES_CM,
                               {"sessions": json.dumps(sessions, ensure_ascii=False)})

    # ------------------------------------------------------------------ write
    def report(self, instance, stage, event):
        """Handle one stage event from an instance. Always (True, msg) - fail-soft."""
        instance = (instance or "").strip()
        event = (event or "").strip().lower()
        stage = (stage or "").strip()
        if not instance or event not in ("opened", "closing"):
            return False, "need instance + event in (opened, closing)"
        sessions = self._load()
        now = _now_iso()
        # any event ends the currently-open session of this instance
        for s in sessions:
            if s.get("instance") == instance and not s.get("end"):
                s["end"] = now
                s["stats"] = self._stats(s)
        if event == "opened" and stage:
            uuid, model, node = ("", "", "")
            if self.instances is not None:
                uuid, model, node = self.instances.gpu_of(instance)
            sessions.append({"id": "s-" + uuidlib.uuid4().hex[:12],
                             "instance": instance, "stage": stage,
                             "node": node, "gpuUUID": uuid, "gpuModel": model,
                             "start": now, "end": "", "stats": None})
        try:
            self._save(sessions)
        except Exception as e:
            return False, f"store write failed: {e}"
        return True, "recorded"

    def _stats(self, s):
        if self.metrics is None or not s.get("gpuUUID"):
            return s.get("stats")
        st = self.metrics.gpu_window_stats(s["gpuUUID"], _epoch(s["start"]),
                                           _epoch(s["end"]) or _epoch(_now_iso()))
        return st or s.get("stats")

    # ------------------------------------------------------------------ read
    def list(self):
        """{available, sessions(newest first), byScene: per stage x gpuModel}."""
        try:
            sessions = self._load()
        except Exception as e:
            return {"available": False, "reason": str(e)[:200],
                    "sessions": [], "byScene": []}
        # live stats for still-open sessions (display only, never persisted)
        out_sessions = []
        for s in sessions:
            row = dict(s)
            row["stageShort"] = _short(s.get("stage"))
            if not s.get("end"):
                live = dict(s, end=_now_iso())
                row["stats"] = self._stats(live)
                row["open"] = True
            out_sessions.append(row)
        # aggregate: stage x gpuModel over sessions that have stats
        agg = {}
        for s in out_sessions:
            st = s.get("stats")
            if not st:
                continue
            key = (s.get("stage", "?"), s.get("gpuModel") or "?")
            a = agg.setdefault(key, {"stage": key[0], "stageShort": _short(key[0]),
                                     "gpuModel": key[1], "n": 0, "_util": [],
                                     "utilP95": 0.0, "utilMax": 0.0,
                                     "encMax": 0.0, "fbMaxMiB": 0.0})
            a["n"] += 1
            a["_util"].append(st.get("utilAvg", 0.0))
            a["utilP95"] = max(a["utilP95"], st.get("utilP95", 0.0))
            a["utilMax"] = max(a["utilMax"], st.get("utilMax", 0.0))
            a["encMax"] = max(a["encMax"], st.get("encMax", 0.0))
            a["fbMaxMiB"] = max(a["fbMaxMiB"], st.get("fbMaxMiB", 0.0))
        by_scene = []
        for a in agg.values():
            u = a.pop("_util")
            a["utilAvg"] = round(sum(u) / len(u), 1) if u else 0.0
            by_scene.append(a)
        by_scene.sort(key=lambda x: -x["utilMax"])
        out_sessions.reverse()   # newest first
        return {"available": True, "sessions": out_sessions[:100], "byScene": by_scene}
