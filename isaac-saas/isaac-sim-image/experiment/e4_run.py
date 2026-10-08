#!/usr/bin/env python3
"""e4_run.py (v2) — E4 중앙 통제기. wander.py v6 상주 에이전트들에게 run 을 발행하고 수집·기록한다.

전제: 인스턴스들이 Running, 각 세션 Script Editor 에서 wander.py(v6) 를 exec 한 상태(로그에 READY, IDLE).
사용:
  kubectl -n monitoring port-forward svc/prometheus-server 9090:80 &
  python3 e4_run.py status                                  # 에이전트 상태표
  python3 e4_run.py run --n 3 [--participants a,b,c]        # 단일 run
  python3 e4_run.py plan --plan 1,3,6,8 [--gap-min 3]       # 연속 run (참가자 = 세션 목록 앞에서 N개, --order 로 순서 지정)
  python3 e4_run.py stop                                    # 진행 중 run 중단
  공통: --prom http://localhost:9090 --out ./e4_results --lead-min 3 --minutes 60 --nwin 4 --max-minutes 105 --check-only
산출: out/<run_id>/{raw,summary,meta,README}_N*.* + run.md/run.json
"""
import argparse, datetime, json, os, subprocess, sys, time

NS, LABEL, CM = "oos-sim", "group=dt-sim", "wander-config"
KST = datetime.timezone(datetime.timedelta(hours=9))


def sh(cmd, check=False):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"cmd failed: {cmd}\n{r.stderr}")
    return r.stdout


def now_kst(fmt="%H:%M:%S"):
    return datetime.datetime.now(KST).strftime(fmt)


def pods():
    j = json.loads(sh(f"kubectl -n {NS} get pods -l {LABEL} -o json") or '{"items":[]}')
    return sorted([{"pod": p["metadata"]["name"], "instance": p["metadata"]["labels"].get("app", "").replace("dt-sim-", ""),
                    "node": p["spec"].get("nodeName", ""), "phase": p["status"].get("phase", "")}
                   for p in j["items"] if p["status"].get("phase") == "Running"], key=lambda s: s["instance"])


def wlog(pod, tail=600):
    out = sh(f"kubectl -n {NS} logs {pod} -c isaac-sim --tail={tail} 2>/dev/null")
    return [l for l in out.splitlines() if "[wander]" in l]


def last_json(lines, key):
    for l in reversed(lines):
        if f" {key} {{" in l:
            try:
                return json.loads(l.split(f"{key} ", 1)[1])
            except Exception:
                return None
    return None


def kv(line, key):
    for tok in line.split():
        if tok.startswith(key + "="):
            return tok[len(key) + 1:]
    return None


def agent_state(lines):
    """마지막 상태 이벤트로 에이전트 상태 판정 → (state, run_id, epoch)."""
    for l in reversed(lines):
        for key, st in (("DONE_INCOMPLETE", "IDLE"), ("DONE", "IDLE"), ("ABORTED", "IDLE"), ("START", "RUNNING"),
                        ("ARM", "ARMED"), ("IDLE", "IDLE"), ("SKIP", "IDLE"), ("READY", "IDLE")):
            if f" {key} " in l:
                ep = kv(l, "epoch")
                return st, kv(l, "run_id") or "-", float(ep) if ep else None, key
    return "NO_AGENT", "-", None, "-"


def cm_write(data):
    sh(f"kubectl -n {NS} delete cm {CM} --ignore-not-found")
    lits = " ".join(f'--from-literal={k}="{v}"' for k, v in data.items())
    sh(f"kubectl -n {NS} create cm {CM} {lits}", check=True)


# ------------------------------------------------------------------ commands
def cmd_status(a):
    print(f"{'instance':<14}{'node':<10}{'state':<10}{'last_event':<16}{'run_id':<22}gpu/stage")
    for s in pods():
        lines = wlog(s["pod"])
        st, rid, _, key = agent_state(lines)
        rd = last_json(lines, "READY") or {}
        print(f"{s['instance']:<14}{s['node']:<10}{st:<10}{key:<16}{rid:<22}{rd.get('uuid','')[:12]} {rd.get('stage','').rsplit('/',1)[-1]} {rd.get('renderer_res','')}")


