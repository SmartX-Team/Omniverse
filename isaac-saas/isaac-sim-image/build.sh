#!/usr/bin/env bash
# Isaac Sim 6.0 이미지 빌드 (+ 선택: Harbor 푸쉬).
#
#   ./build.sh                # 로컬 빌드만: isaac-sim:6.0
#   PUSH=1 ./build.sh         # 빌드 후 10.38.38.210/dt-saas/isaac-sim:6.0 푸쉬
#
# 전제: NGC 베이스(nvcr.io/nvidia/isaac-sim:6.0.0) pull 가능해야 함
#   docker login nvcr.io  ($oauthtoken / NGC API key)
# Harbor 푸쉬 시: /etc/docker/daemon.json 에 "insecure-registries": ["10.38.38.210"]
set -euo pipefail
cd "$(dirname "$0")"
[ -f build.env ] && { set -a; . ./build.env; set +a; }

IMAGE_NAME="${IMAGE_NAME:-isaac-sim}"
IMAGE_TAG="${IMAGE_TAG:-6.0}"
LOCAL_REF="${IMAGE_NAME}:${IMAGE_TAG}"

docker build \
  --build-arg EXT_REPO_URLS="${EXT_REPO_URLS:-}" \
  --build-arg EXT_SRC_DIR="${EXT_SRC_DIR:-/opt/oos_omniverse_extensions}" \
  --build-arg BUILD_ROS_WS="${BUILD_ROS_WS:-0}" \
  -t "$LOCAL_REF" .

echo "built: $LOCAL_REF"

# --- 선택: Harbor 푸쉬 (클러스터 정책: 모든 이미지 = 내부 Harbor) ---
if [ "${PUSH:-0}" = "1" ]; then
  HARBOR="${HARBOR:-10.38.38.210}"
  PROJECT="${PROJECT:-dt-saas}"
  REF="$HARBOR/$PROJECT/${IMAGE_NAME}:${IMAGE_TAG}"
  DOCKER_CFG="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
  if [ "${FORCE_LOGIN:-0}" = "1" ] || ! grep -q "$HARBOR" "$DOCKER_CFG" 2>/dev/null; then
    docker login "$HARBOR"
  fi
  docker tag "$LOCAL_REF" "$REF"
  docker push "$REF"
  echo
  echo "pushed: $REF"
  echo "k8s 반영: k8s/deployment.yaml ->  - { name: IMAGE, value: \"$REF\" }"
  echo "(실험 스크립트 /opt/experiment/ 기본 내장 — 별도 -exp 오버레이 불필요)"
fi
