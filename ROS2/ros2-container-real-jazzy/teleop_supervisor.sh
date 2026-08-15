#!/bin/bash
# teleop_supervisor.sh — 패드 재열거에 강건한 텔레옵 감독 프로세스 (2026-08)
#
# 문제: DualSense가 절전/재접속할 때마다 /dev/input/jsN 노드가 새로 생성되고
#       (번호가 바뀌기도 함), 기존 joy 노드는 죽은 옛 핸들을 쥔 채 침묵한다.
# 해법: 3초 주기로 (a) 본체가 현재 어느 js 노드인지 /proc 에서 식별하고
#       (b) 노드 inode 변화(재열거)를 감지 → joy_linux 만 해당 장치로 재기동.
#       teleop_node 는 장치와 무관하므로 1회만 기동.
#
# 장치 선택 우선순위:
#   1) /dev/input/dualsense (호스트 udev 규칙 설치 시 — deploy/99-dualsense-js.rules)
#   2) /proc/bus/input/devices 에서 Name="Wireless Controller" 정확 일치 블록의 jsN
#      (Motion Sensors / Touchpad 는 이름이 달라 자동 배제)
#   3) 폴백: /dev/input/js0

source /opt/ros/jazzy/setup.bash

PARAMS=/configs/ds5_teleop.yaml
CMD_VEL="${ROS_CMD_VEL_TOPIC:-/a200_0000/cmd_vel}"
POLL_SEC=3

pick_device() {
    if [ -e /dev/input/dualsense ]; then
        readlink -f /dev/input/dualsense
        return
    fi
    local dev
    dev=$(awk '
        /^N: Name="Wireless Controller"$/ {found=1; next}
        /^N: Name=/ {found=0}
        found && /^H: Handlers=/ {
            for (i=1; i<=NF; i++)
                if ($i ~ /^js[0-9]+$/) { print "/dev/input/" $i; exit }
        }' /proc/bus/input/devices 2>/dev/null)
    if [ -n "$dev" ]; then echo "$dev"; return; fi
    echo /dev/input/js0
}

echo "[teleop_supervisor] cmd_vel=$CMD_VEL params=$PARAMS"
echo "[teleop_supervisor] deadman: hold L1 / turbo: L1+R1"

# teleop_node: 장치 무관 — 1회 기동
ros2 run teleop_twist_joy teleop_node --ros-args \
    --params-file "$PARAMS" -r /cmd_vel:="$CMD_VEL" &
TELEOP_PID=$!

JOY_PID=""
CUR_DEV=""
CUR_INO=""

cleanup() {
    [ -n "$JOY_PID" ] && kill "$JOY_PID" 2>/dev/null
    kill "$TELEOP_PID" 2>/dev/null
    exit 0
}
trap cleanup INT TERM

while true; do
    DEV=$(pick_device)
    INO=$(stat -c '%i' "$DEV" 2>/dev/null || echo none)

    JOY_ALIVE=false
    if [ -n "$JOY_PID" ] && kill -0 "$JOY_PID" 2>/dev/null; then
        JOY_ALIVE=true
    fi

    if [ "$INO" = "none" ]; then
        # 장치 없음: joy 내리고 대기 (재열거되면 다음 주기에 자동 복구)
        if $JOY_ALIVE; then
            echo "[teleop_supervisor] joystick device gone — stopping joy_linux, waiting"
            kill "$JOY_PID" 2>/dev/null
            JOY_PID=""; CUR_DEV=""; CUR_INO=""
        fi
    elif [ "$DEV" != "$CUR_DEV" ] || [ "$INO" != "$CUR_INO" ] || ! $JOY_ALIVE; then
        # 장치가 바뀌었거나(번호 이동/재열거로 inode 변경) joy 가 죽음 → 재기동
        if $JOY_ALIVE; then
            echo "[teleop_supervisor] device changed ($CUR_DEV/$CUR_INO -> $DEV/$INO) — restarting joy_linux"
            kill "$JOY_PID" 2>/dev/null
            sleep 1
        else
            echo "[teleop_supervisor] starting joy_linux on $DEV (inode $INO)"
        fi
        ros2 run joy_linux joy_linux_node --ros-args \
            --params-file "$PARAMS" -p dev:="$DEV" &
        JOY_PID=$!
        CUR_DEV="$DEV"; CUR_INO="$INO"
    fi

    sleep "$POLL_SEC"
done
