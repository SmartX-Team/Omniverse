#!/usr/bin/env bash
# Mirror the third-party sidecar images used by Isaac Sim instances into our internal
# Harbor (dt-saas project), so instance pods never depend on Docker Hub / quay at runtime
# (rate-limits, outages) and stay on internal container storage for security.
#
#   [HARBOR=10.38.38.210] [PROJECT=dt-saas] ./mirror-images.sh
#
# Run this ONCE per new sidecar version (and whenever you bump a tag in ui/app/config.py).
# It is idempotent: re-running just re-pushes the same tags.
#
# Prerequisites (same as build.sh):
#   - The Harbor PROJECT must already exist.
#   - The build host's Docker must trust Harbor's TLS (see build.sh header for the
#     insecure-registries note if Harbor is self-signed/HTTP).
set -euo pipefail

HARBOR="${HARBOR:-10.38.38.210}"
PROJECT="${PROJECT:-dt-saas}"
DST="$HARBOR/$PROJECT"

# ------------------------------------------------------------------ image map
# "<public origin>  <harbor repo:tag>"   (keep tags in sync with ui/app/config.py)
#   METRICS_OTEL_IMAGE  -> otel-collector-contrib   (the one that was missing -> ImagePullBackOff)
#   CODE_SERVER_IMAGE   -> code-server              (so the whole instance is internal)
OTEL_TAG="${OTEL_TAG:-0.119.0}"
CODE_SERVER_TAG="${CODE_SERVER_TAG:-latest}"
NODE_EXPORTER_TAG="${NODE_EXPORTER_TAG:-v1.8.2}"   # -> node-exporter:1.8 (NETSTAT_IMAGE)
MIRRORS=(
  "otel/opentelemetry-collector-contrib:${OTEL_TAG}   ${DST}/otel-collector-contrib:${OTEL_TAG}"
  "codercom/code-server:${CODE_SERVER_TAG}            ${DST}/code-server:${CODE_SERVER_TAG}"
  "quay.io/prometheus/node-exporter:${NODE_EXPORTER_TAG}   ${DST}/node-exporter:1.8"
)

# ------------------------------------------------------------------ Harbor login
# Reuse existing credentials if already logged in; only prompt when none exist.
DOCKER_CFG="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
if [ "${FORCE_LOGIN:-0}" = "1" ] || ! grep -q "$HARBOR" "$DOCKER_CFG" 2>/dev/null; then
  docker login "$HARBOR"
else
  echo "using existing Harbor login for $HARBOR (FORCE_LOGIN=1 to re-auth)"
fi

# ------------------------------------------------------------------ mirror loop
for m in "${MIRRORS[@]}"; do
  # shellcheck disable=SC2206
  pair=($m)
  SRC="${pair[0]}"; REF="${pair[1]}"
  echo
  echo "== mirroring $SRC -> $REF =="
  docker pull "$SRC"
  docker tag  "$SRC" "$REF"
  docker push "$REF"
done

echo
echo "done. mirrored to $DST :"
for m in "${MIRRORS[@]}"; do echo "  - ${m##* }"; done
echo
echo "These match the Harbor refs in ui/app/config.py (METRICS_OTEL_IMAGE / CODE_SERVER_IMAGE)."
echo "Note: instance pods pull with the 'regcred' secret (Docker Hub). They reach Harbor"
echo "anonymously only if the dt-saas project is public-pull; if a new instance now shows"
echo "401/UNAUTHORIZED (instead of the old NotFound), add a Harbor pull secret to the"
echo "instance pod (resources.py imagePullSecrets) or make the project pull-public."
