#!/bin/bash
# =================================================================
#  Isaac Sim 6.0 Container Entrypoint  (dt-saas)
#  - Xvfb(headless 시) / 확장 자동 등록 / Nucleus 연결 / 시작 stage+camera
#  - ROS2: Jazzy (베이스 24.04, 6.0 도 동일). 브리지 system_default.
#  변경(5.1 대비):
#   * ISAAC_VERSION=6.0, 설정 경로 /root 하드코딩 -> $HOME 기준
#     (6.0 베이스가 rootless(HOME=/isaac-sim)라서. root 로 돌리면 /root)
#   * WebRTC 런처: 6.0 은 runheadless.sh 가 native livestream.
#     isaac-sim.streaming.sh 가 이미지에 남아 있으면 그걸 우선 사용.
#   * k8s UI 호환: 커스텀 커맨드의 첫 인자가 구 5.1 경로
#     /isaac-sim/isaac-sim.streaming.sh 인데 파일이 없으면 6.0 런처로 자동 매핑
#     (isaac-ui 의 STREAM_CMD 를 안 바꿔도 인스턴스가 뜨도록)
# =================================================================
set -e

# --- 0. 버전 / 런처 / 확장 소스 (이미지에서 ls /isaac-sim/*.sh 로 검증) ---
ISAAC_VERSION="6.0"
HOME_DIR="${HOME:-/root}"
GUI_LAUNCHER="/isaac-sim/isaac-sim.sh"               # GUI
PYTHON_LAUNCHER="/isaac-sim/python.sh"
# WebRTC/headless: 5.1 스크립트가 남아 있으면 우선, 없으면 6.0 native livestream
if [ -x "/isaac-sim/isaac-sim.streaming.sh" ]; then
    WEBRTC_LAUNCHER="/isaac-sim/isaac-sim.streaming.sh"
else
    WEBRTC_LAUNCHER="/isaac-sim/runheadless.sh"      # 6.0: headless + WebRTC livestream
fi
HEADLESS_LAUNCHER="/isaac-sim/runheadless.sh"
SRC_DIR="${EXT_SRC_DIR:-/opt/oos_omniverse_extensions}"
EXT_PREFIX="${EXT_PREFIX:-}"   # 공백 구분 다중 가능. 비우면 전부 / 예: "[ext]"
EXTRA_ARGS=""

echo "=== Isaac Sim ${ISAAC_VERSION} Container Starting (HOME=${HOME_DIR}) ==="

# --- 1. 가상 디스플레이 (headless 일 때만) ---
if [ "${START_GUI}" != "true" ]; then
    rm -f /tmp/.X1-lock
    echo "Starting Xvfb on display :1"
    Xvfb :1 -screen 0 1920x1080x24 &
    export DISPLAY=:1
else
    echo "=== GUI MODE === host DISPLAY: ${DISPLAY}"
fi

