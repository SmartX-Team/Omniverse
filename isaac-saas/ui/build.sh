#!/usr/bin/env bash
# Build the Isaac Sim UI image and push it to Harbor.
#
#   [HARBOR=10.38.38.210] [PROJECT=dt-saas] [NAME=isaac-ui] [TAG=0.1] ./build.sh
#
# Prerequisites:
#   - The Harbor PROJECT must already exist (create it in the Harbor web UI).
#   - The build host's Docker must trust Harbor's TLS. If Harbor uses a
#     self-signed cert or plain HTTP, add it to /etc/docker/daemon.json:
#         { "insecure-registries": ["10.38.38.210"] }
#     then: sudo systemctl restart docker
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HARBOR="${HARBOR:-10.38.38.210}"
PROJECT="${PROJECT:-dt-saas}"
NAME="${NAME:-isaac-ui}"
TAG="${TAG:-0.14.0}"
REF="$HARBOR/$PROJECT/$NAME:$TAG"

# Reuse existing Harbor credentials if already logged in; only prompt when none exist.
# (Stored in ~/.docker/config.json. Set FORCE_LOGIN=1 to re-authenticate explicitly.)
DOCKER_CFG="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
if [ "${FORCE_LOGIN:-0}" = "1" ] || ! grep -q "$HARBOR" "$DOCKER_CFG" 2>/dev/null; then
  docker login "$HARBOR"
else
  echo "using existing Harbor login for $HARBOR (FORCE_LOGIN=1 to re-auth)"
fi

docker build -t "$REF" "$HERE"
docker push "$REF"

echo
echo "pushed: $REF"
echo "-> set this exact ref in ../deploy/k8s/deployment.yaml (spec.template.spec.containers[0].image)"
