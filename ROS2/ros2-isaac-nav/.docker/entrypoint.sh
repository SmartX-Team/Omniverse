#!/bin/bash
set -e

# 1. ROS 2 기본 환경을 먼저 source 하여 AMENT_PREFIX_PATH 등의 변수를 생성합니다.
source /opt/ros/humble/setup.bash


if [ -f /root/nav_ws/install/setup.bash ]; then
  source /root/nav_ws/install/setup.bash
  echo "Custom workspace 'nav_ws' sourced."
fi

exec "$@"