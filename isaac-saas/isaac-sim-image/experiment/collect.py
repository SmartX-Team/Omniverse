#!/usr/bin/env python3
"""collect.py — E4 중앙 취합 스크립트 (control1 또는 kubectl 되는 곳에서 실행, 표준 라이브러리만 사용)

흐름
  1. kubectl 로 dt-sim 인스턴스 Pod 목록 → 각 Pod의 isaac-sim 로그에서 wander.py META(JSON) 라인 추출
     (START/END epoch, GPU UUID, 완결된 15분 창 목록)
  2. Prometheus query_range 로 세션 x 창 별 지표 추출
       네트워크(app 라벨): Tx/Rx Mbps 평균·p95, 드롭·오류·TCP 재전송(증분)
       GPU(UUID 라벨):     util 평균·SD·최대, NVENC 평균·최대, VRAM 최대, modelName
  3. 저장: raw_N{n}.csv (세션x창), summary_N{n}.csv (세션수 x GPU모델 층화: 평균±SD, n), meta_N{n}.json, README_N{n}.md

사용
  kubectl -n monitoring port-forward svc/prometheus-server 9090:80 &      # 호스트에서 ClusterIP 직접 안 닿을 때
  python3 collect.py --n 8 --prom http://localhost:9090 --out ./e4_results
  # META 없이(로그 유실 등) 수동 창 지정:  --start 1791250000  (창 = start+120 + 900*i, 4개)
"""
import argparse, csv, datetime, json, os, statistics, subprocess, sys, urllib.parse, urllib.request

WARMUP, WIN, NWIN = 120, 900, 4
KST = datetime.timezone(datetime.timedelta(hours=9))


# ------------------------------------------------------------------ kubectl
def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def pods(ns, label):
    j = json.loads(sh(f"kubectl -n {ns} get pods -l {label} -o json") or '{"items":[]}')
    out = []
    for p in j["items"]:
        app = p["metadata"]["labels"].get("app", "")
        out.append({"pod": p["metadata"]["name"], "app": app,
                    "instance": app.replace("dt-sim-", ""),
                    "node": p["spec"].get("nodeName", ""),
                    "phase": p["status"].get("phase", "")})
    return out


def meta_from_log(ns, pod, container="isaac-sim", run_id=None):
    """마지막 META(또는 run_id 일치하는 META). v6 에이전트는 run 마다 META 를 남기므로 run_id 로 고른다."""
    log = sh(f"kubectl -n {ns} logs {pod} -c {container} --tail=20000")
    metas = []
    for l in log.splitlines():
        if "[wander]" in l and " META {" in l:
            try:
                metas.append(json.loads(l.split("META ", 1)[1]))
            except Exception:
                pass
    if run_id:
        metas = [m for m in metas if m.get("run_id") == run_id]
    return metas[-1] if metas else None


# ------------------------------------------------------------------ prometheus
class Prom:
    def __init__(self, base):
        self.base = base.rstrip("/")

    def _get(self, path, params):
        url = f"{self.base}{path}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=30) as r:
            d = json.loads(r.read().decode())
        if d.get("status") != "success":
            raise RuntimeError(d.get("error"))
        return d["data"]["result"]

    def range(self, q, s, e, step):
        return self._get("/api/v1/query_range", {"query": q, "start": s, "end": e, "step": step})

    def instant(self, q, at):
        return self._get("/api/v1/query", {"query": q, "time": at})

    def series_values(self, q, s, e, step):
        """모든 시리즈 값을 하나의 리스트로 (단일 시리즈 가정; 여럿이면 합쳐짐)."""
        vals = []
        for ser in self.range(q, s, e, step):
            vals += [float(v) for _, v in ser.get("values", [])]
        return vals

    def scalar(self, q, at):
        r = self.instant(q, at)
        return float(r[0]["value"][1]) if r else float("nan")

    def node_label(self, node_name):
        """k8s nodeName -> node-exporter `node` 라벨값 (정확 일치 → 접두 일치 → 원값)."""
        if not hasattr(self, "_nodes"):
            try:
                self._nodes = json.loads(urllib.request.urlopen(
                    f"{self.base}/api/v1/label/node/values", timeout=30).read().decode())["data"]
            except Exception:
                self._nodes = []
        if node_name in self._nodes:
            return node_name
        for v in self._nodes:
            if v.startswith(node_name) or node_name.startswith(v):
                return v
        return node_name

    def label(self, q, at, name):
        r = self.instant(q, at)
        return r[0]["metric"].get(name, "") if r else ""


def stats(v):
    if not v:
        return float("nan"), float("nan"), float("nan"), float("nan")
    v2 = sorted(v)
    p95 = v2[min(len(v2) - 1, int(0.95 * (len(v2) - 1)))]
    sd = statistics.pstdev(v) if len(v) > 1 else 0.0
    return statistics.fmean(v), sd, max(v), p95


