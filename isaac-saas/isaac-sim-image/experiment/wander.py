# wander.py (v6) — 상주 에이전트. 세션 내부 부하 + 자기 데이터 완결성 보장. Isaac Sim Script Editor에 붙여넣어 실행.
#  - exec 1회 → READY 로그 → IDLE 루프: ConfigMap oos-sim/wander-config 를 10s 폴링하며 명령 대기
#      data: cmd=run|stop|idle, run_id, start_at(KST 문자열|epoch), minutes, nwin, max_minutes, participants(쉼표, 비면 전원)
#    새 run_id + 참가자 → ARM → start_at 대기 → START/COND → 부하 → 완결성 확인 → DONE/META(run_id 포함) → IDLE 복귀
#    cmd=stop → 진행 중이면 ABORTED 후 IDLE.  비참가자는 SKIP 1회 로그.  ConfigMap 읽기 불가(RBAC) → START_AT/즉시 1회 실행 후 종료
#    중앙은 e4_run.py (plan 1,3,6,8 등 반복 실행·수집·기록)
#  - 카메라 무작위 이동(v1 파라미터 동일: 2-5초, 줌 0.6-1.6)
#  - 10분마다 HEARTBEAT 로그
#  - MINUTES 경과 후 Prometheus에 자기 app(네트워크)·UUID(GPU) 샘플이 15분 창 NWIN개 채워졌는지 확인,
#    미달이면 15분씩 연장(MAX_MINUTES까지) → 완결 시 DONE + META(JSON 1줄) 로그
#  - 측정값은 저장하지 않음(Prometheus가 보유). 중앙 collect.py가 META 라인만 읽어 추출
#  - 모든 외부 호출은 실패해도 경고만. 카메라 이동엔 영향 없음
import asyncio, math, random, time, datetime, json, os, subprocess, urllib.request, urllib.parse, urllib.error
import omni.kit.app, omni.usd, carb.settings
from omni.kit.viewport.utility import get_active_viewport
from omni.kit.viewport.utility.camera_state import ViewportCameraState
from pxr import Gf

# ---------------- 설정 ----------------
START_AT    = ""                      # KST "YYYY-MM-DD HH:MM:SS". 전 세션 동일값으로 수정 후 실행. ""이면 즉시 시작
MINUTES     = 60.0                    # 기본 부하 시간 (15분 x 4)
MAX_MINUTES = 105.0                   # 완결성 미달 시 연장 상한
WARMUP_SEC  = 120                     # 측정 창 시작 전 제외 구간
WIN_SEC     = 900                     # 측정 창 길이 (15분)
NWIN        = 4                       # 필요한 창 개수
PROM        = "http://prometheus-server.monitoring.svc.cluster.local"
NET_MIN     = 12                      # 창당 네트워크 샘플 최소 (Prometheus 1m 스크레이프 → 기대 15)
GPU_MIN     = 12                      # 창당 DCGM 샘플 최소 (1m 수집 → 기대 15)
TAG         = "wander"
CFG_NAME    = "wander-config"         # oos-sim ConfigMap. data: start_at(KST) [, minutes, nwin, max_minutes]
POLL_SEC    = 10                      # IDLE 상태 ConfigMap 폴링 간격
IDLE_HB_SEC = 300                     # IDLE 하트비트 간격
K8S_API     = "https://kubernetes.default.svc"
SA_DIR      = "/var/run/secrets/kubernetes.io/serviceaccount"

KST = datetime.timezone(datetime.timedelta(hours=9))
INSTANCE = os.environ.get("INSTANCE_NAME", "") or os.environ.get("HOSTNAME", "").rsplit("-", 2)[0].replace("dt-sim-", "")
APP      = "dt-sim-" + INSTANCE
POD      = os.environ.get("HOSTNAME", "")

def _now(): return datetime.datetime.now(KST).strftime("%H:%M:%S")
def log(msg): print(f"[{TAG}] {_now()} {msg}", flush=True)

