#!/bin/bash
set -e

export FASTRTPS_DEFAULT_PROFILES_FILE=${FASTRTPS_DEFAULT_PROFILES_FILE:-/etc/fastdds/fastdds_force_udp.xml}

echo "--- Docker Entrypoint Start ---"

MODE="isaac_sim_default" # 기본 모드를 Isaac Sim으로 가정
COMMANDS_TO_EXEC="bash"  # 기본적으로 bash 쉘 실행

# 첫 번째 인자가 있다면 모드로 간주
if [ ! -z "$1" ]; then
    MODE="$1"
    shift # 모드 인자 제거
    if [ ! -z "$1" ]; then # 모드 뒤에 명령어가 있다면
        COMMANDS_TO_EXEC="$@"
    fi
fi

echo "Selected Mode: $MODE"
echo "Effective RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION" # Dockerfile에서 설정된 값 확인
echo "FASTRTPS_DEFAULT_PROFILES_FILE: $FASTRTPS_DEFAULT_PROFILES_FILE"

# 워크스페이스 경로 (Dockerfile 내 최종 경로와 일치해야 함)
ROS2_DISTRO_SETUP="/opt/ros/humble/setup.bash"
ISAAC_SIM_WS_SETUP="/root/isaac_sim_ros_ws/src/IsaacSim-ros_workspaces/humble_ws/install/setup.bash"
#USER_CUSTOM_WS_SETUP="/root/user_clearpath_ws/install/setup.bash" 필요시 실행 # 예시
OUSTER_DRIVER_WS_SETUP="/root/ouster_ws/install/setup.bash"
CLEARPATH_GENERATED_SETUP="/etc/clearpath/setup.bash"

# 모드에 따른 환경 설정 소싱
if [[ "$MODE" == "isaac_sim" || "$MODE" == "isaac_sim_default" ]]; then
    echo "--- Isaac Sim Mode Setup ---"
    # Isaac Sim 모드에서는 Isaac Sim 워크스페이스만 source (ROS 기본 환경도 여기서 관리될 것으로 가정)
    if [ -f "$ISAAC_SIM_WS_SETUP" ]; then
        echo "Sourcing Isaac Sim workspace: $ISAAC_SIM_WS_SETUP"
        source "$ISAAC_SIM_WS_SETUP"
    else
        echo "Error: Isaac Sim workspace setup file not found at $ISAAC_SIM_WS_SETUP. Cannot proceed." >&2
        exit 1
    fi
    # Isaac Sim 모드에서 사용자 정의 워크스페이스(Kafka 조이스틱 등)가 필요하다면 여기서 추가 source
    # if [ -f "$USER_CUSTOM_WS_SETUP" ]; then
    #     echo "Sourcing user custom workspace for Isaac Sim: $USER_CUSTOM_WS_SETUP"
    #     source "$USER_CUSTOM_WS_SETUP"
    # fi


    # Isaac Sim 모드이고, docker run 시 별도 명령이 없었다면, 기본적으로 bash 실행
    if [ "$MODE" == "isaac_sim_default" ] && [ "$COMMANDS_TO_EXEC" == "bash" ]; then
        echo "Isaac Sim default mode: Environment sourced. Ready for Isaac Sim connection or manual commands."
        # 기존에 Isaac Sim 연동을 위해 자동으로 실행되던 명령이 생긴다면 일단 여기에 추가
        # 예: COMMANDS_TO_EXEC="ros2 launch isaac_ros_bridge client.launch.py"
    fi