# --- 2. 확장 업데이트 (git pull) — 단일/다중 repo 모두 지원 ---
update_repo() {
    ( cd "$1" && (git stash -u >/dev/null 2>&1 || true) && \
      ( git pull --ff-only 2>/dev/null || git pull origin main 2>/dev/null || \
        git pull origin master 2>/dev/null || echo "  pull skipped: $1" ) )
}
if [ -d "$SRC_DIR" ]; then
    echo "=== Updating extensions under $SRC_DIR ==="
    if [ -d "$SRC_DIR/.git" ]; then
        update_repo "$SRC_DIR"
    else
        for repo in "$SRC_DIR"/*/; do [ -d "${repo}.git" ] && update_repo "$repo"; done
    fi
    cd /isaac-sim
fi

# --- 3. ROS 2 환경 (Jazzy) ---
[ -f /opt/ros/jazzy/setup.bash ] && source /opt/ros/jazzy/setup.bash && echo "ROS Jazzy loaded"
ROS_WS_SETUP="${ROS_WS_DIR:-/root/isaac_sim_ros_ws}/src/IsaacSim-ros_workspaces/jazzy_ws/install/setup.bash"
[ -f "$ROS_WS_SETUP" ] && source "$ROS_WS_SETUP" && echo "Isaac Sim ROS workspace loaded"

# --- 4. 확장 등록 (symlink + user.config) ---
declare -a extension_paths
declare -A ext_parent_dirs   # 확장을 "담는" 디렉토리(부모) — Kit folders 등록용(대괄호 안전)
registered_count=0
if [ -d "$SRC_DIR" ]; then
    ISAAC_EXTS_DIR="/isaac-sim/exts"
    mkdir -p "$ISAAC_EXTS_DIR"
    while IFS= read -r -d '' toml_file; do
        config_dir=$(dirname "$toml_file")
        ext_path=$(dirname "$config_dir")
        ext_name=$(basename "$ext_path")
        if [ -n "$EXT_PREFIX" ]; then
            # 경로상 "어느 폴더든" 접두사로 시작하면 매칭 (예: [ext]wks-* 래퍼 폴더)
            rel="${ext_path#"$SRC_DIR"/}"
            _matched=0
            IFS='/' read -ra _segs <<< "$rel"
            for _seg in "${_segs[@]}"; do
                for _p in $EXT_PREFIX; do
                    case "$_seg" in "$_p"*) _matched=1; break 2;; esac
                done
            done
            [ "$_matched" -eq 1 ] || continue
        fi
        if [ -f "$ext_path/config/extension.toml" ]; then
            extension_paths+=("$ext_path")
            registered_count=$((registered_count + 1))
            ext_parent_dirs["$(dirname "$ext_path")"]=1
            target_link="$ISAAC_EXTS_DIR/$ext_name"
            { [ -L "$target_link" ] || [ -e "$target_link" ]; } && rm -rf "$target_link"
            ln -s "$ext_path" "$target_link" && echo "  linked: $ext_name"
        fi
    done < <(find "$SRC_DIR" -type f -name "extension.toml" -not -path "*/deprecated/*" -print0)

    if [ ${#extension_paths[@]} -gt 0 ]; then
        # 6.0: 사용자 설정은 $HOME 기준 (rootless 면 /isaac-sim/.local/..., root 면 /root/.local/...)
        USER_CONFIG_DIR="${HOME_DIR}/.local/share/ov/data/Kit/Isaac-Sim/${ISAAC_VERSION}"
        mkdir -p "$USER_CONFIG_DIR"
        USER_CONFIG="$USER_CONFIG_DIR/user.config.json"
        python3 - "$USER_CONFIG" << 'PY'
import json, os, sys
cfg_file = sys.argv[1]
cfg = {}
if os.path.exists(cfg_file):
    try:
        cfg = json.load(open(cfg_file))
    except Exception:
        cfg = {}
cfg.setdefault('exts', {}).setdefault('folders', [])
p = '/isaac-sim/exts'
if p not in cfg['exts']['folders']:
    cfg['exts']['folders'].append(p)
    print('Added extension search path:', p)
json.dump(cfg, open(cfg_file, 'w'), indent=2)
print('Extension registry updated:', cfg_file)
PY
    fi
    echo "Valid extensions found: $registered_count"
fi

# --- 5. Nucleus 연결 ($HOME 기준) ---
OMNIVERSE_CONFIG="${HOME_DIR}/.nvidia-omniverse/config/omniverse.toml"
mkdir -p "$(dirname "$OMNIVERSE_CONFIG")"
cat > "$OMNIVERSE_CONFIG" << EOF
[library_root]
default = "${OMNI_SERVER}"

[settings]
privacy_consent = "Y"
accept_eula = "Y"

[servers."${OMNI_SERVER}"]
enabled = true
username = "${OMNI_USER}"
password = "${OMNI_PASS}"
EOF
if [ -n "${OMNI_SERVER}" ]; then
    ASSET_ROOT="${OMNI_SERVER}/NVIDIA/Assets/Isaac/${ISAAC_VERSION}"
    EXTRA_ARGS+=" --/persistent/isaac/asset_root/default=${ASSET_ROOT}"
fi
echo "Nucleus connection configured"

# --- 6. 시작 stage + camera 스크립트 ---
SCRIPT_DIR="/isaac-sim/scripts"
OPEN_STAGE_SCRIPT="${SCRIPT_DIR}/open_stage_with_camera.py"
mkdir -p "$SCRIPT_DIR"
cat > "$OPEN_STAGE_SCRIPT" << 'PY'
import sys, asyncio
import omni.usd, carb
import omni.kit.viewport.utility as vp_utils

async def setup_stage_and_camera(stage_path, camera_path=None):
    try:
        print(f"[startup] Opening stage: {stage_path}")
        omni.usd.get_context().open_stage(stage_path)
        await asyncio.sleep(2.0)
        if camera_path:
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(camera_path) if stage else None
            if prim and prim.IsValid() and prim.GetTypeName() == "Camera":
                vp = vp_utils.get_active_viewport()
                if vp:
                    vp.set_active_camera(camera_path)
                    print(f"[startup] Active camera set: {camera_path}")
            else:
                carb.log_warn(f"[startup] Camera not found/invalid: {camera_path}")
    except Exception as e:
        carb.log_error(f"[startup] error: {e}")
        import traceback; traceback.print_exc()

if len(sys.argv) > 1:
    asyncio.ensure_future(setup_stage_and_camera(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
else:
    carb.log_warn("[startup] no stage path provided")
PY

# --- 7. 확장 Kit 인자 (대괄호 [ext] 안전: 개별 확장 leaf 대신 "담는 폴더"를 등록) ---
declare -A _seen_folders
add_ext_folder() {
    [ -n "${_seen_folders[$1]:-}" ] && return
    _seen_folders[$1]=1
    EXTRA_ARGS+=" --/app/exts/folders+=$1"
}
add_ext_folder "/isaac-sim/exts"
for d in "${!ext_parent_dirs[@]}"; do add_ext_folder "$d"; done

# --- 8. stage/camera exec 커맨드 ---
# ARRAY, not a string: kit's `--exec "<script> <arg>"` value is ONE token that kit then
# splits on spaces to build the script's argv. A plain string spliced in unquoted below
# would word-split that quoted value apart (the script path and the stage URL become two
# separate kit args), so the stage never opens. An array preserves each --exec value as a
# single argument. (The single-token stage_report worked by luck under the old string.)
EXEC_ARGS=()
# scene 부하 이력: REPORT_URL(k8s UI가 주입) 있으면 stage 이벤트 리포터를 함께 실행
if [ -n "${REPORT_URL:-}" ] && [ -f /opt/experiment/stage_report.py ]; then
    EXEC_ARGS+=(--exec /opt/experiment/stage_report.py)
fi
# 시작 stage 자동 열기: k8s UI(또는 run.env)가 STARTUP_USD_STAGE 를 주입하면 그 USD 를 연다.
if [ -n "${STARTUP_USD_STAGE:-}" ]; then
    if [ -n "${STARTUP_CAMERA_PATH:-}" ]; then
        EXEC_ARGS+=(--exec "${OPEN_STAGE_SCRIPT} ${STARTUP_USD_STAGE} ${STARTUP_CAMERA_PATH}")
    else
        EXEC_ARGS+=(--exec "${OPEN_STAGE_SCRIPT} ${STARTUP_USD_STAGE}")
    fi
    echo "Startup stage: ${STARTUP_USD_STAGE}${STARTUP_CAMERA_PATH:+  (camera ${STARTUP_CAMERA_PATH})}"
fi

# --- 9. 실행 ---
set -f   # globbing 비활성화: 인자에 [ext] 같은 대괄호가 있어도 glob 확장 방지
echo "=== Container Ready ==="
ARGS=("$@")
# k8s UI 호환: 구 5.1 스트리밍 스크립트 경로로 불렸는데 6.0 이미지에 없으면 자동 매핑
if [ ${#ARGS[@]} -gt 0 ] && [[ "${ARGS[0]}" == */isaac-sim.streaming.sh ]] && [ ! -x "${ARGS[0]}" ]; then
    echo "legacy launcher ${ARGS[0]} not in this image -> using ${WEBRTC_LAUNCHER}"
    ARGS[0]="${WEBRTC_LAUNCHER}"