def _conditions():
    """실험 조건 스냅샷(관측만, 변경 없음): 스테이지·렌더러/뷰포트 해상도·인코딩 비트레이트·버전."""
    c = {}
    try:
        c["stage"] = omni.usd.get_context().get_stage_url()
    except Exception: pass
    try:
        st = carb.settings.get_settings()
        c["renderer_res"] = f'{st.get("/app/renderer/resolution/width")}x{st.get("/app/renderer/resolution/height")}'
        c["enc_bitrate"] = st.get("/app/omni.videoencoding/bitrate")
        c["isaac_version"] = st.get("/app/version")
    except Exception: pass
    try:
        c["viewport_res"] = "x".join(str(v) for v in get_active_viewport().resolution)
    except Exception: pass
    return c

def _cfg():
    """ConfigMap data dict. 실패(RBAC 없음/네트워크) 시 None — 호출자가 폴백."""
    try:
        import ssl
        ns = open(f"{SA_DIR}/namespace").read().strip()
        tok = open(f"{SA_DIR}/token").read().strip()
        ctx = ssl.create_default_context(cafile=f"{SA_DIR}/ca.crt")
        req = urllib.request.Request(f"{K8S_API}/api/v1/namespaces/{ns}/configmaps/{CFG_NAME}",
                                     headers={"Authorization": "Bearer " + tok})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            return json.loads(r.read().decode()).get("data", {}) or {}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}          # 아직 안 만들어짐 → 계속 폴링
        log(f"WARN configmap read failed: HTTP {e.code} (RBAC?)"); return None
    except Exception as e:
        log(f"WARN configmap read failed: {e}"); return None

def _clock_offset():
    """local - prometheus server time (s). 세션 간 시계 어긋남 기록용."""
    try:
        with urllib.request.urlopen(f"{PROM}/api/v1/query?query=time()", timeout=5) as r:
            srv = float(json.loads(r.read().decode())["data"]["result"][1])
        return round(time.time() - srv, 3)
    except Exception:
        return None

def _gpu_uuid():
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"], timeout=10)
        return out.decode().strip().splitlines()[0].strip()
    except Exception as e:
        log(f"WARN nvidia-smi failed: {e}"); return ""

def _prom_count(query, at):
    """count_over_time 인스턴트 쿼리 → 결과 중 최대값 (없으면 0). 블로킹(≤5s)."""
    try:
        qs = urllib.parse.urlencode({"query": query, "time": str(int(at))})
        with urllib.request.urlopen(f"{PROM}/api/v1/query?{qs}", timeout=5) as r:
            d = json.loads(r.read().decode())
        vals = [float(x["value"][1]) for x in d.get("data", {}).get("result", [])]
        return max(vals) if vals else 0.0
    except Exception as e:
        log(f"WARN prom query failed: {e}"); return -1.0

def _windows(t0, n):
    s = t0 + WARMUP_SEC
    return [(s + i*WIN_SEC, s + (i+1)*WIN_SEC) for i in range(n)]

async def _check(t0, uuid, n, need=None):
    """창 n개 각각 네트워크·GPU 샘플 수 확인. ok 창이 need(기본 n)개 이상이면 완결. 블로킹 쿼리는 스레드로."""
    need = need or n
    loop = asyncio.get_event_loop()
    qn = f'count_over_time(system_network_io_bytes_total{{app="{APP}",direction="transmit",device!="lo"}}[{WIN_SEC}s])'
    qg = f'count_over_time(DCGM_FI_DEV_GPU_UTIL{{UUID="{uuid}"}}[{WIN_SEC}s])'
    detail, ok = [], True
    for i, (ws, we) in enumerate(_windows(t0, n)):
        at = we + 30  # 스크레이프 지연 여유
        cn = await loop.run_in_executor(None, _prom_count, qn, at)
        cg = await loop.run_in_executor(None, _prom_count, qg, at) if uuid else -1.0
        good = cn >= NET_MIN and (cg >= GPU_MIN or not uuid)
        detail.append({"win": i, "start": int(ws), "end": int(we), "net": cn, "gpu": cg, "ok": good})
        log(f"check win{i} net={cn:.0f}/{NET_MIN} gpu={cg:.0f}/{GPU_MIN} {'OK' if good else 'SHORT'}")
    ok = sum(1 for d in detail if d["ok"]) >= need
    return ok, detail

