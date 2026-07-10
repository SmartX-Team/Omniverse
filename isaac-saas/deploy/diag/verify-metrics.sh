#!/usr/bin/env bash
# Verify that per-instance metrics (otel-collector sidecar) are actually reaching the
# cluster Prometheus. READ-ONLY: only `kubectl get` / `kubectl get --raw` (API-server
# proxy). Changes nothing in the cluster.
#
#   [NS=oos-sim] [PROM_NS=monitoring] [PROM_SVC=prometheus-server] [PORT=9100] ./verify-metrics.sh
#
# Pipeline checked, in order:
#   1. instance pods exist and carry the prometheus.io/scrape annotations
#   2. each sidecar actually serves metrics       (pod proxy -> :PORT/metrics)
#   3. Prometheus scrapes them (target up==1)      (PromQL: up{...})
#   4. Prometheus holds the network series         (PromQL: system_network_*)
#
# Scope: the otel hostmetrics:network scraper is INTERFACE-level (eth0/lo) x direction.
# It captures per-pod bandwidth/packets/drops/errors + TCP connection-state counts - enough
# for per-pod network usage. It can NOT split bytes by protocol/port (e.g. WebRTC media UDP
# vs signaling TCP, or RTSP). For protocol/port-level visibility, enable Cilium Hubble
# metrics (this cluster runs Cilium) - see docs/PROMETHEUS-INTEGRATION-DESIGN.md.
set -uo pipefail

NS="${NS:-oos-sim}"
PROM_NS="${PROM_NS:-monitoring}"
PROM_SVC="${PROM_SVC:-prometheus-server}"
PORT="${PORT:-9100}"
GROUP="dt-sim"
PROM="/api/v1/namespaces/${PROM_NS}/services/${PROM_SVC}:80/proxy/api/v1"

say() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
ok()  { printf '  \033[1;32mPASS\033[0m %s\n' "$*"; }
bad() { printf '  \033[1;31mFAIL\033[0m %s\n' "$*"; }

# URL-encode a PromQL expression for use in ?query=
enc() { python3 -c "import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))" "$1"; }
# Run an instant query and print the JSON (status + result) through python for readability.
promq() {
  local expr="$1"
  kubectl get --raw "${PROM}/query?query=$(enc "$expr")" 2>/dev/null
}
# How many series did a query return?
promcount() {
  promq "$1" | python3 -c "import sys,json
try: d=json.load(sys.stdin)
except Exception: print(-1); sys.exit()
print(len(d.get('data',{}).get('result',[])) if d.get('status')=='success' else -1)"
}

# ---------------------------------------------------------------- 0. reachability
say "0) Prometheus reachable (API-server proxy)"
BUILD=$(kubectl get --raw "${PROM}/status/buildinfo" 2>/dev/null || true)
if echo "$BUILD" | grep -q '"status":"success"'; then
  ok "prometheus API reachable at ${PROM_SVC}.${PROM_NS}:80"
else
  bad "cannot reach Prometheus API via service proxy."
  echo "      fallback: kubectl -n ${PROM_NS} port-forward svc/${PROM_SVC} 9090:80"
  echo "                then open http://localhost:9090  (run the PromQL below by hand)"
fi

# ---------------------------------------------------------------- 1. pods + annotations
say "1) instance pods + scrape annotations (ns=${NS})"
PODS=$(kubectl -n "$NS" get pods -l "group=${GROUP}" \
        -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations.prometheus\.io/scrape}{"\t"}{.metadata.annotations.prometheus\.io/port}{"\n"}{end}' 2>/dev/null)
if [ -z "$PODS" ]; then
  bad "no instance pods found (label group=${GROUP}). Create an instance first, then re-run."
  echo "      (steps 2-4 need at least one running instance to verify.)"
else
  printf 'POD\tSCRAPE\tPORT\n%s\n' "$PODS" | column -t
  echo "$PODS" | grep -q $'\ttrue\t' \
    && ok "scrape annotations present" \
    || bad "pods missing prometheus.io/scrape=true (METRICS_ENABLED off? old instance from pre-metrics build?)"
