# DRA L40S GPU 밴 격리 테스트

목적: UI 코드 손대기 전, **CEL+DRA가 특정 UUID GPU를 실제로 스케줄에서 빼는지**를 격리 검증.
대상: L40S 노드의 **nvidia-smi 0·1번** = `GPU-812dce01…`(gpu-2) + `GPU-e969de42…`(gpu-3).

- API: `resource.k8s.io/v1` (GA, `exactly:` 블록)
- DeviceClass: `gpu.nvidia.com`
- 이 폴더는 `examples/dra/` (구 `dra-test/`) — **`deploy/k8s/`에 두지 말 것**(ArgoCD 전환 시 `deploy/k8s/`만 동기화 대상). 검증용 예제이며 클러스터에 상시 적용하는 매니페스트가 아님.
- **L40S 한가할 때** 실행: probe는 DRA로, 기존 UI 인스턴스는 device-plugin(`nvidia.com/gpu:1`)으로 같은 노드를 잡아 이중할당 가능.

## 매핑 (preflight 확정본)

```
nvidia-smi idx 0  →  GPU-812dce01…  (DRA gpu-2, minor 2)   ← 밴
nvidia-smi idx 1  →  GPU-e969de42…  (DRA gpu-3, minor 3)   ← 밴
nvidia-smi idx 2  →  GPU-ade2e481…  (DRA gpu-1, minor 1)
nvidia-smi idx 3  →  GPU-c4b4dd19…  (DRA gpu-0, minor 0)
```

## 1) 밴 테스트

```bash
kubectl apply -f l40s-deny01.yaml
kubectl -n oos-sim get pod dra-probe -w        # Running 되면 Ctrl-C
```

할당된 device 확인:

```bash
kubectl get resourceclaims -n oos-sim -o json | python3 -c '
import sys, json
for c in json.load(sys.stdin).get("items",[]):
    al=c.get("status",{}).get("allocation",{}) or {}
    res=(al.get("devices",{}) or {}).get("results",[])
    if not res:
        print(c["metadata"]["name"], "-> (미할당)"); continue
    for d in res:
        print(c["metadata"]["name"], "->", d.get("device"), "pool:", d.get("pool"))
'
```

★ 그라운드 트루스 (파드가 보는 실물 UUID):

```bash
kubectl exec -n oos-sim dra-probe -- nvidia-smi --query-gpu=uuid,name --format=csv,noheader
```

**성공 조건:** UUID가 `812dce01` / `e969de42` **둘 다 아님**.

## 2) 바인딩 확인 (역방향)

```bash
kubectl apply -f l40s-only01.yaml
kubectl exec -n oos-sim dra-probe-bind -- nvidia-smi --query-gpu=uuid --format=csv,noheader
```

**성공 조건:** `812dce01` 또는 `e969de42` 중 하나.

## 3) 정리 / 디버그

```bash
# Pending에서 안 넘어가면
kubectl -n oos-sim describe pod dra-probe | sed -n '/Events/,$p'

kubectl delete pod dra-probe dra-probe-bind -n oos-sim --ignore-not-found
kubectl delete resourceclaimtemplate l40s-deny01 l40s-only01 -n oos-sim --ignore-not-found
```

## 판정

1)에서 밴 두 장이 안 잡히고 + 2)에서 그 두 장에만 잡히면 → CEL UUID 제외가 라이브 집행됨 확정.
→ 다음: UI `resources.py`의 `nvidia.com/gpu:1` 요청을 이 ResourceClaim 경로로 전환.