def _parse_kst(s):
    """'YYYY-MM-DD HH:MM:SS'(KST) 또는 epoch 초. 과거 시각이면 경고 후 즉시 시작."""
    s = s.strip()
    t = float(s) if s.replace(".", "", 1).isdigit() else \
        datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST).timestamp()
    if t < time.time():
        log(f"WARN start_at '{s}' is in the past by {int(time.time()-t)}s -> starting immediately "
            f"(host date in UTC? use TZ=Asia/Seoul or epoch)")
    return t

async def _poll_cmd(last_run_id):
    """IDLE 루프: 새 run 명령(참가 대상)이 올 때까지 대기. (cfg, 'run') / (None,'fallback')."""
    hb = 0
    skipped = set()
    while True:
        cfg = _cfg()
        if cfg is None:
            return None, "fallback"
        rid, cmd = cfg.get("run_id", ""), (cfg.get("cmd") or ("run" if cfg.get("start_at") else "idle")).lower()
        parts = [p.strip() for p in (cfg.get("participants") or "").split(",") if p.strip()]
        if cmd == "run" and rid and rid != last_run_id and cfg.get("start_at"):
            if parts and INSTANCE not in parts:
                if rid not in skipped:
                    log(f"SKIP run_id={rid} (not in participants)"); skipped.add(rid)
            else:
                return cfg, "run"
        if time.time() - hb > IDLE_HB_SEC:
            log(f"IDLE last_run={last_run_id or '-'} cmd={cmd} run_id={rid or '-'}"); hb = time.time()
        await asyncio.sleep(POLL_SEC)

def _stop_requested(rid):
    c = _cfg() or {}
    return (c.get("cmd") or "").lower() == "stop" or (c.get("run_id") and c.get("run_id") != rid and (c.get("cmd") or "").lower() == "run")

async def _wait_stage():
    ctx = omni.usd.get_context()
    while not ctx.get_stage() or not ctx.get_stage_url():
        log("waiting for stage ..."); await asyncio.sleep(5)

async def run():
    await _wait_stage()
    uuid = _gpu_uuid()
    ready = _conditions(); ready.update({"uuid": uuid, "pod": POD, "app": APP, "instance": INSTANCE})
    log("READY " + json.dumps(ready, separators=(",", ":")))   # 중앙(e4_run.py)이 시작 전 조건 동일성 검증
    last_run_id = ""
    while True:
        cfg, src = await _poll_cmd(last_run_id)
        if src == "fallback":                       # ConfigMap 불가 → 1회 실행 후 종료
            cfg = {"run_id": "local", "start_at": START_AT} if START_AT else {"run_id": "local"}
        rid = cfg.get("run_id", "local")
        minutes = float(cfg.get("minutes") or MINUTES); nwin = int(cfg.get("nwin") or NWIN)
        max_minutes = float(cfg.get("max_minutes") or MAX_MINUTES)
        t0 = _parse_kst(cfg["start_at"]) if cfg.get("start_at") else time.time()
        log(f"ARM run_id={rid} source={src} start_epoch={t0:.0f} (in {max(0,int(t0-time.time()))}s) minutes={minutes} nwin={nwin}")
        aborted = False
        while time.time() < t0:
            await asyncio.sleep(min(5.0, t0 - time.time()))
            if _stop_requested(rid):
                aborted = True; break
        if aborted:
            log(f"ABORTED run_id={rid} (stop before start)"); last_run_id = rid; continue
        t0 = max(t0, time.time())
        await _one_run(rid, src, uuid, t0, minutes, nwin, max_minutes)
        last_run_id = rid
        if src == "fallback":
            break

