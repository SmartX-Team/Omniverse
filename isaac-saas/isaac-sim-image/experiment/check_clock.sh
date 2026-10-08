#!/usr/bin/env bash
# 실험 노드 시계 동기 확인. 노드마다 임시 Pod(sleep)를 띄우고 kubectl exec 로 date 를 읽어
# control1 시계와 비교한다. exec 왕복 지연(~0.1~0.3s)이 포함되므로 |offset| > 1000ms 만 문제로 본다.
# 사용: bash check_clock.sh [node ...]   (기본: l40s rm352-1 rm352-2 sv4000-1 sv4000-2)
set -u
NODES=("$@"); [ ${#NODES[@]} -eq 0 ] && NODES=(l40s rm352-1 rm352-2 sv4000-1 sv4000-2)
NS=oos-sim

for n in "${NODES[@]}"; do
  kubectl -n $NS run clk-$n --restart=Never --image=busybox:1.36 \
    --overrides="{\"spec\":{\"nodeName\":\"$n\",\"tolerations\":[{\"operator\":\"Exists\"}]}}" \
    --command -- sleep 300 >/dev/null 2>&1 &
done; wait
for n in "${NODES[@]}"; do kubectl -n $NS wait --for=condition=Ready pod/clk-$n --timeout=90s >/dev/null 2>&1; done

printf "%-10s %-10s %s\n" node offset_ms verdict
for n in "${NODES[@]}"; do
  t1=$(date +%s%N)
  v=$(kubectl -n $NS exec clk-$n -- date +%s%N 2>/dev/null | tr -d '\r')
  t2=$(date +%s%N)
  case "$v" in *N*|"") v=$(kubectl -n $NS exec clk-$n -- date +%s 2>/dev/null | tr -d '\r'); v="${v}000000000";; esac   # busybox date 는 %N 미지원 → 초 단위
  if [ "$v" != "000000000" ]; then
    mid=$(( (t1 + t2) / 2 ))
    off=$(( (v - mid) / 1000000 ))
    verdict=OK; [ ${off#-} -gt 1000 ] && verdict="DRIFT>1s"
    printf "%-10s %-10d %s\n" "$n" "$off" "$verdict"
  else
    printf "%-10s %-10s %s\n" "$n" "-" "exec failed (pod not ready?)"
  fi
done
for n in "${NODES[@]}"; do kubectl -n $NS delete pod clk-$n --wait=false >/dev/null 2>&1; done
echo "컨테이너 시계 = 노드 커널 시계. busybox 는 초 단위라 ±1000ms 는 측정 오차. 전부 OK 면 동기 문제 없음. 상세: ssh <node> chronyc tracking"
