#!/bin/bash
set -e

echo "--- Docker Entrypoint Start (real-robot edition / ROS 2 Jazzy, 2026-08) ---"

# Jazzy + Clearpath: 토픽은 robot.yaml namespace(a200_0000)로 네임스페이스되고
# cmd_vel 타입은 TwistStamped. 텔레옵/Nav2 모두 이 env를 따른다.
export ROS_CMD_VEL_TOPIC=${ROS_CMD_VEL_TOPIC:-/a200_0000/cmd_vel}
# 변경점: Isaac Sim(가상 로봇) 모드 제거 — 4.5 시절 코드로 6.0 전환에 따라 폐기.
#         real_robot 이 기본 모드. PS5 DualSense 텔레옵(TELEOP=true 기본) 추가.

MODE="real_robot"          # 기본 모드: 실물 로봇
COMMANDS_TO_EXEC="bash"
AUTO_LAUNCH_BRINGUP="false"
TELEOP_ENABLED="true"      # PS5 텔레옵 기본 ON (데드맨 L1이라 패드 없으면 무해)

# 첫 번째 인자가 있다면 모드로 간주
if [ ! -z "$1" ]; then
    MODE="$1"
    shift
    if [ ! -z "$1" ]; then
        COMMANDS_TO_EXEC="$@"
    fi
fi

# 환경 변수로 자동 실행 제어 (docker run -e AUTO_LAUNCH=true)
if [ ! -z "$AUTO_LAUNCH" ]; then
    AUTO_LAUNCH_BRINGUP="$AUTO_LAUNCH"
fi
# 환경 변수로 텔레옵 제어 (docker run -e TELEOP=false)
if [ ! -z "$TELEOP" ]; then
    TELEOP_ENABLED="$TELEOP"
fi

echo "Selected Mode: $MODE"
echo "Auto Launch Bringup: $AUTO_LAUNCH_BRINGUP"
echo "PS5 Teleop: $TELEOP_ENABLED"
echo "Effective RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION"

# 워크스페이스 경로
ROS2_DISTRO_SETUP="/opt/ros/jazzy/setup.bash"
OUSTER_DRIVER_WS_SETUP="/root/ouster_ws/install/setup.bash"
CLEARPATH_GENERATED_SETUP="/etc/clearpath/setup.bash"

APP_WS="/root/app_ws"

start_teleop_if_enabled() {
    if [ "$TELEOP_ENABLED" == "true" ]; then
        echo "Starting PS5 DualSense teleop (deadman: hold L1, turbo: L1+R1)..."
        if ls /dev/input/js* >/dev/null 2>&1; then
            echo "✓ Joystick device found: $(ls /dev/input/js* | tr '\n' ' ')"
        else
            echo "⚠ Warning: no /dev/input/js* device visible in container."
            echo "  - Pair DualSense on the HOST first (bluetoothctl pair/trust/connect)"
            echo "  - Run docker with --device=/dev:/dev --privileged"
            echo "  joy_node will keep retrying in the background."
        fi
        /root/teleop_supervisor.sh &
        TELEOP_PID=$!
        echo "✓ Teleop supervisor started (PID: $TELEOP_PID) — 재열거 자동 추적"
    fi
}

