#!/bin/bash
set -e

export FASTRTPS_DEFAULT_PROFILES_FILE=${FASTRTPS_DEFAULT_PROFILES_FILE:-/etc/fastdds/fastdds_force_udp.xml}

echo "--- Docker Entrypoint Start ---"

MODE="isaac_sim_default" # 기본 모드를 Isaac Sim으로 가정
COMMANDS_TO_EXEC="bash"  # 기본적으로 bash 쉘 실행
AUTO_LAUNCH_BRINGUP="false" # 자동으로 robot_bringup.launch.py 실행 여부

# 첫 번째 인자가 있다면 모드로 간주
if [ ! -z "$1" ]; then
    MODE="$1"
    shift # 모드 인자 제거
    if [ ! -z "$1" ]; then # 모드 뒤에 명령어가 있다면
        COMMANDS_TO_EXEC="$@"
    fi
fi

# 환경 변수로 자동 실행 제어 (docker run -e AUTO_LAUNCH=true)
if [ ! -z "$AUTO_LAUNCH" ]; then
    AUTO_LAUNCH_BRINGUP="$AUTO_LAUNCH"
fi

echo "Selected Mode: $MODE"
echo "Auto Launch Bringup: $AUTO_LAUNCH_BRINGUP"
echo "Effective RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION" # Dockerfile에서 설정된 값 확인
echo "FASTRTPS_DEFAULT_PROFILES_FILE: $FASTRTPS_DEFAULT_PROFILES_FILE"

# 워크스페이스 경로 (Dockerfile 내 최종 경로와 일치해야 함)
ROS2_DISTRO_SETUP="/opt/ros/humble/setup.bash"
ISAAC_SIM_WS_SETUP="/root/isaac_sim_ros_ws/src/IsaacSim-ros_workspaces/humble_ws/install/setup.bash"
OUSTER_DRIVER_WS_SETUP="/root/ouster_ws/install/setup.bash"
CLEARPATH_GENERATED_SETUP="/etc/clearpath/setup.bash"

APP_WS="/root/app_ws"

# 모드에 따른 환경 설정 소싱
if [[ "$MODE" == "isaac_sim" || "$MODE" == "isaac_sim_default" ]]; then
    echo "--- Isaac Sim Mode Setup ---"

    if [ -d "${APP_WS}/src" ]; then
        echo "--- Building and sourcing husky_isaac_bringup workspace at ${APP_WS} ---"
        cd ${APP_WS}
        colcon build --symlink-install
        source ${APP_WS}/install/setup.bash
        cd /root # 작업 디렉토리 원위치로 복귀
    else
        echo "Warning: Application workspace source directory not found at ${APP_WS}/src. Skipping build."
    fi


    # 1. Source base ROS 2 Humble environment first
    if [ -f "$ROS2_DISTRO_SETUP" ]; then
        echo "Sourcing ROS 2 Humble environment: $ROS2_DISTRO_SETUP"
        source "$ROS2_DISTRO_SETUP"
    else
        echo "Error: ROS 2 Distro setup file not found at $ROS2_DISTRO_SETUP" >&2
        exit 1
    fi

    # 3. Source Isaac Sim workspace
    if [ -f "$ISAAC_SIM_WS_SETUP" ]; then
        echo "Sourcing Isaac Sim workspace: $ISAAC_SIM_WS_SETUP"
        source "$ISAAC_SIM_WS_SETUP"
    else
        echo "Error: Isaac Sim workspace setup file not found at $ISAAC_SIM_WS_SETUP. Cannot proceed." >&2
        exit 1
    fi
    
    # 4. Nav2 와 SLAM 패키지가 필요하므로 확인
    echo "Checking for Nav2 and SLAM packages..."
    if ros2 pkg list | grep -q "nav2_bringup"; then
        echo "✓ Nav2 packages found"
    else
        echo "⚠ Warning: Nav2 packages not found. Navigation features may not work."
    fi
    
    if ros2 pkg list | grep -q "slam_toolbox"; then
        echo "✓ SLAM Toolbox found"
    else
        echo "⚠ Warning: SLAM Toolbox not found. SLAM features may not work."
    fi
    
    # 5. 센서 드라이버 파일 확인 (실제 로봇 모드에서 사용)
    if [ -f "/root/robot_bringup_sensors.launch.py" ]; then
        echo "✓ Sensor drivers launch file found"
    else
        echo "⚠ Warning: Sensor drivers launch file not found. Real robot sensors may not work."
    fi

    # Isaac Sim 모드에서 자동 실행 또는 수동 명령 처리
    if [ "$AUTO_LAUNCH_BRINGUP" == "true" ]; then
        echo "Auto-launching robot bringup for Isaac Sim mode..."
        COMMANDS_TO_EXEC="ros2 launch husky_isaac_bringup robot_bringup.launch.py robot_mode:=isaac_sim use_sim_time:=true use_sensors:=false"
    elif [ "$MODE" == "isaac_sim_default" ] && [ "$COMMANDS_TO_EXEC" == "bash" ]; then
        echo ""
        echo "==============================================================================="
        echo "Isaac Sim default mode: Environment ready for Isaac Sim connection"
        echo ""
        echo "To start SLAM + Navigation, run:"
        echo "  ros2 launch /root/robot_bringup.launch.py robot_mode:=isaac_sim use_sensors:=false"
        echo ""
        echo "Or set AUTO_LAUNCH=true when running docker:"
        echo "  docker run -e AUTO_LAUNCH=true ..."
        echo ""
        echo "For Isaac Sim with custom topics:"
        echo "  export ROS_SCAN_TOPIC=/virtual/scan"
        echo "  export ROS_ODOM_TOPIC=/virtual/odom"
        echo "  ros2 launch /root/robot_bringup.launch.py robot_mode:=isaac_sim use_sensors:=false"
        echo ""
        echo "Available ROS 2 tools:"
        echo "  ros2 topic list          # View available topics from Isaac Sim"
        echo "  ros2 topic echo /scan    # Monitor laser scan data"
        echo "  ros2 run rviz2 rviz2     # Start visualization"
        echo "==============================================================================="
        echo ""
    fi

