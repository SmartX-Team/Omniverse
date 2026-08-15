#!/usr/bin/env python3
"""
ds5_teleop.launch.py — PS5 DualSense 텔레옵 (신규, 2026-08)

joy_linux(커널 js 직독) + teleop_twist_joy 를 띄워 게임패드 입력을 Twist로 변환한다.
발행 토픽: ROS_CMD_VEL_TOPIC (entrypoint 기본 /a200_0000/cmd_vel).\n메시지 타입: TwistStamped (Jazzy Clearpath 요구사항, ds5_teleop.yaml에서 설정).

entrypoint.sh 의 real_robot 모드에서 TELEOP=true(기본)일 때 백그라운드로 포함되며,
단독 실행도 가능:
    ros2 launch /root/ds5_teleop.launch.py
"""

import os

from launch import LaunchDescription
from launch.actions import LogInfo
from launch_ros.actions import Node

DS5_PARAMS = "/configs/ds5_teleop.yaml"


def generate_launch_description():
    cmd_vel_topic = os.environ.get("ROS_CMD_VEL_TOPIC", "/a200_0000/cmd_vel")

    return LaunchDescription([
        LogInfo(msg=f"[ds5_teleop] publishing Twist to: {cmd_vel_topic} "
                    "(deadman: hold L1, turbo: L1+R1)"),
        Node(
            package="joy_linux",
            executable="joy_linux_node",
            name="joy_node",
            output="screen",
            parameters=[DS5_PARAMS],
        ),
        Node(
            package="teleop_twist_joy",
            executable="teleop_node",
            name="teleop_twist_joy_node",
            output="screen",
            parameters=[DS5_PARAMS],
            remappings=[("/cmd_vel", cmd_vel_topic)],
        ),
    ])
