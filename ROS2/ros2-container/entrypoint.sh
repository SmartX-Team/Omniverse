#!/bin/bash
set -e

# RMW 구현 및 FastDDS 프로파일 명시적 설정
# RMW_IMPLEMENTATION은 Dockerfile의 ENV로 설정되었으므로 여기서는 export 불필요 (단, 확인용으로 echo는 유용)
# export RMW_IMPLEMENTATION=rmw_fastrtps_cpp (Dockerfile ENV 사용 시 이 줄은 없어도 됨)
export FASTRTPS_DEFAULT_PROFILES_FILE=/etc/fastdds/fastdds_force_udp.xml

echo "--- Docker Entrypoint Start ---"
echo "Effective RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION"
echo "FASTRTPS_DEFAULT_PROFILES_FILE: $FASTRTPS_DEFAULT_PROFILES_FILE"

# 1. 기본 ROS 2 Humble 환경 설정 소싱
ROS2_DISTRO_SETUP="/opt/ros/humble/setup.bash"
if [ -f "$ROS2_DISTRO_SETUP" ]; then
    echo "Sourcing ROS 2 Humble environment: $ROS2_DISTRO_SETUP"
    source "$ROS2_DISTRO_SETUP"
else
    echo "Error: ROS 2 Distro setup file not found at $ROS2_DISTRO_SETUP"
    exit 1
fi

# 2. 빌드된 워크스페이스 환경 설정 소싱 (Dockerfile에서 빌드한 경우)
# Dockerfile에서 IsaacSim-ros_workspaces 빌드 부분을 주석 처리했다면 아래도 주석 처리 또는 경로 조정
ROS_WORKSPACE_SETUP_PATH_PREFIX="/root/isaac_sim_ros_ws"
ROS_WORKSPACE_SETUP_PATH="$ROS_WORKSPACE_SETUP_PATH_PREFIX/src/IsaacSim-ros_workspaces/humble_ws/install/setup.bash"

if [ -f "$ROS_WORKSPACE_SETUP_PATH" ]; then
    echo "Sourcing ROS 2 Workspace environment: $ROS_WORKSPACE_SETUP_PATH"
    source "$ROS_WORKSPACE_SETUP_PATH"
else
    echo "Warning: Workspace setup file not found at $ROS_WORKSPACE_SETUP_PATH. (This may be OK if not using a custom workspace from IsaacSim-ros_workspaces)."
fi
echo "--- Environment Sourced ---"

# 전달된 명령어 실행
exec "$@"