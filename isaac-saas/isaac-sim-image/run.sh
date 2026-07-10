#!/usr/bin/env bash
# Isaac Sim 6.0 단독 실행 (docker run). k8s 배포는 ui repo 의 k8s/ 참조.
# 캐시 호스트 경로는 5.1 과 분리 (~/docker/isaac-sim6) — 구버전 캐시 잔재가
# 크래시를 유발할 수 있어(공식 문서 경고) 새 디렉토리를 쓴다.
set -euo pipefail
cd "$(dirname "$0")"
[ -f run.env ] || { echo "run.env 없음 — 먼저:  cp run.env.example run.env  후 값 채우기"; exit 1; }
set -a; . ./run.env; set +a

EXT_SRC_DIR="${EXT_SRC_DIR:-/opt/oos_omniverse_extensions}"
IMAGE_NAME="${IMAGE_NAME:-isaac-sim}"
IMAGE_TAG="${IMAGE_TAG:-6.0}"
CACHE_ROOT="${CACHE_ROOT:-$HOME/docker/isaac-sim6}"

mkdir -p "$CACHE_ROOT"/{cache/main,cache/computecache,logs,data} "$HOME/.cache/ov/hub"

GUI_MOUNTS=()
if [ "${START_GUI:-false}" = "true" ]; then
  GUI_MOUNTS=(-e "DISPLAY=${DISPLAY:-:0}" -v /tmp/.X11-unix:/tmp/.X11-unix:rw)
fi

EXT_MOUNT=()
if [ -n "${EXT_LOCAL_PATH:-}" ]; then
  [ -d "${EXT_LOCAL_PATH}" ] || { echo "EXT_LOCAL_PATH 경로 없음: ${EXT_LOCAL_PATH}"; exit 1; }
  ext_name="$(basename "${EXT_LOCAL_PATH%/}")"
  EXT_MOUNT=(-v "${EXT_LOCAL_PATH%/}:${EXT_SRC_DIR}/${ext_name}:ro")
  echo "Mounting local extensions (ro): ${EXT_LOCAL_PATH} -> ${EXT_SRC_DIR}/${ext_name}"
fi

# GPU 전달 방식 (5.1 과 동일)
#  - gpus   : 표준 (--gpus). 호스트가 no-cgroups=false 일 때
#  - device : 우회 (--runtime=nvidia + --device). no-cgroups=true 라 --gpus 가 NVML 실패할 때
GPU_ARGS=()
if [ "${GPU_MODE:-gpus}" = "device" ]; then
  GPU_ARGS=(--runtime=nvidia
            -e "NVIDIA_VISIBLE_DEVICES=${GPU_DEVICE:-0}"
            --device /dev/nvidiactl
            --device /dev/nvidia-modeset
            --device /dev/nvidia-uvm
            --device /dev/nvidia-uvm-tools
            --device "/dev/nvidia${GPU_DEVICE:-0}")
  echo "GPU mode: device passthrough (GPU ${GPU_DEVICE:-0}) — no-cgroups 우회"
else
  GPU_ARGS=(--gpus "device=${GPU_DEVICE:-0}")
fi

# 이 이미지는 root 로 실행(엔트리포인트가 $HOME 기준 경로 사용) → 캐시는 /root/... 에 마운트.
# 공식 rootless(1234) 로 돌리려면: -u 1234:1234 + 마운트 대상을 /isaac-sim/... 으로 교체.
docker run --rm -it \
  --name "${CONTAINER_NAME:-isaac-sim-6}" \
  "${GPU_ARGS[@]}" \
  --network host --ipc host \
  -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y -e OMNI_KIT_ALLOW_ROOT=1 \
  -e OMNI_SERVER -e OMNI_USER -e OMNI_PASS \
  -e START_GUI -e START_WEBRTC -e STARTUP_USD_STAGE -e STARTUP_CAMERA_PATH \
  -e ISAACSIM_HOST -e ISAACSIM_SIGNAL_PORT -e ISAACSIM_STREAM_PORT \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e EXT_SRC_DIR -e EXT_PREFIX \
  "${GUI_MOUNTS[@]}" \
  "${EXT_MOUNT[@]}" \
  -v "$CACHE_ROOT/cache/main:/root/.cache:rw" \
  -v "$CACHE_ROOT/cache/computecache:/root/.nv/ComputeCache:rw" \
  -v "$CACHE_ROOT/logs:/root/.nvidia-omniverse/logs:rw" \
  -v "$CACHE_ROOT/data:/root/.local/share/ov/data:rw" \
  -v "$HOME/.cache/ov/hub:/var/cache/hub:rw" \
  "${IMAGE_NAME}:${IMAGE_TAG}"
