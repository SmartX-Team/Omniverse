# Stage open/close reporter. Runs inside Isaac Sim (Kit) via --exec at startup.
# Whenever a USD stage is OPENED or CLOSING, POSTs {instance, stage, event} to the
# isaac-ui in-cluster API (REPORT_URL env, injected by the UI into every instance).
# The UI joins these windows with DCGM GPU metrics to record how heavy each scene
# is per GPU model. Fire-and-forget: failures only warn, never disturb the sim.
# ASCII only. No stage content is touched and nothing is ever saved.
import json
import os
import threading
import time
import urllib.request

import carb
import omni.usd

_URL = os.environ.get("REPORT_URL", "")
_INSTANCE = os.environ.get("INSTANCE_NAME", "") or os.environ.get("HOSTNAME", "")
_SUB = None  # keep the subscription referenced for the app lifetime


def _post(event, stage):
    if not _URL:
        return
    body = json.dumps({"instance": _INSTANCE, "stage": stage or "",
                       "event": event, "ts": time.time()}).encode()

    def go():
        try:
            req = urllib.request.Request(_URL, data=body,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:  # network problems must never affect the sim
            carb.log_warn("[stage-report] post failed: %s" % e)

    threading.Thread(target=go, daemon=True).start()


def _on_event(e):
    try:
        ctx = omni.usd.get_context()
        t = int(e.type)
        if t == int(omni.usd.StageEventType.OPENED):
            _post("opened", ctx.get_stage_url())
        elif t == int(omni.usd.StageEventType.CLOSING):
            _post("closing", ctx.get_stage_url())
    except Exception as e:
        carb.log_warn("[stage-report] handler error: %s" % e)


if _URL:
    _SUB = (omni.usd.get_context().get_stage_event_stream()
            .create_subscription_to_pop(_on_event, name="isaac-ui stage report"))
    carb.log_info("[stage-report] active -> %s (instance=%s)" % (_URL, _INSTANCE))
else:
    carb.log_info("[stage-report] REPORT_URL not set; reporter disabled")
