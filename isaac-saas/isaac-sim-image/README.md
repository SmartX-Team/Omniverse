# Isaac Sim 6.0 Container (dt-saas)

`~/Downloads/docker-isaac`(5.1 세트)의 **6.0 업데이트판**. 연구실 Omniverse Extension 자동 등록 + Nucleus 연결 + 시작 USD 자동 로드는 그대로, 베이스만 `nvcr.io/nvidia/isaac-sim:6.0.0`.
**ROS 2 = Jazzy** (6.0 베이스도 Ubuntu 24.04 Noble — 브리지 `system_default`가 Jazzy 자동 로드. 공식 지원: Humble/22.04, Jazzy/24.04, Jazzy 권장).

> 설정은 **`build.env`(빌드)** / **`run.env`(실행)**. `run.env`는 `cp run.env.example run.env` 후 채움 (비밀번호 포함 → 커밋 금지).

---

## 5.1 → 6.0 바뀐 것 (이 세트에 반영됨)

| 항목 | 5.1 | 6.0 | 반영 |
|---|---|---|---|
| 베이스 이미지 | `nvcr.io/nvidia/isaac-sim:5.1.0` | `nvcr.io/nvidia/isaac-sim:6.0.0` (multi-arch, Python 3.12) | Dockerfile |
| 컨테이너 사용자 | root 시작 아님(USER root로 전환) | **rootless(uid 1234, HOME=/isaac-sim)** | 빌드는 root, 실행도 root 유지(`OMNI_KIT_ALLOW_ROOT=1`). entrypoint가 `$HOME` 기준 경로를 써서 rootless(`-u 1234:1234`)로도 동작 |
| WebRTC 런처 | `isaac-sim.streaming.sh` | **`runheadless.sh` = native livestream** | entrypoint가 자동 감지(구 스크립트 있으면 우선). k8s UI가 구 경로로 호출해도 자동 매핑 |
| 스트리밍 env | 없음 (`--/app/livestream/publicEndpointAddress=` 플래그) | `ISAACSIM_HOST` / `ISAACSIM_SIGNAL_PORT`(49100 TCP) / `ISAACSIM_STREAM_PORT`(47998 UDP) | run.env에 추가. 구 플래그도 6.0에서 여전히 동작하므로 k8s UI(`PUBLIC_ADDR_FLAG`)는 그대로 사용 가능 |
| 설정/캐시 경로 | `/root/...` 하드코딩 | `$HOME` 기준 (rootless면 `/isaac-sim/.cache` 등) | entrypoint `$HOME` 파라미터화, run.sh 캐시는 `~/docker/isaac-sim6`(5.1 캐시와 분리 — 구버전 캐시 잔재가 크래시 유발) |
| 실험 스크립트 | 별도 오버레이(`research/image/` → `5.1-exp1` 재푸쉬) | **기본 내장** `/opt/experiment/{wander.py,set_4k.py}` | Dockerfile COPY — `-exp` 오버레이 단계 불필요 |
| 이미지명 | `oos-isaac-sim` | `isaac-sim` (회사명 제거 정책) | build.env |

## 빌드 & 실행

```bash
# 0) NGC 베이스 pull 인증 (최초 1회): docker login nvcr.io  ($oauthtoken / NGC API key)
# 1) build.env 확인 → 빌드 (Windows: .\build.ps1)
./build.sh                 # 로컬: isaac-sim:6.0
PUSH=1 ./build.sh          # + Harbor 푸쉬: 10.38.38.210/dt-saas/isaac-sim:6.0
# 2) 단독 실행 (Windows: .\run.ps1)
cp run.env.example run.env   # 값 채우기
./run.sh
```

원격 스트리밍 접속: `run.env`에 `ISAACSIM_HOST=<호스트IP>` 설정 후 WebRTC Streaming Client에서 해당 IP 입력. 방화벽: 49100/TCP, 47998/UDP.

## k8s(isaac-ui) 연계 — 확인/주의사항

- 클러스터 반영: `PUSH=1 ./build.sh` 후 `k8s/deployment.yaml`의 `IMAGE`를 `10.38.38.210/dt-saas/isaac-sim:6.0`으로 변경 → control1 반영 → 재배포.
- isaac-ui의 `STREAM_CMD`(`/isaac-sim/isaac-sim.streaming.sh`)는 **바꾸지 않아도 됨** — 이 이미지의 entrypoint가 구 경로를 6.0 런처로 자동 매핑. 단, 첫 배포 후 인스턴스 로그에서 `legacy launcher ... -> using /isaac-sim/runheadless.sh` 줄과 `Isaac Sim Full Streaming App is loaded.` 확인할 것.
- **측정 주의(KCI)**: 6.0에서 스트림 프로파일(해상도/코덱 기본값)이 5.1과 다를 수 있음 → 기존 5.1 측정치와 섞지 말고, 6.0 전환 후 N=1 기준 런부터 다시 확인.
- 이미지 내부 검증: `docker run --rm --entrypoint bash isaac-sim:6.0 -c "ls /isaac-sim/*.sh /opt/experiment/"`

## 설정 요약 (5.1과 동일한 사용법)

| 하고 싶은 것 | 파일 | 설정 |
|---|---|---|
| 확장 빌드에 포함 | `build.env` | `EXT_REPO_URLS="https://.../repo.git"` (공백 구분 다중) |
| 확장 로컬 마운트 | `build.env`+`run.env` | `EXT_REPO_URLS=""` + `EXT_LOCAL_PATH=/host/path/...` |
| 자동 탐색 접두사 | `run.env` | `EXT_PREFIX=[ext]` (비우면 전부) |
| Nucleus | `run.env` | `OMNI_SERVER` / `OMNI_USER` / `OMNI_PASS` |
| 시작 Scene USD | `run.env` | `STARTUP_USD_STAGE=omniverse://.../scene.usd` |
| 실행 모드 | `run.env` | `START_GUI` / `START_WEBRTC` (둘 다 false = headless) |
| GPU 선택/우회 | `run.env` | `GPU_DEVICE=0`, `GPU_MODE=device` (no-cgroups 호스트) |
