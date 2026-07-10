# isaac-saas — Isaac Sim 셀프서비스 플랫폼

Kubernetes 위에서 NVIDIA Isaac Sim 인스턴스를 셀프서비스로 띄우고 관리하는 플랫폼.
웹 UI(FastAPI)로 인스턴스 생성/삭제, GPU 현황 조회, GPU 밴 정책(node / product / GPU-UUID),
DRA(Dynamic Resource Allocation) 기반 GPU 단위 스케줄링 강제를 제공한다.

```
isaac-saas/
├─ ui/                     셀프서비스 웹 UI (이미지: isaac-ui)
│  ├─ app/                 애플리케이션 패키지 (계층형, 아래 참고)
│  │  └─ static/           index.html, style.css, app.js
│  ├─ Dockerfile           python:3.12-slim + uv, `python -m app`
│  ├─ pyproject.toml       의존성 선언 (fastapi, uvicorn, kubernetes, …)
│  ├─ uv.lock              잠금 파일 — 전체 의존성 트리 버전+해시 고정 (커밋 필수)
│  └─ build.sh             빌드 + Harbor 푸시
│
├─ deploy/                 클러스터 배포물 + 운영 스크립트
│  ├─ k8s/                 선언적 매니페스트 (rbac / deployment / service / kustomization)
│  │  └─ db/               PostgreSQL (별도 배포 — prune 보호, db/README.md 참고)
│  ├─ redeploy.sh          빌드→푸시→재배포 원스텝 (현행 수동 배포 경로)
│  ├─ argocd-application.yaml  ArgoCD Application CR (aspirational — 아직 미적용)
│  ├─ mirror-images.sh     사이드카 이미지 public→Harbor 미러링
│  └─ diag/                diag-cluster.sh, verify-metrics.sh (읽기 전용 진단)
│
├─ isaac-sim-image/        Isaac Sim 컨테이너 이미지 빌드 (버전은 build.env에서 관리)
│  └─ experiment/          이미지에 내장되는 실험 스크립트 (/opt/experiment/)
│
├─ examples/
│  └─ dra/                 DRA CEL UUID 밴 격리 검증 예제 (상시 적용 아님)
│
└─ docs/                   METRICS.md, PROMETHEUS-INTEGRATION-DESIGN.md
```

### 코드 구조 (단일 컨테이너, 계층형 모듈)

의존 방향: `config → k8s → policy/resources/tracking → instances/gpu → web`

- 각 계층은 위 계층에만 의존 → 한 계층을 갈아끼워도 나머지는 그대로.
- **web**: FastAPI app factory (`create_app()`) — 서비스 주입식이라 TestClient로 클러스터 밖
  테스트 가능. 자동 API 문서: `/docs`.
- **tracking(annotation) → PostgreSQL** 교체: `tracking.py`만 수정 (`deploy/k8s/db/` 참고).
- 서비스는 `K8sClient`를 주입받음 → Fake 클라이언트로 단위테스트 용이.
- 의존성 정책: 선언은 `pyproject.toml`, 고정은 `uv.lock`. 빌드는 `uv sync --frozen` —
  lockfile과 어긋나면 빌드 자체가 실패해 버전 드리프트가 구조적으로 불가능.
  - 의존성 추가: `uv add <pkg>` (pyproject + lock 동시 갱신, 둘 다 커밋)
  - 업그레이드: `uv lock --upgrade-package <pkg>` → 테스트 → 커밋
  - 로컬 개발: `ui/`에서 `uv sync` 후 `uv run python -m app`

---

## 사전 준비 (1회)

1) **Harbor 프로젝트 생성** — 레지스트리 웹 UI에서 프로젝트 `dt-saas` 생성.

2) **노드 신뢰 설정** — 클러스터 노드의 컨테이너 런타임이 Harbor를 신뢰해야 이미지를 pull 함.
   self-signed/HTTP면 노드에서 ImagePullBackOff 발생.
   - 빌드 호스트 Docker: `/etc/docker/daemon.json`에 `{"insecure-registries":["<HARBOR>"]}` 후 재시작.
   - 클러스터 노드(containerd): registry 신뢰/insecure 설정 (관리자 작업).

3) **Harbor pull secret** (Git에 넣지 말 것):
```bash
kubectl -n <NS> create secret docker-registry harbor-regcred \
  --docker-server=<HARBOR> --docker-username=<USER> --docker-password='****'
```

---

## ① 이미지 빌드 → Harbor 푸시
```bash
cd ui
TAG=0.15.0 ./build.sh      # 로그인 → build → push
# 결과 ref: <HARBOR>/dt-saas/isaac-ui:0.15.0
```
- 푸시한 ref를 `deploy/k8s/deployment.yaml`의 `image:`와 일치시킬 것.

## ② 배포 (현행: 수동)
```bash
kubectl apply -k deploy/k8s/                # rbac + deploy + svc 한 번에
kubectl -n <NS> rollout status deploy/isaac-ui
kubectl -n <NS> get svc isaac-ui            # EXTERNAL-IP 확인 → http://<IP>
```
또는 원스텝: `TAG=<버전> ./deploy/redeploy.sh` (sanity check → build → push → 재배포 → verify).

