# wander.py (v3) — 세션 내부 부하 + 자기 데이터 완결성 보장. Isaac Sim Script Editor에 붙여넣어 실행.
#  - START_AT(KST)까지 대기 후 일제히 시작, 카메라 무작위 이동(v1 파라미터 동일: 2-5초, 줌 0.6-1.6)
#  - 10분마다 HEARTBEAT 로그
#  - MINUTES 경과 후 Prometheus에 자기 app(네트워크)·UUID(GPU) 샘플이 15분 창 NWIN개 채워졌는지 확인,
#    미달이면 15분씩 연장(MAX_MINUTES까지) → 완결 시 DONE + META(JSON 1줄) 로그
#  - 측정값은 저장하지 않음(Prometheus가 보유). 중앙 collect.py가 META 라인만 읽어 추출
#  - 모든 외부 호출은 실패해도 경고만. 카메라 이동엔 영향 없음
import asyncio, math, random, time, datetime, json, os, subprocess, urllib.request, urllib.parse
import omni.kit.app, omni.usd, carb.settings
from omni.kit.viewport.utility import get_active_viewport
from omni.kit.viewport.utility.camera_state import ViewportCameraState
from pxr import Gf

# ---------------- 설정 ----------------
START_AT    = "2026-10-06 14:00:00"   # KST. 전 세션 동일. ""이면 즉시 시작
MINUTES     = 60.0                    # 기본 부하 시간 (15분 x 4)
MAX_MINUTES = 105.0                   # 완결성 미달 시 연장 상한
WARMUP_SEC  = 120                     # 측정 창 시작 전 제외 구간
WIN_SEC     = 900                     # 측정 창 길이 (15분)
NWIN        = 4                       # 필요한 창 개수
PROM        = "http://prometheus-server.monitoring.svc.cluster.local"
NET_MIN     = 12                      # 창당 네트워크 샘플 최소 (Prometheus 1m 스크레이프 → 기대 15)
GPU_MIN     = 12                      # 창당 DCGM 샘플 최소 (1m 수집 → 기대 15)
TAG         = "wander"

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

async def _check(t0, uuid, n):
    """창 n개 각각 네트워크·GPU 샘플 수 확인. (ok, 상세) — 블로킹 쿼리는 스레드로."""
    loop = asyncio.get_event_loop()
    qn = f'count_over_time(system_network_io_bytes_total{{app="{APP}",direction="transmit",device!="lo"}}[{WIN_SEC}s])'
    qg = f'count_over_time(DCGM_FI_DEV_GPU_UTIL{{UUID="{uuid}"}}[{WIN_SEC}s])'
    detail, ok = [], True
    for i, (ws, we) in enumerate(_windows(t0, n)):
        at = we + 30  # 스크레이프 지연 여유
        cn = await loop.run_in_executor(None, _prom_count, qn, at)
        cg = await loop.run_in_executor(None, _prom_count, qg, at) if uuid else -1.0
        good = cn >= NET_MIN and (cg >= GPU_MIN or not uuid)
        ok = ok and good
        detail.append({"win": i, "start": int(ws), "end": int(we), "net": cn, "gpu": cg, "ok": good})
        log(f"check win{i} net={cn:.0f}/{NET_MIN} gpu={cg:.0f}/{GPU_MIN} {'OK' if good else 'SHORT'}")
    return ok, detail

def _start_epoch():
    if not START_AT: return time.time()
    return datetime.datetime.strptime(START_AT, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST).timestamp()

async def _wait_stage():
    ctx = omni.usd.get_context()
    while not ctx.get_stage() or not ctx.get_stage_url():
        log("waiting for stage ..."); await asyncio.sleep(5)

async def run():
    await _wait_stage()
    uuid = _gpu_uuid()
    t0 = _start_epoch()
    if t0 > time.time():
        log(f"armed instance={INSTANCE} uuid={uuid} start={START_AT} (in {int(t0-time.time())}s)")
        while time.time() < t0:
            await asyncio.sleep(min(1.0, t0 - time.time()))
    else:
        t0 = time.time()
    app = omni.kit.app.get_app()
    cam = ViewportCameraState(viewport=get_active_viewport())
    c = Gf.Vec3d(cam.target_world)
    d0 = (Gf.Vec3d(cam.position_world) - c).GetLength() or 100.0
    cond = _conditions()
    log(f"START instance={INSTANCE} app={APP} pod={POD} uuid={uuid} epoch={t0:.0f}")
    log("COND " + json.dumps(cond, separators=(",", ":")))
    p, g = Gf.Vec3d(cam.position_world), Gf.Vec3d(c)
    end = t0 + MINUTES * 60
    hard_end = t0 + MAX_MINUTES * 60
    next_hb = t0 + 600
    nwin = NWIN
    detail, complete = [], False
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
                log(f"HEARTBEAT elapsed={int((time.time()-t0)/60)}min"); next_hb += 600
        # ---- 완결성 확인 ----
        await asyncio.sleep(45)   # 마지막 스크레이프 반영 대기
        complete, detail = await _check(t0, uuid, nwin)
        if complete or time.time() + WIN_SEC > hard_end:
            break
        log(f"extend +{WIN_SEC//60}min (windows so far {nwin})")
        nwin += 1
        end = min(end + WIN_SEC, hard_end)
    meta = {"instance": INSTANCE, "app": APP, "pod": POD, "uuid": uuid,
            "start": int(t0), "end": int(time.time()), "complete": complete, "cond": cond,
            "windows": [[w["start"], w["end"]] for w in detail if w["ok"]][:NWIN],
            "detail": detail}
    log(("DONE" if complete else "DONE_INCOMPLETE") + f" epoch={time.time():.0f}")
    log("META " + json.dumps(meta, separators=(",", ":")))

try:
    T.cancel()        # 재실행 시 이전 태스크 취소
except NameError:
    pass
T = asyncio.ensure_future(run())
log(f"scheduled instance={INSTANCE}")
