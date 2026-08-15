#!/usr/bin/env python3
"""
slam_nav.launch.py — Husky A200 실물 + ROS 2 Jazzy 전용 SLAM(매핑) + Nav2 (2026-08)

구 robot_bringup.launch.py(Isaac 4.5 시절)를 대체하는 클린 구현. 핵심 설계:

1. 전 노드를 /a200_0000 네임스페이스에서 기동하고 ('/tf' → 'tf') 리매핑
   → Clearpath Jazzy가 /a200_0000/tf 로 쏘는 odom→base_link TF와 합류.
2. Clearpath 플랫폼은 여기서 기동하지 않음 (entrypoint가 소유 — 이중 기동 버그 제거).
3. cmd_vel 체인: controller/behaviors → cmd_vel_nav → velocity_smoother → cmd_vel
   전부 TwistStamped (params의 enable_stamped_cmd_vel) →
   최종 /a200_0000/cmd_vel 은 Clearpath twist_mux 입력. 조이스틱(L1)이 우선권 유지.
4. 스캔 파이프: /ouster/scan → (relay) → /a200_0000/scan.
   base_link→os_lidar 정적 TF는 여기서 발행 (마운트 오프셋 env로 조정).

env:
  ROS_ROBOT_NS        (기본 a200_0000)
  ROS_LIDAR_XYZ_RPY   (기본 "0 0 0.5 0 0 0")  base_link→os_lidar 마운트
  ROS_SCAN_SOURCE     (기본 /ouster/scan)
"""

import os

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess, GroupAction,
                            LogInfo, TimerAction)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml

NAV2_PARAMS = "/root/app_ws/src/husky_isaac_bringup/config/nav2_params_jazzy_real.yaml"


