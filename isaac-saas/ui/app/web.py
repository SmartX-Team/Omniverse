"""HTTP delivery layer (FastAPI + uvicorn).

Thin - it only parses requests and delegates to the domain services, then serializes
the result. Services are injected via create_app(), so the app is testable with fakes
(fastapi.testclient) without an in-cluster ServiceAccount.

Endpoints are plain `def` (not async): the services do blocking urllib I/O and
instances.create() polls the LB IP for up to 15s - FastAPI runs sync handlers in a
threadpool, so the event loop is never blocked.

Interactive API docs: /docs (Swagger UI), /redoc.
"""
import os
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel

from . import config

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _load(name):
    with open(os.path.join(_STATIC, name), "rb") as f:
        return f.read()


# ---------------------------------------------------------------- request models
class CreateReq(BaseModel):
    name: str = ""
    owner: str = ""
    description: str = ""
    image: str = ""      # optional registry image; "" = server default (config.IMAGE)


class NameReq(BaseModel):
    name: str = ""


class BanReq(BaseModel):
    kind: str = ""
    node: str = ""
    product: str = ""
    uuid: str = ""
    index: Optional[str] = None
    reason: str = ""
    by: str = ""


class BanIdReq(BaseModel):
    id: str = ""
    applied: bool = True


class StageReport(BaseModel):
    instance: str = ""
    stage: str = ""
    event: str = ""     # opened | closing
    ts: float = 0.0     # sender clock, informational only (server time is recorded)


# ---------------------------------------------------------------- app factory
def create_app(instances=None, gpus=None, policy_svc=None, metrics=None, registry=None,
               scenes=None):
    # Lazy imports keep `from app.web import create_app` usable in tests
    # without touching the in-cluster ServiceAccount.
    if policy_svc is None:
        from .policy import PolicyService
        policy_svc = PolicyService()
        try:
            policy_svc.seed_defaults()   # seed permanently-unusable GPU bans (fail-soft)
        except Exception:
            pass
    if instances is None:
        from .instances import InstanceService
        instances = InstanceService(policy_svc=policy_svc)
    if gpus is None:
        from .gpu import GpuService
        gpus = GpuService(policy_svc=policy_svc)
    if metrics is None:
        from .metrics import MetricsService
        metrics = MetricsService()
    if registry is None:
        from .registry import RegistryService
        registry = RegistryService()
    if scenes is None:
        from .scenes import SceneService
        scenes = SceneService(metrics=metrics, instances=instances)

    from . import __version__
    app = FastAPI(title="isaac-ui", version=__version__)

    index = _load("index.html").decode("utf-8") \
        .replace("__NS__", config.NAMESPACE) \
        .replace("__NODES__", ",".join(config.NODES)).encode("utf-8")
    style = _load("style.css")
    script = _load("app.js")

    # ---- static ----
    @app.get("/", response_class=HTMLResponse)
    @app.get("/index.html", response_class=HTMLResponse)
    def root():
        return Response(index, media_type="text/html; charset=utf-8",
                        headers={"Cache-Control": "no-store"})

    @app.get("/style.css")
    def css():
        return Response(style, media_type="text/css; charset=utf-8",
                        headers={"Cache-Control": "no-store"})

    @app.get("/app.js")
    def js():
        return Response(script, media_type="application/javascript; charset=utf-8",
                        headers={"Cache-Control": "no-store"})

    @app.get("/healthz", response_class=PlainTextResponse)
    def healthz():
        return "ok"

    # ---- read API ----
    @app.get("/api/instances")
    def api_instances():
        rows = instances.list()
        instances.reconcile(rows)
        return rows

    @app.get("/api/instance")
    def api_instance(name: str = ""):
        return instances.detail(name)

    @app.get("/api/gpu")
    def api_gpu():
        return gpus.overview()

    @app.get("/api/metrics")
    def api_metrics(window: int = 3600):
        # clamp window to [5m, 24h]; fails soft inside the service
        window = max(300, min(int(window or 3600), 86400))
        return metrics.series(window=window)

    @app.get("/api/metrics/verify")
    def api_metrics_verify():
        # per-pod scrape health + live rates; fails soft inside the service
        return metrics.verify()

    @app.get("/api/metrics/gpu")
    def api_metrics_gpu():
        # DCGM GPU telemetry by model + by instance; fails soft inside the service
        return metrics.gpu()

    @app.get("/api/images")
    def api_images():
        # registry image catalog for the Create modal; fails soft inside the service
        return registry.images()

    @app.get("/api/scenes")
    def api_scenes():
        # scene load history: sessions + per stage x GPU-model aggregates; fail-soft
        return scenes.list()

    @app.get("/api/bans")
    def api_bans():
        bans, ok = policy_svc.list()
        return {"bans": bans, "ok": ok,
                "store": getattr(policy_svc.store, "name", "?")}

    # ---- write API ----
    @app.post("/api/create")
    def api_create(r: CreateReq):
        # image is an allow-list pick: must come from the registry catalog (or "")
        ok, image = registry.validate(r.image)
        if not ok:
            return {"ok": False, "msg": image}
        ok, msg = instances.create(r.name, r.owner, r.description, image=image)
        return {"ok": ok, "msg": msg}

    @app.post("/api/delete")
    def api_delete(r: NameReq):
        ok, msg = instances.delete(r.name)
        return {"ok": ok, "msg": msg}

    @app.post("/api/prune")
    def api_prune():
        ok, msg = instances.prune()
        return {"ok": ok, "msg": msg}

    @app.post("/api/stage-report")
    def api_stage_report(r: StageReport):
        # called by the instances themselves (stage_report.py inside Isaac Sim)
        ok, msg = scenes.report(r.instance, r.stage, r.event)
        return {"ok": ok, "msg": msg}

    @app.post("/api/ban")
    def api_ban(r: BanReq):
        ok, msg = policy_svc.add(r.kind, r.node, r.product, r.uuid,
                                 r.index, r.reason, r.by)
        return {"ok": ok, "msg": msg}

    @app.post("/api/unban")
    def api_unban(r: BanIdReq):
        ok, msg = policy_svc.remove(r.id)
        return {"ok": ok, "msg": msg}

    @app.post("/api/ban-applied")
    def api_ban_applied(r: BanIdReq):
        ok, msg = policy_svc.set_applied(r.id, r.applied)
        return {"ok": ok, "msg": msg}

    return app


def main():
    print(f"isaac-ui listening on :{config.PORT} (ns={config.NAMESPACE}, nodes={config.NODES})", flush=True)
    uvicorn.run(create_app(), host="0.0.0.0", port=config.PORT, log_level="warning")