fi
if [ "${START_GUI}" = "true" ]; then
    echo "Launching GUI: ${GUI_LAUNCHER}"
    exec ${GUI_LAUNCHER} ${EXTRA_ARGS} "${EXEC_ARGS[@]}" "${ARGS[@]}"
elif [ "${START_PYTHON}" = "true" ]; then
    echo "Launching Python: ${PYTHON_LAUNCHER}"
    exec ${PYTHON_LAUNCHER} ${EXTRA_ARGS} "${EXEC_ARGS[@]}" "${ARGS[@]}"
elif [ "${START_BASH}" = "true" ]; then
    echo "Starting bash session"
    exec /bin/bash
elif [ "${START_WEBRTC}" = "true" ]; then
    echo "Launching headless + WebRTC: ${WEBRTC_LAUNCHER}"
    exec ${WEBRTC_LAUNCHER} ${EXTRA_ARGS} "${EXEC_ARGS[@]}"
elif [ ${#ARGS[@]} -eq 0 ]; then
    echo "Launching headless: ${HEADLESS_LAUNCHER}"
    exec ${HEADLESS_LAUNCHER} ${EXTRA_ARGS} "${EXEC_ARGS[@]}"
else
    echo "Executing custom command: ${ARGS[*]}"
    exec "${ARGS[@]}" ${EXTRA_ARGS} "${EXEC_ARGS[@]}"
fi
