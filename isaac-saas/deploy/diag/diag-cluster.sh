#!/usr/bin/env bash
# isaac-ui LB / MetalLB / cluster reachability diagnostic.
# READ-ONLY: kubectl get/describe/logs + local ip/ss/curl/arping. Run ON control1.
#   [NS=oos-sim] [SVC=isaac-ui] [MLB_NS=metallb-system] ./diag-cluster.sh
# Paste the whole output back. Nothing here mutates the cluster.
set -o pipefail
NS="${NS:-oos-sim}"; SVC="${SVC:-isaac-ui}"; MLB_NS="${MLB_NS:-metallb-system}"
h(){ printf '\n\033[1;36m===== %s =====\033[0m\n' "$*"; }
have(){ command -v "$1" >/dev/null 2>&1; }

h "0) context / kube reachability"
kubectl config current-context 2>/dev/null || echo "  (no context)"
kubectl get --raw='/readyz' 2>/dev/null && echo "  apiserver readyz OK" || echo "  apiserver NOT ready"

h "1) UI Service - type / LB IP / ports / externalTrafficPolicy"
kubectl -n "$NS" get svc "$SVC" -o wide
kubectl -n "$NS" get svc "$SVC" -o jsonpath='  type={.spec.type} extPolicy={.spec.externalTrafficPolicy} lbIP={.status.loadBalancer.ingress[0].ip} ports={range .spec.ports[*]}{.port}->{.nodePort}/{.protocol} {end}{"\n"}' 2>/dev/null
echo "--- describe events (MetalLB IP assignment / errors) ---"
kubectl -n "$NS" describe svc "$SVC" 2>/dev/null | sed -n '/Events/,$p'

h "2) UI endpoints (backend 'listener' wired to the pod?)"
kubectl -n "$NS" get endpoints "$SVC" -o wide 2>/dev/null
kubectl -n "$NS" get endpointslices -l "kubernetes.io/service-name=$SVC" -o wide 2>/dev/null
echo "--- UI pod placement (which node) ---"
kubectl -n "$NS" get pods -l app="$SVC" -o wide 2>/dev/null

h "3) ALL LoadBalancer services (IP pool usage / collisions)"
kubectl get svc -A -o wide 2>/dev/null | awk 'NR==1 || /LoadBalancer/'

h "4) MetalLB pods (controller assigns IP, speakers announce L2)"
kubectl -n "$MLB_NS" get pods -o wide 2>/dev/null || { echo "  ns '$MLB_NS' not found. Try:"; kubectl get ns 2>/dev/null | grep -i metal; }

h "5) MetalLB config - CRDs (new) or configmap (legacy)"
kubectl get ipaddresspools -A -o yaml 2>/dev/null | grep -iE 'name:|addresses:|^\s+- [0-9]' | sed 's/^/  /'
echo "--- L2Advertisements / BGP ---"
kubectl get l2advertisements -A 2>/dev/null
kubectl get bgppeers,bgpadvertisements -A 2>/dev/null
echo "--- legacy configmap (if used) ---"
kubectl -n "$MLB_NS" get configmap config -o jsonpath='{.data.config}' 2>/dev/null | sed 's/^/  /'

h "6) WHICH NODE announces the LB IP (L2 leader) - speaker logs"
LBIP=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
echo "  LB IP = ${LBIP:-<none>}"
for p in $(kubectl -n "$MLB_NS" get pods -o name 2>/dev/null | grep -i speaker); do
  echo "--- $p ---"
  kubectl -n "$MLB_NS" logs "$p" --tail=300 2>/dev/null \
    | grep -iE "${LBIP:-NO_IP}|announc|assigned|serviceannounced|leader|error|failed" | tail -12
done

h "7) reachability FROM control1 (baseline: this host CAN reach it)"
echo "--- route + ARP owner of $LBIP ---"
ip route get "${LBIP:-0.0.0.0}" 2>/dev/null
ip neigh show "$LBIP" 2>/dev/null
if have arping; then (sudo arping -c2 -w2 "$LBIP" 2>/dev/null || arping -c2 "$LBIP" 2>/dev/null) || echo "  (arping blocked/none)"; fi
echo "--- direct HTTP (expect 200) ---"
curl -sS -o /dev/null -w "  healthz http=%{http_code} time=%{time_total}s remote=%{remote_ip}\n" --max-time 5 "http://$LBIP/healthz" || echo "  curl FAILED from control1"
echo "--- nodePort listener on this host (if control1 is a worker) ---"
NP=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)
if have ss; then sudo ss -ltnp 2>/dev/null | grep ":${NP:-99999} " || echo "  nodePort ${NP} not on control1 (pod runs elsewhere - normal)"; fi

h "8) node + CNI + broken pods"
kubectl get nodes -o wide 2>/dev/null
echo "--- host subnets on control1 (which L2 is it on?) ---"
ip -brief addr 2>/dev/null | grep -vE 'lo|cni|cali|cilium|veth|flannel|@' | sed 's/^/  /'
echo "--- non-Running pods cluster-wide ---"
kubectl get pods -A 2>/dev/null | awk 'NR>1 && $4!="Running" && $4!="Completed"'
echo "--- Cilium ---"
kubectl -n kube-system get pods 2>/dev/null | grep -i cilium | sed 's/^/  /'

h "9) SSH TCP forwarding (why 'ssh -L 8080:$LBIP:80' tunnel may fail)"
if have sshd; then sudo sshd -T 2>/dev/null | grep -iE 'allowtcpforwarding|allowstreamlocal|permitopen|gatewayports' | sed 's/^/  /' \
  || echo "  (need sudo for sshd -T; else check /etc/ssh/sshd_config)"; fi
grep -iE '^\s*(AllowTcpForwarding|PermitOpen|GatewayPorts)' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | sed 's/^/  cfg: /'

h "READ ME"
cat <<'NOTE'
  §1 lbIP present? extPolicy=Local means only the pod's node ARP-answers.
  §2 endpoints NON-empty (a listener backend exists).
  §5 does the pool actually contain 10.38.38.202? (IP outside pool = dead LB IP)
  §6 which NODE announces it - your browser must share that node's L2 broadcast domain.
  §7 http=200 from control1 = server fine; issue is purely path FROM your laptop.
  §8 which subnet control1 sits on vs your laptop (MetalLB L2 does NOT cross subnets).
  §9 AllowTcpForwarding must be 'yes' or 'ssh -L' tunnels silently fail (hardening sets 'no').
NOTE