elif [ "$MODE" == "real_robot" ]; then
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

    # 3. Source Ouster LiDAR driver workspace
    if [ -f "$OUSTER_DRIVER_WS_SETUP" ]; then
        echo "Sourcing Ouster LiDAR workspace: $OUSTER_DRIVER_WS_SETUP"
        source "$OUSTER_DRIVER_WS_SETUP"
    else
        echo "Warning: Ouster LiDAR workspace setup file not found at $OUSTER_DRIVER_WS_SETUP." >&2
    fi

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
        echo "  Ensure '--device=/dev/ttyUSB0:/dev/ttyUSB0' is part of 'docker run'."
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

    # Real Robot 모드에서 자동 실행 처리
    if [ "$AUTO_LAUNCH_BRINGUP" == "true" ]; then
        echo "Auto-launching robot bringup for Real Robot mode..."
        COMMANDS_TO_EXEC="ros2 launch husky_isaac_bringup robot_bringup.launch.py robot_mode:=real_robot use_sim_time:=false"
    elif [ "$COMMANDS_TO_EXEC" == "bash" ]; then

        echo ""
        echo "==============================================================================="
        echo "Real Robot mode: Environment ready"
        echo ""
        echo "To start complete robot system with SLAM + Navigation:"
        echo "  ros2 launch /root/robot_bringup.launch.py robot_mode:=real_robot"
        echo ""
        echo "Or launch individual components:"
        echo "  ros2 launch /etc/clearpath/platform/launch/platform-service.launch.py"
        echo "  ros2 launch /etc/clearpath/sensors/launch/sensors-service.launch.py"
        echo ""
        echo "For automatic startup, set AUTO_LAUNCH=true when running docker:"
        echo "  docker run -e AUTO_LAUNCH=true ..."
        echo "==============================================================================="
        echo ""
    fi
    
elif [ "$MODE" == "slam_nav_test" ]; then
    # 새로운 테스트 모드: SLAM + Nav2만 빠르게 테스트
    echo "--- SLAM + Navigation Test Mode ---"
    
    # Source ROS 2 environment
    if [ -f "$ROS2_DISTRO_SETUP" ]; then
        source "$ROS2_DISTRO_SETUP"
    fi
    
    echo "Starting SLAM + Nav2 in test mode (no hardware dependencies)..."
    COMMANDS_TO_EXEC="ros2 launch /root/robot_bringup.launch.py \
        robot_mode:=isaac_sim \
        use_ouster:=false \
        use_realsense:=false \
        slam_enabled:=true \
        nav_enabled:=true"
        
else
    echo "Error: Invalid mode '$MODE' specified." >&2
    echo "Allowed modes: 'isaac_sim', 'isaac_sim_default', 'real_robot', 'slam_nav_test'" >&2
    COMMANDS_TO_EXEC="bash"
fi

echo "--- Environment Sourced for mode: $MODE ---"

# AMENT_PREFIX_PATH 출력 (디버깅용 - 간략화)
AMENT_PATHS=$(echo "$AMENT_PREFIX_PATH" | tr ':' '\n')
AMENT_PATHS_COUNT=$(echo "$AMENT_PATHS" | wc -l)
echo "AMENT_PREFIX_PATH: $AMENT_PATHS_COUNT packages loaded"

# 주요 패키지 확인
echo -n "Key packages: "
for pkg in slam_toolbox nav2_bringup clearpath_robot; do
    if ros2 pkg list 2>/dev/null | grep -q "^$pkg$"; then
        echo -n "[$pkg ✓] "
    fi
done
echo ""

echo "--- Executing Command: $COMMANDS_TO_EXEC ---"
exec $COMMANDS_TO_EXEC