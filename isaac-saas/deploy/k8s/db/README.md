# isaac-db (PostgreSQL)

isaac-ui의 정책/추적 데이터 종착지. 현재 단계에서 UI는 ConfigMap 스토어로도 동작하므로
**DB 배포는 선택**이지만, tracking(annotation→DB) 전환과 밴/감사 이력 누적 전에 깔아두는 것 권장.

## 배포 (UI와 분리된 이유)
메인 ArgoCD Application(ui/k8s)은 prune+selfHeal — DB가 거기 섞이면 prune 한 번에 데이터 증발.
그래서 이 디렉터리는 ui/k8s 기본 kustomization에 **포함되지 않음**.

```bash
# 1) 비밀번호 시크릿 (Git 금지)
kubectl -n oos-sim create secret generic isaac-db-cred \
  --from-literal=POSTGRES_PASSWORD='<strong-password>'

# 2) 배포
kubectl apply -k k8s/db/
kubectl -n oos-sim rollout status statefulset/isaac-db

# 3) 접속 확인
kubectl -n oos-sim exec -it isaac-db-0 -- psql -U isaacui -d isaacui -c '\l'
```

ArgoCD로 관리하려면 **별도 Application**으로, `prune: false` 필수.

## 스토리지 전제
PVC는 클러스터 기본 StorageClass 사용. 없으면 statefulset.yaml 주석의
local-path-provisioner 설치 후 진행. local-path는 데이터가 노드(l40s) 로컬에
물리적으로 존재 → nodeSelector 제거 금지.

## 스키마 (tracking/policy 전환 시 초안)
```sql
CREATE TABLE bans (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('node','product','gpu')),
  node TEXT, product TEXT, uuid TEXT, idx INT,
  reason TEXT, by_user TEXT, applied BOOL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE instances (
  name TEXT, owner TEXT, description TEXT, created_by TEXT,
  node TEXT, gpu_uuid TEXT, created_at TIMESTAMPTZ, deleted_at TIMESTAMPTZ,
  tracking JSONB);   -- 자유 형식 blob: 지금 annotation 스키마 그대로 수용
```

## AWS 이전
RDS PostgreSQL 생성 → `pg_dump | psql` → 앱 env의 DB 호스트만 교체. 이 매니페스트는 폐기.