def cmd_stop(a):
    cm_write({"cmd": "stop", "run_id": "stop-" + now_kst("%H%M%S")})
    print("stop 발행. 세션 로그에 ABORTED 확인 후 `status`.")


def one_run(a, n, participants, rec_all):
    rid = f"N{n}_{now_kst('%Y%m%d_%H%M')}"
    ev_lines = []

    def ev(msg):
        line = f"[{now_kst()}] {rid} {msg}"; print(line, flush=True); ev_lines.append(line)

    sess = [s for s in pods() if s["instance"] in participants]
    if len(sess) != n:
        ev(f"ABORT: 참가 세션 {len(sess)} != N {n} (Running 아님?: {set(participants)-{s['instance'] for s in sess}})"); return None
    # 1. 준비/조건 확인
    for s in sess:
        lines = wlog(s["pod"])
        s["ready"] = last_json(lines, "READY")
        s["state"], _, _, _ = agent_state(lines)
    bad = [f"{s['instance']}({s['state']})" for s in sess if not s["ready"] or s["state"] != "IDLE"]
    if bad:
        ev(f"ABORT: READY/IDLE 아님: {bad}"); return None
    keys = ("stage", "renderer_res", "viewport_res")
    conds = {json.dumps({k: s["ready"].get(k) for k in keys}, sort_keys=True) for s in sess}
    for s in sess:
        ev(f"READY {s['instance']:<12} node={s['node']:<9} gpu={s['ready'].get('uuid','')[:12]} "
           f"stage={s['ready'].get('stage','?').rsplit('/',1)[-1]} res={s['ready'].get('renderer_res')}")
    if len(conds) != 1:
        ev(f"ABORT: 조건 불일치 {sorted(conds)}"); return None
    if a.check_only:
        ev("check-only"); return None
    # 2. run 발행
    start_at = (datetime.datetime.now(KST) + datetime.timedelta(minutes=a.lead_min)).replace(second=0, microsecond=0)
    t0 = start_at.timestamp()
    cm_write({"cmd": "run", "run_id": rid, "start_at": start_at.strftime("%Y-%m-%d %H:%M:%S"),
              "minutes": a.minutes, "nwin": a.nwin, "max_minutes": a.max_minutes,
              "participants": ",".join(participants)})
    windows = [[int(t0 + 120 + 900 * i), int(t0 + 120 + 900 * (i + 1))] for i in range(a.nwin)]
    ev(f"RUN start_at={start_at:%H:%M:%S} participants={participants} minutes={a.minutes} nwin={a.nwin}")
    # 3. ARM/START 확인
    starts = {}
    while time.time() < t0 + 90 and len(starts) < n:
        for s in sess:
            if s["instance"] in starts:
                continue
            for l in reversed(wlog(s["pod"], 200)):
                if " START " in l and kv(l, "run_id") == rid:
                    starts[s["instance"]] = float(kv(l, "epoch")); ev(f"START {s['instance']} Δ{starts[s['instance']]-t0:+.1f}s"); break
        time.sleep(5)
    spread = (max(starts.values()) - min(starts.values())) if starts else None
    ev(f"동시성 {len(starts)}/{n} 편차={spread if spread is None else round(spread,1)}s " + ("OK" if spread is not None and spread <= 5 else "WARN"))
    # 4. DONE 대기
    done, hb = {}, 0
    while time.time() < t0 + (a.max_minutes + 10) * 60 and len(done) < n:
        for s in sess:
            if s["instance"] in done:
                continue
            for l in reversed(wlog(s["pod"], 300)):
                if kv(l, "run_id") == rid and (" DONE" in l or " ABORTED " in l):
                    done[s["instance"]] = "ABORTED" if "ABORTED" in l else ("DONE_INCOMPLETE" if "INCOMPLETE" in l else "DONE")
                    ev(f"{done[s['instance']]} {s['instance']}"); break
        if time.time() - hb > 600:
            ev(f"progress {len(done)}/{n} elapsed={int((time.time()-t0)/60)}min"); hb = time.time()
        if len(done) < n:
            time.sleep(30)
    if any(v == "ABORTED" for v in done.values()):
        ev("ABORTED run — 수집 생략"); return None
    # 5. 수집
    time.sleep(60)
    here = os.path.dirname(os.path.abspath(__file__))
    cmd = (f'python3 {os.path.join(here, "collect.py")} --n {n} --prom {a.prom} --out {a.out} '
           f'--run-id {rid} --instances {",".join(participants)}')
    ev(f"collect: {cmd}")
    out = sh(cmd); print(out)
    # 6. 기록
    rec = {"run_id": rid, "n": n, "participants": participants, "start_epoch": int(t0), "windows": windows,
           "start_spread_s": spread, "done": done, "cond": next(iter(conds)),
           "sessions": [{k: s[k] for k in ("instance", "pod", "node")} | {"uuid": s["ready"].get("uuid")} for s in sess],
           "events": ev_lines, "collect_tail": out.strip().splitlines()[-6:]}
    d = os.path.join(a.out, rid); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "run.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    with open(os.path.join(d, "run.md"), "w", encoding="utf-8") as f:
        f.write(f"# {rid} (N={n})\n\n- start: {start_at:%Y-%m-%d %H:%M:%S} KST (epoch {int(t0)})\n- windows: {windows}\n"
                f"- START 편차: {spread}s\n- DONE: {done}\n- 조건: {rec['cond']}\n\n## sessions\n")
        for s in rec["sessions"]:
            f.write(f"- {s['instance']} node={s['node']} uuid={s['uuid']} pod={s['pod']}\n")
        f.write("\n## events\n" + "\n".join(ev_lines) + "\n\n## collect\n```\n" + "\n".join(rec["collect_tail"]) + "\n```\n")
    ev(f"record → {d}/run.md")
    rec_all.append(rec)
    return rec