# ------------------------------------------------------------------ per window
def window_row(prom, sess, win_i, ws, we):
    app, uuid = sess["app"], sess["uuid"]
    r = {"instance": sess["instance"], "pod": sess["pod"], "node": sess["node"],
         "uuid": uuid, "model": "", "win": win_i, "start": ws, "end": we,
         "start_kst": datetime.datetime.fromtimestamp(ws, KST).strftime("%m-%d %H:%M")}
    # --- network (OTel hostmetrics, app label) ---
    for d, key in (("transmit", "tx"), ("receive", "rx")):
        q = (f'sum(rate(system_network_io_bytes_total{{app="{app}",direction="{d}",device!="lo"}}[3m]))*8/1e6')
        m, sd, mx, p95 = stats(prom.series_values(q, ws, we, 15))
        r[f"{key}_mbps_mean"], r[f"{key}_mbps_sd"], r[f"{key}_mbps_p95"] = m, sd, p95
    for metric, key in (("system_network_dropped_total", "drops"), ("system_network_errors_total", "errors")):
        r[key] = prom.scalar(f'sum(increase({metric}{{app="{app}"}}[{WIN}s]))', we)
    # TCP 재전송 (node-exporter → OTel 재노출; 메트릭명이 다르면 NaN)
    r["tcp_retrans"] = prom.scalar(f'sum(increase(node_netstat_Tcp_RetransSegs{{app="{app}"}}[{WIN}s]))', we)
    # --- node CPU (monitoring-ns node-exporter, node label = k8s nodeName) ---
    if sess.get("node"):
        nl = prom.node_label(sess["node"])
        q = f'100*(1-avg(rate(node_cpu_seconds_total{{mode="idle",node="{nl}"}}[2m])))'
        m, sd, mx, _ = stats(prom.series_values(q, ws, we, 60))
        r["node_cpu_mean"], r["node_cpu_max"] = m, mx
    # --- GPU (DCGM, UUID label) ---
    if uuid:
        r["model"] = prom.label(f'DCGM_FI_DEV_GPU_UTIL{{UUID="{uuid}"}}', we, "modelName")
        m, sd, mx, _ = stats(prom.series_values(f'max by (UUID) (DCGM_FI_DEV_GPU_UTIL{{UUID="{uuid}"}})', ws, we, 60))
        r["gpu_util_mean"], r["gpu_util_sd"], r["gpu_util_max"] = m, sd, mx
        m, sd, mx, _ = stats(prom.series_values(f'max by (UUID) (DCGM_FI_DEV_ENC_UTIL{{UUID="{uuid}"}})', ws, we, 60))
        r["enc_mean"], r["enc_sd"], r["enc_max"] = m, sd, mx
        fb = prom.series_values(f'max by (UUID) (DCGM_FI_DEV_FB_USED{{UUID="{uuid}"}})', ws, we, 60)
        r["vram_max_gib"] = max(fb) / 1024 if fb else float("nan")
        r["gpu_samples"] = len(fb)
    return r


# ------------------------------------------------------------------ summary
def summarize(rows, n_sessions):
    groups = {}
    for r in rows:
        groups.setdefault(r["model"] or "?", []).append(r)
    out = []
    for model, rs in sorted(groups.items()):
        def ms(key):
            v = [x[key] for x in rs if isinstance(x.get(key), (int, float)) and x[key] == x[key]]  # drop missing/NaN
            return (statistics.fmean(v), statistics.pstdev(v) if len(v) > 1 else 0.0) if v else (float("nan"), 0.0)
        tx, gu, en, vr, nc = ms("tx_mbps_mean"), ms("gpu_util_mean"), ms("enc_mean"), ms("vram_max_gib"), ms("node_cpu_mean")
        out.append({"sessions": n_sessions, "model": model,
                    "n_instances": len({x["instance"] for x in rs}), "n_windows": len(rs),
                    "tx_mbps": f"{tx[0]:.1f} ± {tx[1]:.1f}", "gpu_util": f"{gu[0]:.1f} ± {gu[1]:.1f}",
                    "nvenc": f"{en[0]:.1f} ± {en[1]:.1f}", "vram_max_gib": f"{vr[0]:.1f}",
                    "node_cpu": f"{nc[0]:.1f} ± {nc[1]:.1f}",
                    "drops": sum(x["drops"] for x in rs if x["drops"] == x["drops"]),
                    "errors": sum(x["errors"] for x in rs if x["errors"] == x["errors"]),
                    "tcp_retrans": sum(x["tcp_retrans"] for x in rs if x["tcp_retrans"] == x["tcp_retrans"])})
    return out