def generate_launch_description():
    ns = os.environ.get("ROS_ROBOT_NS", "a200_0000")
    scan_source = os.environ.get("ROS_SCAN_SOURCE", "/ouster/scan")
    lidar_mount = os.environ.get("ROS_LIDAR_XYZ_RPY", "0 0 0.5 0 0 0").split()

    nav_enabled = LaunchConfiguration("nav_enabled")
    slam_enabled = LaunchConfiguration("slam_enabled")

    tf_remaps = [("/tf", "tf"), ("/tf_static", "tf_static")]

    # ---- 스캔 relay: /ouster/scan → /<ns>/scan --------------------------------
    scan_relay = Node(
        package="topic_tools",
        executable="relay",
        name="ouster_scan_relay",
        namespace=ns,
        parameters=[{"input_topic": scan_source, "output_topic": f"/{ns}/scan"}],
        output="screen",
    )

    # ---- base_link → os_lidar 정적 TF (네임스페이스 tf로 발행) -----------------
    lidar_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="static_tf_base_to_lidar",
        namespace=ns,
        arguments=lidar_mount + ["base_link", "os_lidar"],
        remappings=tf_remaps,
        output="screen",
    )

    # ---- SLAM Toolbox (async 매핑) --------------------------------------------
    slam = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        namespace=ns,
        output="screen",
        parameters=[{
            "use_sim_time": False,
            "mode": "mapping",
            "scan_topic": "scan",          # 상대 → /<ns>/scan
            "map_frame": "map",
            "odom_frame": "odom",
            "base_frame": "base_link",
            "resolution": 0.05,
            "max_laser_range": 20.0,
            "transform_timeout": 0.5,
            "minimum_travel_distance": 0.2,
            "minimum_travel_heading": 0.2,
        }],
        # slam_toolbox는 map 토픽을 절대경로(/map)로 발행해 네임스페이스를 탈출
        # → 명시 리매핑으로 /<ns>/map 에 가둠
        remappings=tf_remaps + [("/map", "map"), ("/map_metadata", "map_metadata")],
        condition=IfCondition(slam_enabled),
    )

    # ---- slam_toolbox lifecycle 활성화 (Jazzy 전환점) --------------------------
    # Jazzy의 slam_toolbox는 lifecycle 노드 — 명시적으로 configure/activate 하지
    # 않으면 UNCONFIGURED 상태로 잠들어 스캔 구독조차 하지 않는다.
    # 원샷 호출은 노드의 lifecycle 서비스가 뜨기 전에 떨어지는 레이스가 있어
    # 재시도 루프로 감쌈 (최대 ~60초 대기).
    slam_lifecycle_up = ExecuteProcess(
        cmd=["bash", "-c",
             f"for i in $(seq 1 30); do "
             f"ros2 lifecycle set /{ns}/slam_toolbox configure && break; sleep 2; done; "
             f"sleep 1; "
             f"for i in $(seq 1 30); do "
             f"ros2 lifecycle set /{ns}/slam_toolbox activate && break; sleep 2; done; "
             f"echo '[slam_nav] slam_toolbox lifecycle up'"],
        output="screen", condition=IfCondition(slam_enabled))

    # ---- Nav2 (노드 명시 기동 — nav2_bringup 미사용) ---------------------------
    # nav2_bringup navigation_launch.py는 Jazzy에서 collision_monitor/docking 등
    # 추가 노드를 끌고 들어와 파라미터 미비 시 configure 실패 → 명시 기동으로 통제.
    #
    # RewrittenYaml(root_key=ns): 노드가 /<ns> 아래로 가면 yaml 최상위 키가
    # 노드 FQN과 안 맞아 파라미터가 통째로 무시됨 → 네임스페이스 키를 앞에 씌워
    # 재작성 (nav2_bringup 표준 방식과 동일).
    configured_params = RewrittenYaml(
        source_file=NAV2_PARAMS, root_key=ns, param_rewrites={}, convert_types=True)
    common = dict(namespace=ns, output="screen", parameters=[configured_params])

    controller = Node(
        package="nav2_controller", executable="controller_server",
        name="controller_server",
        remappings=tf_remaps + [("cmd_vel", "cmd_vel_nav")],
        **common)
    planner = Node(
        package="nav2_planner", executable="planner_server",
        name="planner_server", remappings=tf_remaps, **common)
    behaviors = Node(
        package="nav2_behaviors", executable="behavior_server",
        name="behavior_server",
        remappings=tf_remaps + [("cmd_vel", "cmd_vel_nav")],
        **common)
    bt_nav = Node(
        package="nav2_bt_navigator", executable="bt_navigator",
        name="bt_navigator", remappings=tf_remaps, **common)
    waypoints = Node(
        package="nav2_waypoint_follower", executable="waypoint_follower",
        name="waypoint_follower", remappings=tf_remaps, **common)
    smoother = Node(
        package="nav2_velocity_smoother", executable="velocity_smoother",
        name="velocity_smoother",
        remappings=tf_remaps + [("cmd_vel", "cmd_vel_nav"),
                                ("cmd_vel_smoothed", "cmd_vel")],
        **common)
    lifecycle = Node(
        package="nav2_lifecycle_manager", executable="lifecycle_manager",
        name="lifecycle_manager_navigation",
        namespace=ns, output="screen",
        parameters=[{
            "use_sim_time": False,
            "autostart": True,
            "node_names": [
                "controller_server", "planner_server", "behavior_server",
                "bt_navigator", "waypoint_follower", "velocity_smoother",
            ],
        }])

    nav2_group = GroupAction(
        condition=IfCondition(nav_enabled),
        actions=[LogInfo(msg=f"[slam_nav] Starting Nav2 in /{ns} (stamped cmd_vel)"),
                 controller, planner, behaviors, bt_nav, waypoints, smoother, lifecycle],
    )

    return LaunchDescription([
        DeclareLaunchArgument("slam_enabled", default_value="true"),
        DeclareLaunchArgument("nav_enabled", default_value="true"),
        LogInfo(msg=f"[slam_nav] ns=/{ns} scan={scan_source} lidar_mount={' '.join(lidar_mount)}"),
        scan_relay,
        lidar_tf,
        TimerAction(period=3.0, actions=[slam]),
        TimerAction(period=6.0, actions=[slam_lifecycle_up]),
        # Nav2는 slam 활성화 후 (global_costmap이 map 프레임을 기다림 — 60초 여유)
        TimerAction(period=15.0, actions=[nav2_group]),
    ])