elif [ "$MODE" == "real_robot" ]; then
    echo "--- Real Robot Mode Setup ---"
    # 1. Source base ROS 2 Humble environment
    if [ -f "$ROS2_DISTRO_SETUP" ]; then
        echo "Sourcing ROS 2 Humble environment: $ROS2_DISTRO_SETUP"
        source "$ROS2_DISTRO_SETUP"
    else
        echo "Error: ROS 2 Distro setup file not found at $ROS2_DISTRO_SETUP" >&2; exit 1
    fi
    
    # 2. Source Clearpath generated environment
    if [ -f "$CLEARPATH_GENERATED_SETUP" ]; then
        echo "Sourcing generated Clearpath environment: $CLEARPATH_GENERATED_SETUP"
        source "$CLEARPATH_GENERATED_SETUP"
    else
        echo "Warning: Clearpath generated setup file $CLEARPATH_GENERATED_SETUP not found." >&2
        # This might be critical, consider exiting if it's always required
    fi

    # 3. Source Ouster LiDAR driver workspace (if it exists and is used)
    if [ -f "$OUSTER_DRIVER_WS_SETUP" ]; then
        echo "Sourcing Ouster LiDAR workspace: $OUSTER_DRIVER_WS_SETUP"
        source "$OUSTER_DRIVER_WS_SETUP"
    else
        echo "Warning: Ouster LiDAR workspace setup file not found at $OUSTER_DRIVER_WS_SETUP." >&2
    fi

    # Export CPR_SETUP_PATH, potentially used by Clearpath launch files
    export CPR_SETUP_PATH=/etc/clearpath
    echo "CPR_SETUP_PATH set to: $CPR_SETUP_PATH"


    # --- MCU 시리얼 포트 심볼릭 링크 생성 시작 호스트 시스템에 따라 달라질 수 있으니 미리 호스트 시스템 설정 체크 ---
    REAL_MCU_DEVICE="/dev/ttyUSB0" # 호스트에서 확인된 실제 장치명
    SYMLINK_PATH="/dev/clearpath/prolific"
    SYMLINK_DIR=$(dirname "$SYMLINK_PATH") # /dev/clearpath

    echo "Checking for MCU device $REAL_MCU_DEVICE and attempting to create symlink $SYMLINK_PATH..."
    if [ -e "$REAL_MCU_DEVICE" ]; then
        mkdir -p "$SYMLINK_DIR"
        if [ ! -L "$SYMLINK_PATH" ]; then # -L: 심볼릭 링크인지 확인, !-e: 파일/디렉토리/링크 없는지 확인
            ln -s "$REAL_MCU_DEVICE" "$SYMLINK_PATH" && echo "Symlink $SYMLINK_PATH -> $REAL_MCU_DEVICE created." || echo "Failed to create symlink $SYMLINK_PATH."
        else
            echo "Symlink $SYMLINK_PATH already exists."
        fi
    else
        echo "Warning: Target MCU device $REAL_MCU_DEVICE not found in container. Cannot create symlink."
        echo "Ensure '--device=/dev/ttyUSB0:/dev/ttyUSB0' or similar is part of 'docker run'."
    fi
    # --- MCU 시리얼 포트 심볼릭 링크 생성 끝 ---


    PLATFORM_LAUNCH_FILE="/etc/clearpath/platform/launch/platform-service.launch.py"
    SENSORS_LAUNCH_FILE="/etc/clearpath/sensors/launch/sensors-service.launch.py"
    MANIPULATORS_LAUNCH_FILE="/etc/clearpath/manipulators/launch/manipulators-service.launch.py" # If used

    if [ -f "$PLATFORM_LAUNCH_FILE" ]; then
        echo "Launching Clearpath Platform Service in background: $PLATFORM_LAUNCH_FILE"
        ros2 launch "$PLATFORM_LAUNCH_FILE" &
        sleep 3 # Give it a moment to start
    else
        echo "Warning: Platform service launch file not found at $PLATFORM_LAUNCH_FILE"
    fi
    
    if [ -f "$SENSORS_LAUNCH_FILE" ]; then
        echo "Launching Clearpath Sensors Service in background: $SENSORS_LAUNCH_FILE"
        ros2 launch "$SENSORS_LAUNCH_FILE" &
        sleep 3 # Give it a moment to start
    else
        echo "Warning: Sensors service launch file not found at $SENSORS_LAUNCH_FILE"
    fi

    # If defaulting to bash in real_robot mode, provide instructions
    if [ "$COMMANDS_TO_EXEC" == "bash" ]; then
        echo "Real Robot mode: Environment sourced. To start robot services, run commands like:"
        echo "  ros2 launch /etc/clearpath/platform/launch/platform-service.launch.py"
        echo "  ros2 launch /etc/clearpath/sensors/launch/sensors-service.launch.py"
        # Add manipulators if applicable:
        # echo "  ros2 launch /etc/clearpath/manipulators/launch/manipulators-service.launch.py"
        echo "These can be run in separate terminals using 'docker exec', or combined in a custom launch file."
    fi
else
    echo "Error: Invalid mode '$MODE' specified. Allowed: 'isaac_sim', 'isaac_sim_default', or 'real_robot'." >&2
    COMMANDS_TO_EXEC="bash" # Default to bash on error
fi

echo "--- Environment Sourced for mode: $MODE ---"
# AMENT_PREFIX_PATH 출력 (디버깅용)
AMENT_PATHS=$(echo "$AMENT_PREFIX_PATH" | tr ':' '\n')
AMENT_PATHS_COUNT=$(echo "$AMENT_PATHS" | wc -l)
if [ "$AMENT_PATHS_COUNT" -gt 6 ]; then
    SHOWN_AMENT_PATHS=$(echo "$AMENT_PATHS" | head -n 3; echo "..."; echo "$AMENT_PATHS" | tail -n 3)
else
    SHOWN_AMENT_PATHS=$(echo "$AMENT_PATHS")
fi
echo "AMENT_PREFIX_PATH (sample):"
echo "$SHOWN_AMENT_PATHS" | tr '\n' ':' | sed 's/:$//' && echo ""

echo "--- Executing Command: $COMMANDS_TO_EXEC ---"
exec $COMMANDS_TO_EXEC