fi
FIRST_POD=$(echo "$PODS" | awk 'NF{print $1; exit}')

# ---------------------------------------------------------------- 2. sidecar serves metrics
say "2) sidecar exposes /metrics (direct pod proxy :${PORT})"
if [ -n "${FIRST_POD:-}" ]; then
  RAW=$(kubectl get --raw "/api/v1/namespaces/${NS}/pods/${FIRST_POD}:${PORT}/proxy/metrics" 2>/dev/null || true)
  N=$(echo "$RAW" | grep -c '^system_network' || true)
  if [ "${N:-0}" -gt 0 ]; then
    ok "${FIRST_POD} sidecar serving ${N} system_network_* metric lines"
    echo "$RAW" | grep '^system_network' | head -4 | sed 's/^/      /'
  else
    bad "${FIRST_POD}:${PORT}/metrics has no system_network_* lines (sidecar not ready / wrong port?)"
  fi
else
  echo "  (skipped - no pod)"
fi

# ---------------------------------------------------------------- 3. Prometheus target up
say "3) Prometheus scrapes the instances (up==1)"
UP=$(promcount "up{namespace=\"${NS}\", app=~\"${GROUP}-.+\"}")
if [ "${UP:-0}" -gt 0 ]; then
  ok "${UP} instance target(s) with up==1"
  promq "up{namespace=\"${NS}\", app=~\"${GROUP}-.+\"}" | python3 -c "import sys,json
d=json.load(sys.stdin)
for r in d['data']['result']:
    m=r['metric']; print('      up=%s  app=%s  pod=%s'%(r['value'][1], m.get('app','?'), m.get('pod','?')))" 2>/dev/null
else
  bad "no instance targets up in Prometheus (scrape not happening yet)."
  echo "      check: kubectl get --raw \"${PROM}/targets\" | grep dt-sim"
  echo "      give it one scrape interval (~15-30s) after the pod is Ready."
fi

# ---------------------------------------------------------------- 4. network series stored
say "4) network metrics stored (system_network_*)"
NET=$(promcount "{__name__=~\"system_network.+\", namespace=\"${NS}\"}")
if [ "${NET:-0}" -gt 0 ]; then
  ok "${NET} system_network_* series in TSDB for ns=${NS}"
  echo "  NOTE: filter device=\"eth0\". device=\"lo\" (loopback) counts in-pod traffic"
  echo "        (code-server <-> isaac) and inflates totals ~5x - exclude it for real usage."
  echo "  per-instance tx/rx bytes rate (REAL external, eth0 only):"
  echo "      sum by (app) (rate(system_network_io_bytes_total{namespace=\"${NS}\",device=\"eth0\"}[5m]))"
  echo "  per-pod transmit only (stream output):"
  echo "      sum by (pod) (rate(system_network_io_bytes_total{namespace=\"${NS}\",device=\"eth0\",direction=\"transmit\"}[5m]))"
  echo "  drop / error rate (quality alarms):"
  echo "      sum by (pod) (rate(system_network_dropped_total{namespace=\"${NS}\",device=\"eth0\"}[5m]))"
  echo "      sum by (pod) (rate(system_network_errors_total {namespace=\"${NS}\",device=\"eth0\"}[5m]))"
  echo "  current sample (per device, so you can SEE eth0 vs lo inflation):"
  promq "sum by (app, device, direction) (system_network_io_bytes_total{namespace=\"${NS}\"})" | python3 -c "import sys,json
d=json.load(sys.stdin)
for r in d['data'].get('result',[])[:12]:
    m=r['metric']; print('      app=%-24s dev=%-5s dir=%-9s bytes=%s'%(m.get('app','?'), m.get('device','?'), m.get('direction','?'), r['value'][1]))" 2>/dev/null
  echo "  (lo ~= 5x eth0 here => always filter device=\"eth0\" for true network usage.)"
else
  bad "no system_network_* series for ns=${NS} (steps 2/3 must pass first)."
fi

say "done"