def write_csv(path, rows):
    if not rows:
        return
    keys = list(rows[0].keys())
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.3f}" if isinstance(v, float) else v) for k, v in r.items()})


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True, help="동시 세션 수 (라벨용)")
    ap.add_argument("--prom", default=os.environ.get("PROM_URL", "http://localhost:9090"))
    ap.add_argument("--ns", default="oos-sim")
    ap.add_argument("--label", default="group=dt-sim")
    ap.add_argument("--out", default="./e4_results")
    ap.add_argument("--start", type=int, help="META 없을 때 수동 START epoch")
    ap.add_argument("--instances", help="쉼표 구분 인스턴스명 필터 (기본: 라벨 전부)")
    ap.add_argument("--uuid", action="append", default=[], help="META 없을 때 GPU UUID 지정: --uuid scripttest=GPU-xxxx (반복 가능)")
    ap.add_argument("--run-id", help="v6 에이전트 run_id (해당 run 의 META 만 사용, 출력은 out/<run_id>/)")
    a = ap.parse_args()
    if a.run_id:
        a.out = os.path.join(a.out, a.run_id)
    os.makedirs(a.out, exist_ok=True)
    prom = Prom(a.prom)
    uuid_map = dict(x.split("=", 1) for x in a.uuid)
    now = int(datetime.datetime.now().timestamp())

    # 1. 세션 메타
    sessions = []
    for p in pods(a.ns, a.label):
        if a.instances and p["instance"] not in a.instances.split(","):
            continue
        m = meta_from_log(a.ns, p["pod"], run_id=a.run_id)
        if m:
            p.update({"uuid": m.get("uuid", ""), "start": m["start"], "end": m["end"],
                      "complete": m.get("complete"), "windows": m.get("windows") or [],
                      "cond": m.get("cond", {})})
        elif a.start:
            s = a.start + WARMUP
            p.update({"uuid": uuid_map.get(p["instance"], ""), "start": a.start, "end": a.start + WARMUP + WIN * NWIN, "complete": None,
                      "windows": [[s + i * WIN, s + (i + 1) * WIN] for i in range(NWIN)]})
            print(f"[warn] {p['pod']}: META 없음 → --start 기준 창 사용" + ("" if p["uuid"] else ", GPU UUID 미상(--uuid 로 지정 가능)"))
        else:
            print(f"[skip] {p['pod']}: META 없음 (--start 지정 시 포함)"); continue
        if not p["windows"]:
            print(f"[skip] {p['pod']}: 완결 창 없음"); continue
        sessions.append(p)
    if not sessions:
        sys.exit("세션 없음")
    print(f"sessions: {len(sessions)}  (expected --n {a.n})")
    for s in sessions:
        print(f"  {s['instance']:<12} node={s['node']:<10} uuid={s['uuid'][:12]} windows={len(s['windows'])} complete={s['complete']}")

    # 2. 추출
    rows = []
    for s in sessions:
        for i, (ws, we) in enumerate(s["windows"][:NWIN]):
            if we > now - 60:
                print(f"  {s['instance']} win{i} skipped (window not finished)"); continue
            r = window_row(prom, s, i, ws, we)
            r["sessions"] = a.n
            rows.append(r)
            print(f"  {s['instance']} win{i} tx={r['tx_mbps_mean']:.2f} gpu={r.get('gpu_util_mean', float('nan')):.1f} "
                  f"enc={r.get('enc_mean', float('nan')):.1f} model={r['model']}")

    # 3. 저장
    tag = f"N{a.n}"
    write_csv(f"{a.out}/raw_{tag}.csv", rows)
    summ = summarize(rows, a.n)
    write_csv(f"{a.out}/summary_{tag}.csv", summ)
    with open(f"{a.out}/meta_{tag}.json", "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=1)
    with open(f"{a.out}/README_{tag}.md", "w", encoding="utf-8") as f:
        f.write(f"# E4 동시 {a.n}세션{' · ' + a.run_id if a.run_id else ''} — 취합 {datetime.datetime.now(KST):%Y-%m-%d %H:%M} KST\n\n")
        f.write(f"- Prometheus: {a.prom}\n- 창: warmup {WARMUP}s 제외, {WIN}s x {NWIN}\n")
        f.write(f"- 세션: " + ", ".join(f"{s['instance']}({s['node']})" for s in sessions) + "\n")
        conds = {json.dumps(s.get("cond", {}), sort_keys=True) for s in sessions}
        f.write(f"- 조건(META cond, {'동일' if len(conds) == 1 else '세션별 상이!'}): " + " | ".join(sorted(conds)) + "\n\n")
        f.write("| sessions | model | n_inst | n_win | Tx (Mbps) | GPU util (%) | NVENC (%) | VRAM max (GiB) | node CPU (%) | drops | errors | retrans |\n|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in summ:
            f.write(f"| {r['sessions']} | {r['model']} | {r['n_instances']} | {r['n_windows']} | {r['tx_mbps']} | {r['gpu_util']} | {r['nvenc']} | {r['vram_max_gib']} | {r['node_cpu']} | {r['drops']:.0f} | {r['errors']:.0f} | {r['tcp_retrans']:.0f} |\n")
        f.write(f"\n파일: raw_{tag}.csv, summary_{tag}.csv, meta_{tag}.json\n")
    print(f"\nsaved → {a.out}/{{raw,summary,meta,README}}_{tag}.*")
    for r in summ:
        print(f"  {r['sessions']} | {r['model']:<22} n={r['n_instances']} | Tx {r['tx_mbps']} | GPU {r['gpu_util']} | NVENC {r['nvenc']}")


if __name__ == "__main__":
    main()
