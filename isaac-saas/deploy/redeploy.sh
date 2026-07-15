#!/usr/bin/env bash
# Build + push the isaac-ui image, then redeploy it to the cluster (manual / pre-ArgoCD).
#
#   [TAG=0.9.4] [NS=oos-sim] [KEEP_SVC=1] ./redeploy.sh
#
# What it does (read-only checks first, then mutating steps clearly fenced):
#   1. sanity: image tag in deployment.yaml matches TAG; lockfile present
#   2. build + push image to Harbor (build.sh)
#   3. recreate the UI: delete the old Deployment (Service kept => LB IP preserved),
#      then `kubectl apply -k k8s/` (re-applies SA/RBAC/Deployment/Service)
#   4. verify: rollout status + /healthz + reported version
#
# It NEVER touches: the namespace, secrets, the ban ConfigMap, or any Isaac Sim
# instance the UI created. Set KEEP_SVC=0 to also delete the Service (LB IP may change).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"   # isaac-saas/deploy
UI_DIR="$HERE/../ui"                     # isaac-saas/ui (Dockerfile + app/)
cd "$HERE"

TAG="${TAG:-0.16.1}"
NS="${NS:-oos-sim}"
KEEP_SVC="${KEEP_SVC:-1}"
HARBOR="${HARBOR:-10.38.38.210}"
PROJECT="${PROJECT:-dt-saas}"
NAME="${NAME:-isaac-ui}"
REF="$HARBOR/$PROJECT/$NAME:$TAG"

say() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

# ---------------------------------------------------------------- 1. sanity
say "1) sanity checks (read-only)"
command -v kubectl >/dev/null || { echo "kubectl not found"; exit 1; }
command -v docker  >/dev/null || { echo "docker not found"; exit 1; }
[ -f "$UI_DIR/uv.lock" ] || { echo "uv.lock missing (expected at $UI_DIR/uv.lock)"; exit 1; }

DEP_IMG=$(grep -E '^\s*image:' k8s/deployment.yaml | head -1 | awk '{print $2}')
if [ "$DEP_IMG" != "$REF" ]; then
  echo "!! k8s/deployment.yaml image ($DEP_IMG) != build ref ($REF)"
  echo "   bump TAG or edit deployment.yaml so they match, then re-run."
  exit 1
fi
echo "image ref: $REF  (matches deployment.yaml)"

# Guard: if ArgoCD already manages this app, manual apply will fight selfHeal.
if kubectl -n argocd get application "$NAME" >/dev/null 2>&1; then
  echo "!! ArgoCD Application '$NAME' exists - it will revert manual changes."
  echo "   Use the GitOps path (commit + 'argocd app sync $NAME') instead. Aborting."
  exit 1
fi

# ---------------------------------------------------------------- 2. build + push
say "2) build + push image"
TAG="$TAG" HARBOR="$HARBOR" PROJECT="$PROJECT" NAME="$NAME" "$UI_DIR/build.sh"

# ---------------------------------------------------------------- 3. redeploy (mutating)
say "3) redeploy"
echo "deleting old Deployment (Service & RBAC handled by apply) ..."
kubectl -n "$NS" delete deployment "$NAME" --ignore-not-found
if [ "$KEEP_SVC" != "1" ]; then
  echo "KEEP_SVC=0 -> deleting Service too (LB IP may change) ..."
  kubectl -n "$NS" delete service "$NAME" --ignore-not-found
fi
echo "applying k8s/ (SA + RBAC + Deployment + Service) ..."
kubectl apply -k k8s/

# ---------------------------------------------------------------- 4. verify
say "4) verify"
kubectl -n "$NS" rollout status deploy/"$NAME" --timeout=180s
IP=$(kubectl -n "$NS" get svc "$NAME" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
echo "service IP: ${IP:-<pending>}"
if [ -n "${IP:-}" ]; then
  echo -n "healthz: "; curl -fsS --max-time 5 "http://$IP/healthz" || echo "(not reachable yet)"
  echo
  VER=$(curl -fsS --max-time 5 "http://$IP/openapi.json" 2>/dev/null \
        | python3 -c "import sys,json;print(json.load(sys.stdin)['info']['version'])" 2>/dev/null || true)
  echo "reported version: ${VER:-?}  (expected $TAG.x)"
  echo "UI: http://$IP   |  API docs: http://$IP/docs"
fi
say "done"