def cmd_run(a):
    avail = [s["instance"] for s in pods()]
    parts = a.participants.split(",") if a.participants else avail[:a.n]
    one_run(a, a.n, parts, [])
    cm_write({"cmd": "idle", "run_id": "idle"})


def cmd_plan(a):
    avail = [s["instance"] for s in pods()]
    order = a.order.split(",") if a.order else avail
    plan = [int(x) for x in a.plan.split(",")]
    if max(plan) > len(order):
        sys.exit(f"세션 {len(order)}개 < plan 최대 {max(plan)}")
    rec_all = []
    for i, n in enumerate(plan):
        parts = order[:n]
        print(f"\n===== plan {i+1}/{len(plan)}: N={n} participants={parts} =====")
        r = one_run(a, n, parts, rec_all)
        if r is None and not a.check_only:
            print("run 실패 → plan 중단"); break
        if i < len(plan) - 1 and not a.check_only:
            cm_write({"cmd": "idle", "run_id": "idle"})
            print(f"gap {a.gap_min}min ..."); time.sleep(a.gap_min * 60)
    cm_write({"cmd": "idle", "run_id": "idle"})
    if rec_all:
        with open(os.path.join(a.out, f"plan_{now_kst('%Y%m%d_%H%M')}.md"), "w", encoding="utf-8") as f:
            f.write("# E4 plan summary\n\n| run_id | N | 편차(s) | DONE | dir |\n|---|---|---|---|---|\n")
            for r in rec_all:
                f.write(f"| {r['run_id']} | {r['n']} | {r['start_spread_s']} | {sum(1 for v in r['done'].values() if v=='DONE')}/{r['n']} | {a.out}/{r['run_id']} |\n")
        print(f"plan summary → {a.out}/plan_*.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "run", "plan", "stop"])
    ap.add_argument("--n", type=int)
    ap.add_argument("--plan", help="예: 1,3,6,8")
    ap.add_argument("--participants", help="run: 참가 인스턴스 쉼표 (기본: 목록 앞 N개)")
    ap.add_argument("--order", help="plan: 세션 우선순위 쉼표 (앞에서 N개 참가)")
    ap.add_argument("--prom", default="http://localhost:9090")
    ap.add_argument("--out", default="./e4_results")
    ap.add_argument("--lead-min", type=int, default=3)
    ap.add_argument("--gap-min", type=int, default=3)
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--nwin", type=int, default=4)
    ap.add_argument("--max-minutes", type=int, default=105)
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.cmd == "run" and not a.n:
        sys.exit("run 은 --n 필요")
    if a.cmd == "plan" and not a.plan:
        sys.exit("plan 은 --plan 필요")
    {"status": cmd_status, "run": cmd_run, "plan": cmd_plan, "stop": cmd_stop}[a.cmd](a)


if __name__ == "__main__":
    main()