async def _one_run(rid, src, uuid, t0, minutes, nwin_req, max_minutes):
    app = omni.kit.app.get_app()
    cam = ViewportCameraState(viewport=get_active_viewport())
    c = Gf.Vec3d(cam.target_world)
    d0 = (Gf.Vec3d(cam.position_world) - c).GetLength() or 100.0
    cond = _conditions()
    cond["clock_offset_s"] = _clock_offset()
    cond["start_source"] = src
    cond["run_id"] = rid
    log(f"START run_id={rid} instance={INSTANCE} app={APP} pod={POD} uuid={uuid} epoch={t0:.0f}")
    log("COND " + json.dumps(cond, separators=(",", ":")))
    p, g = Gf.Vec3d(cam.position_world), Gf.Vec3d(c)
    def _need_end(k):            # k개 창이 전부 끝나고 스크레이프가 반영될 시각
        return t0 + WARMUP_SEC + k * WIN_SEC + 45
    end = max(t0 + minutes * 60, _need_end(nwin_req))   # minutes 는 하한. 창 4개면 약 62.75분
    hard_end = t0 + max_minutes * 60
    next_hb = t0 + 600
    nwin = nwin_req
    detail, complete = [], False
    next_stop_chk = time.time() + 30
    while True:
        # ---- 이동 루프 (end까지) ----
        while time.time() < end:
            yaw = random.uniform(-math.pi, math.pi)
            pit = math.radians(random.uniform(10, 60))
            d = d0 * random.uniform(0.6, 1.6)
            np_ = c + Gf.Vec3d(d*math.cos(pit)*math.cos(yaw), d*math.cos(pit)*math.sin(yaw), d*math.sin(pit))
            ng = c + Gf.Vec3d(*(random.uniform(-1, 1)*0.15*d0 for _ in range(3)))
            lt, ts, sp, sg = random.uniform(2, 5), time.time(), Gf.Vec3d(p), Gf.Vec3d(g)
            while time.time() - ts < lt and time.time() < end:
                f = (time.time() - ts) / lt; e = f*f*(3-2*f)
                cam.set_position_world(Gf.Lerp(e, sp, np_), True)
                cam.set_target_world(Gf.Lerp(e, sg, ng), True)
                await app.next_update_async()
            p, g = np_, ng
            if time.time() >= next_hb:
                log(f"HEARTBEAT run_id={rid} elapsed={int((time.time()-t0)/60)}min"); next_hb += 600
            if time.time() >= next_stop_chk:
                next_stop_chk = time.time() + 30
                if _stop_requested(rid):
                    log(f"ABORTED run_id={rid} elapsed={int((time.time()-t0)/60)}min"); return
        # ---- 완결성 확인 (모든 창이 끝난 뒤에만) ----
        complete, detail = await _check(t0, uuid, nwin, nwin_req)
        if complete or _need_end(nwin + 1) > hard_end:
            break
        nwin += 1
        end = _need_end(nwin)
        short = [d["win"] for d in detail if not d["ok"]]
        log(f"extend: short windows {short} -> add window {nwin-1}, run until +{int((end-t0)/60)}min")
    meta = {"run_id": rid, "instance": INSTANCE, "app": APP, "pod": POD, "uuid": uuid,
            "start": int(t0), "end": int(time.time()), "complete": complete, "cond": cond,
            "windows": [[w["start"], w["end"]] for w in detail if w["ok"]][:nwin_req],
            "detail": detail}
    log(("DONE" if complete else "DONE_INCOMPLETE") + f" run_id={rid} epoch={time.time():.0f}")
    log("META " + json.dumps(meta, separators=(",", ":")))

try:
    T.cancel()        # 재실행 시 이전 태스크 취소
except NameError:
    pass
T = asyncio.ensure_future(run())
log(f"scheduled instance={INSTANCE}")