if [ "$MODE" == "real_robot" ]; then
    echo "--- Real Robot Mode Setup ---"

    # 1. Source base ROS 2 Humble environment
    if [ -f "$ROS2_DISTRO_SETUP" ]; then
        echo "Sourcing ROS 2 Humble environment: $ROS2_DISTRO_SETUP"
        source "$ROS2_DISTRO_SETUP"
    else
        echo "Error: ROS 2 Distro setup file not found at $ROS2_DISTRO_SETUP" >&2
        exit 1
    fi

    # 2. Source Clearpath generated environment
    if [ -f "$CLEARPATH_GENERATED_SETUP" ]; then
        echo "Sourcing generated Clearpath environment: $CLEARPATH_GENERATED_SETUP"
        source "$CLEARPATH_GENERATED_SETUP"
    else
        echo "Warning: Clearpath generated setup file $CLEARPATH_GENERATED_SETUP not found." >&2
    fi

    # 3. Source Ouster LiDAR driver workspace (소스 빌드본)
    if [ -f "$OUSTER_DRIVER_WS_SETUP" ]; then
        echo "Sourcing Ouster LiDAR workspace: $OUSTER_DRIVER_WS_SETUP"
        source "$OUSTER_DRIVER_WS_SETUP"
    else
        echo "Warning: Ouster LiDAR workspace setup file not found at $OUSTER_DRIVER_WS_SETUP." >&2
    fi

    # 4. Build & source app workspace (bringup 패키지)
    if [ -d "${APP_WS}/src" ]; then
        echo "--- Building and sourcing husky_isaac_bringup workspace at ${APP_WS} ---"
        cd ${APP_WS}
        colcon build --symlink-install
        source ${APP_WS}/install/setup.bash
        cd /root
    fi

    # Export CPR_SETUP_PATH
    export CPR_SETUP_PATH=/etc/clearpath
    echo "CPR_SETUP_PATH set to: $CPR_SETUP_PATH"

    # --- MCU 시리얼 포트 심볼릭 링크 생성 ---
    REAL_MCU_DEVICE="/dev/ttyUSB0"
    SYMLINK_PATH="/dev/clearpath/prolific"
    SYMLINK_DIR=$(dirname "$SYMLINK_PATH")

    echo "Checking for MCU device $REAL_MCU_DEVICE..."
    if [ -e "$REAL_MCU_DEVICE" ]; then
        mkdir -p "$SYMLINK_DIR"
        if [ ! -L "$SYMLINK_PATH" ]; then
            ln -s "$REAL_MCU_DEVICE" "$SYMLINK_PATH" && \
                echo "✓ Symlink $SYMLINK_PATH -> $REAL_MCU_DEVICE created." || \
                echo "✗ Failed to create symlink $SYMLINK_PATH."
        else
            echo "✓ Symlink $SYMLINK_PATH already exists."
        fi
    else
        echo "⚠ Warning: MCU device $REAL_MCU_DEVICE not found in container."
        echo "  Ensure '--device=/dev:/dev' (or at least ttyUSB0) is part of 'docker run'."
    fi

    echo "Starting Clearpath platform services..."
    ros2 launch /etc/clearpath/platform/launch/platform-service.launch.py &
    PLATFORM_PID=$!
    sleep 3

    echo "Starting Clearpath sensor services..."
    ros2 launch /etc/clearpath/sensors/launch/sensors-service.launch.py &
    SENSORS_PID=$!
    sleep 2

    echo "✓ Clearpath services started (Platform PID: $PLATFORM_PID, Sensors PID: $SENSORS_PID)"

    # --- PS5 텔레옵 (신규) ---
    start_teleop_if_enabled

    # Real Robot 모드에서 자동 실행 처리
    # AUTO_LAUNCH=true → 센서 드라이버(Ouster/RealSense)까지만 자동 기동.
    # SLAM/Nav2는 lifecycle 관리 특성상 사용자가 세션 단위로 직접 켠다:
    #   docker exec -it husky /root/start_slam_nav.sh
    if [ "$AUTO_LAUNCH_BRINGUP" == "true" ]; then
        echo "Auto-launching sensor drivers (Ouster/RealSense)..."
        echo ""
        echo ">>> SLAM/Nav2 는 필요할 때:  docker exec -it husky /root/start_slam_nav.sh"
        echo ""
        COMMANDS_TO_EXEC="ros2 launch husky_isaac_bringup robot_bringup_sensors.launch.py"
    elif [ "$COMMANDS_TO_EXEC" == "bash" ]; then
        echo ""
        echo "==============================================================================="
        echo "Real Robot mode: Environment ready"
        echo ""
        echo "PS5 teleop: running in background (TELEOP=$TELEOP_ENABLED)"
        echo "  - drive: hold L1 + left stick (fwd/back) / right stick (turn)"
        echo "  - verify pad mapping:  ros2 topic echo /joy"
        echo ""
        echo "To start complete robot system with SLAM + Navigation:"
        echo "  ros2 launch husky_isaac_bringup robot_bringup.launch.py robot_mode:=real_robot"
        echo ""
        echo "Or launch individual components:"
        echo "  ros2 launch /etc/clearpath/platform/launch/platform-service.launch.py"
        echo "  ros2 launch /etc/clearpath/sensors/launch/sensors-service.launch.py"
        echo ""
        echo "For automatic startup, set AUTO_LAUNCH=true when running docker."
        echo "==============================================================================="
        echo ""
    fi

elif [ "$MODE" == "sensors_only" ]; then
    # 센서 드라이버만 (베이스 없이 Ouster/RealSense 점검용)
    echo "--- Sensors Only Mode ---"
    source "$ROS2_DISTRO_SETUP"
    [ -f "$OUSTER_DRIVER_WS_SETUP" ] && source "$OUSTER_DRIVER_WS_SETUP"
    if [ -d "${APP_WS}/src" ]; then
        cd ${APP_WS} && colcon build --symlink-install && source ${APP_WS}/install/setup.bash && cd /root
    fi
    COMMANDS_TO_EXEC="ros2 launch husky_isaac_bringup robot_bringup_sensors.launch.py"

elif [ "$MODE" == "joytest" ]; then
    # 로봇 없이 패드 매핑 확인: joy_node만 실행
    echo "--- Joystick Test Mode ---"
    source "$ROS2_DISTRO_SETUP"
    echo ">>> 다른 셸에서: docker exec -it <container> bash -c 'source /opt/ros/jazzy/setup.bash && ros2 topic echo /joy'"
    COMMANDS_TO_EXEC="ros2 run joy joy_node --ros-args --params-file /configs/ds5_teleop.yaml"

else
    echo "Error: Invalid mode '$MODE' specified." >&2
    echo "Allowed modes: 'real_robot', 'sensors_only', 'joytest'" >&2
    source "$ROS2_DISTRO_SETUP"
    COMMANDS_TO_EXEC="bash"
fi

echo "--- Environment Sourced for mode: $MODE ---"

# AMENT_PREFIX_PATH 출력 (디버깅용 - 간략화)
AMENT_PATHS=$(echo "$AMENT_PREFIX_PATH" | tr ':' '\n')
AMENT_PATHS_COUNT=$(echo "$AMENT_PATHS" | wc -l)
echo "AMENT_PREFIX_PATH: $AMENT_PATHS_COUNT packages loaded"

# 주요 패키지 확인
echo -n "Key packages: "
for pkg in slam_toolbox nav2_bringup clearpath_robot ouster_ros joy teleop_twist_joy; do
    if ros2 pkg list 2>/dev/null | grep -q "^$pkg$"; then
        echo -n "[$pkg ✓] "
    fi
done
echo ""

echo "--- Executing Command: $COMMANDS_TO_EXEC ---"
exec $COMMANDS_TO_EXEC