- 안 뜨면: `kubectl -n <NS> describe pod -l app=isaac-ui | sed -n '/Events/,$p'`
  - `ImagePullBackOff` → 사전준비 2)·3) (노드 신뢰 / pull secret) 확인.

## ③ ArgoCD 자동 배포로 전환 (목표 상태 — 아직 미적용)
1) 이 폴더를 Git에 커밋·푸시.
2) `deploy/argocd-application.yaml`의 `repoURL`/`path` 확인.
3) 적용: `kubectl apply -f deploy/argocd-application.yaml`

→ ArgoCD가 `isaac-saas/deploy/k8s`를 감시하며 자동 동기화(prune·selfHeal).
이후 **수동 `kubectl apply` 금지** (Git이 단일 진실).

## 코드 수정 후 릴리즈 루프
1. `ui/app/` 코드 수정 + `ui/app/__init__.py` 버전 범프.
2. `deploy/k8s/deployment.yaml`의 `image:` 태그를 같은 버전으로 변경.
3. `TAG=<버전> ./deploy/redeploy.sh` — 태그 불일치 시 sanity check에서 중단됨.
   (`latest` 태그는 비권장 — 항상 명시 태그)

---

## GPU 밴 시스템

UI 우상단 **GPU bans** 버튼에서 관리. 세 단위:

| kind | 대상 | 강제 수준 |
|---|---|---|
| `node` | 노드 전체 | **완전** — 신규 인스턴스 nodeAffinity에서 제외 |
| `product` | GPU 제품군 (예: `A100`) | **완전** — DRA CEL `productName` 매칭으로 GPU 단위 제외 (혼합 노드에서 나머지 GPU는 생존), DRA 꺼짐 시 노드 라벨 폴백 |
| `gpu` | 특정 노드의 GPU 1장 (UUID) | **완전(DRA)** — ResourceClaimTemplate CEL deny-list로 스케줄 타임 강제 |

밴된 GPU는 현황 카드에 밴 마커로 표시되고 launchable 계산에서 빠짐.
(`GPU_BAN_AS_USED=1`로 구식 "점유 중" 표시 모드 선택 가능 — 기본 0)

**저장소**: 기본은 네임스페이스 ConfigMap `isaac-ui-policy` (추가 인프라 불필요).
장기 저장소는 **PostgreSQL** — 매니페스트·스키마 초안은 `deploy/k8s/db/README.md` 참고.
주의: env(`DEFAULT_GPU_BANS`)에서 밴을 빼도 ConfigMap에 이미 시드된 밴은 남는다 —
UI에서 remove 필요.

API: `GET /api/bans`, `POST /api/ban` `{kind,node,product,uuid,index,reason,by}`,
`POST /api/unban` `{id}`, `POST /api/ban-applied` `{id,applied}`.

---

## DRA 기반 GPU 스케줄링 강제

인스턴스는 GPU를 **DRA ResourceClaim**으로 요청하고, UUID/product 밴은 그 클레임의
**CEL 셀렉터**로 스케줄 타임에 실집행된다.

- 생성 시 per-instance `ResourceClaimTemplate`(`dt-sim-<name>-gpu`)을 만들고
  `policy.banned_gpu_uuids()`의 UUID + `INSTANCE_DENY_PRODUCTS`의 제품군을 CEL로 제외
  → Deployment 파드가 이 클레임을 참조 (`nvidia.com/gpu` 요청 제거).
- 삭제 시 RCT도 함께 정리. node 밴은 기존대로 nodeAffinity로 처리.
- GPU 현황 used/free는 device-plugin 파드 + DRA ResourceClaim 할당을 합산.
- `policy.node_gpu_devices()`가 ResourceSlice에서 노드별 (uuid, product) 목록을 읽어
  eligible_nodes / gpu overview를 GPU 단위로 계산.

전제: K8s ≥ 1.34 (DRA GA) + NVIDIA DRA driver (k8s-dra-driver-gpu),
DeviceClass `gpu.nvidia.com`, API `resource.k8s.io/v1`.

**주의: `DRA_ENABLED=0`으로 끄면 UUID/product 밴이 표시 전용으로 격하**되어 밴된 GPU에
인스턴스가 앉을 수 있다. 격리 검증 예제는 `examples/dra/` 참고.

RBAC: `resourceclaimtemplates`(ns: get/list/create/delete),
`resourceclaims`/`resourceslices`(cluster: get/list) — `deploy/k8s/rbac.yaml`.

---

## 메트릭 / 관측

- 인스턴스별 DCGM + OTel 사이드카 구성 — 설계는 `docs/PROMETHEUS-INTEGRATION-DESIGN.md`,
  지표 정의는 `docs/METRICS.md`.
- 사이드카 이미지는 `deploy/mirror-images.sh`로 public → Harbor 미러링
  (태그는 `ui/app/config.py`와 동기 유지).
- 검증: `deploy/diag/verify-metrics.sh` (읽기 전용).
