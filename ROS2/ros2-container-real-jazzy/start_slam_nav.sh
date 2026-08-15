#!/bin/bash
# start_slam_nav.sh — SLAM(매핑) + Nav2 세션 기동 (사용자 수동 실행)
#
# 사용법 (호스트에서):
#   docker exec -it husky /root/start_slam_nav.sh                 # SLAM + Nav2
#   docker exec -it husky /root/start_slam_nav.sh nav_enabled:=false   # SLAM만
#   Ctrl+C 로 종료 (지도는 다음 세션에서 새로 시작)
#
# 전제: 컨테이너가 real_robot 모드로 떠 있고 센서(AUTO_LAUNCH=true) 가동 중.
# slam_toolbox lifecycle configure/activate 는 launch 내부 재시도 루프가 처리.
set -e

source /opt/ros/jazzy/setup.bash
[ -f /etc/clearpath/setup.bash ] && source /etc/clearpath/setup.bash
[ -f /root/ouster_ws/install/setup.bash ] && source /root/ouster_ws/install/setup.bash
if [ -f /root/app_ws/install/setup.bash ]; then
    source /root/app_ws/install/setup.bash
else
    echo "app_ws 미빌드 상태 — 빌드 후 진행"
    cd /root/app_ws && colcon build --symlink-install && source install/setup.bash && cd /root
fi

echo "=== SLAM + Nav2 session start (Ctrl+C to stop) ==="
echo "  map:     /a200_0000/map"
echo "  goal:    RViz2 Nav2 Goal 또는 /a200_0000/navigate_to_pose 액션"
echo ""
exec ros2 launch husky_isaac_bringup slam_nav.launch.py "$@"
