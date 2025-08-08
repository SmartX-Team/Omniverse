#!/usr/bin/env python3
"""
Main Robot Bringup Launch File - Fixed Version
Handles SLAM, Navigation2, TF Bridge, and Auto Initial Pose

This is the main entry point that:
- Always launches SLAM and Nav2 (if enabled)
- Includes TF bridge for Isaac Sim compatibility
- Auto-sets initial pose for any starting position
- Conditionally includes sensor drivers for real robot mode

Author: InYong Song
Version: 5.1 - Syntax Error Fixed
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, 
    IncludeLaunchDescription,
    GroupAction,
    TimerAction,
    LogInfo,
    ExecuteProcess
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch.conditions import IfCondition

def generate_launch_description():

    bringup_package_path = '/root/app_ws/src/husky_isaac_bringup'

    # ===== Environment Variables for Topic Names =====
    scan_topic = os.environ.get('ROS_SCAN_TOPIC', '/scan_stamped')
    odom_topic = os.environ.get('ROS_ODOM_TOPIC', '/odom')
    cmd_vel_topic = os.environ.get('ROS_CMD_VEL_TOPIC', '/cmd_vel')
    pointcloud_topic = os.environ.get('ROS_POINTCLOUD_TOPIC', '/points')
    imu_topic = os.environ.get('ROS_IMU_TOPIC', '/imu/data')
    
    # TF Frame names
    map_frame = os.environ.get('ROS_MAP_FRAME', 'map')
    odom_frame = os.environ.get('ROS_ODOM_FRAME', 'odom')
    base_frame = os.environ.get('ROS_BASE_FRAME', 'base_link')
    laser_frame = os.environ.get('ROS_LASER_FRAME', 'laser')
    
    # ===== Package directories =====
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    slam_toolbox_dir = get_package_share_directory('slam_toolbox')
    
    # Nav2 configuration - 통합된 파일 사용
    slam_params_file = os.path.join(slam_toolbox_dir, 'config', 'mapper_params_online_async.yaml')
    nav2_params_file = os.path.join(bringup_package_path, 'config', 'nav2_params_universal.yaml')
    
    # ===== Helper function for remappings =====
    def get_remappings(topic_mappings):
        """Create remapping list only for topics that differ from defaults"""
        remappings = []
        for default, actual in topic_mappings:
            if default != actual:
                remappings.append((default, actual))
        return remappings if remappings else None
    
    # Create remapping lists
    slam_remappings = get_remappings([
        ('/scan', scan_topic),
        ('/odom', odom_topic)
    ])
    
    controller_remappings = get_remappings([
        ('/odom', odom_topic),
        ('/cmd_vel', cmd_vel_topic)
    ])
    
    behavior_remappings = get_remappings([
        ('/cmd_vel', cmd_vel_topic)
    ])
    
    # ===== Declare Launch Arguments FIRST =====
    declare_robot_mode_arg = DeclareLaunchArgument(
        'robot_mode',
        default_value='real_robot',
        description='Robot mode: real_robot or isaac_sim'
    )
    
    declare_use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )
    
    declare_slam_enabled_arg = DeclareLaunchArgument(
        'slam_enabled',
        default_value='true',
        description='Enable SLAM toolbox'
    )
    
    declare_slam_mode_arg = DeclareLaunchArgument(
        'slam_mode',
        default_value='mapping',
        description='SLAM mode: mapping or localization'
    )
    
    declare_map_file_arg = DeclareLaunchArgument(
        'map_file',
        default_value='',
        description='Map file for localization mode'
    )
    
    declare_nav_enabled_arg = DeclareLaunchArgument(
        'nav_enabled',
        default_value='true',
        description='Enable Nav2 stack'
    )
    
    declare_autostart_nav_arg = DeclareLaunchArgument(
        'autostart_nav',
        default_value='true',
        description='Auto-start Nav2 nodes'
    )
    
    declare_use_sensors_arg = DeclareLaunchArgument(
        'use_sensors',
        default_value='true',
        description='Include sensor drivers (real robot only)'
    )
    
    declare_use_ouster_arg = DeclareLaunchArgument(
        'use_ouster',
        default_value='true',
        description='Use Ouster LiDAR'
    )
    
    declare_use_realsense_arg = DeclareLaunchArgument(
        'use_realsense',
        default_value='true',
        description='Use RealSense camera'
    )
    
    declare_use_tf_bridge_arg = DeclareLaunchArgument(
        'use_tf_bridge',
        default_value='true',
        description='Use TF bridge for Isaac Sim'
    )
    
    declare_namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='Robot namespace'
    )
    
    # ===== LaunchConfiguration 객체 생성 =====
    # DeclareLaunchArgument 이후에 생성해야 함
    robot_mode = LaunchConfiguration('robot_mode')
    use_sim_time = LaunchConfiguration('use_sim_time')
    slam_enabled = LaunchConfiguration('slam_enabled')
    slam_mode = LaunchConfiguration('slam_mode')
    map_file = LaunchConfiguration('map_file')
    nav_enabled = LaunchConfiguration('nav_enabled')
    autostart_nav = LaunchConfiguration('autostart_nav')
    use_sensors = LaunchConfiguration('use_sensors')
    use_ouster = LaunchConfiguration('use_ouster')
    use_realsense = LaunchConfiguration('use_realsense')
    use_tf_bridge = LaunchConfiguration('use_tf_bridge')
    namespace = LaunchConfiguration('namespace')
    
    # ===== Mode detection - 올바른 PythonExpression 사용 =====
    is_isaac_sim = PythonExpression(["'", robot_mode, "' == 'isaac_sim'"])
    is_real_robot = PythonExpression(["'", robot_mode, "' == 'real_robot'"])
    
    # ===== TF Bridge (Isaac Sim Mode) - 수정된 조건문 =====
    tf_bridge_group = GroupAction(
        condition=IfCondition(
            PythonExpression([
                "'", robot_mode, "' == 'isaac_sim' and '", 
                use_tf_bridge, "' == 'true'"
            ])
        ),
        actions=[
            LogInfo(msg='Starting TF Bridge for Isaac Sim...'),
            ExecuteProcess(
                cmd=[
                    'python3', os.path.join(bringup_package_path, 'scripts', 'isaac_bridge.py'),
                    '--ros-args', 
                    '-p', ['use_sim_time:=', use_sim_time]
                ],
                output='screen',
                name='tf_bridge'
            )
        ]
    )
    
    # ===== Sensor Drivers (Real Robot Only) =====
    sensor_group = GroupAction(
        condition=IfCondition(
            PythonExpression([
                "'", use_sensors, "' == 'true' and '", 
                robot_mode, "' == 'real_robot'"
            ])
        ),
        actions=[
            LogInfo(msg='Including sensor drivers for real robot...'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource('/root/robot_bringup_sensors.launch.py'),
                launch_arguments={
                    'use_sim_time': use_sim_time,
                    'use_ouster': use_ouster,
                    'use_realsense': use_realsense,
                }.items()
            )
        ]
    )
    
    # ===== Clearpath Platform (Real Robot Only) =====
    clearpath_group = GroupAction(
        condition=IfCondition(is_real_robot),
        actions=[
            LogInfo(msg='Starting Clearpath platform services...'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource('/etc/clearpath/launch/robot.launch.py'),
                launch_arguments={
                    'setup_path': '/etc/clearpath',
                    'use_sim_time': use_sim_time,
                }.items()
            )
        ]
    )
    
    # ===== SLAM Toolbox Node - 수정된 파라미터 =====
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            slam_params_file,
            {
                'use_sim_time': is_isaac_sim,  # PythonExpression 직접 사용
                'mode': slam_mode,
                'scan_topic': scan_topic,
                'map_frame': map_frame,
                'base_frame': base_frame,
                'odom_frame': odom_frame,
                'resolution': 0.05,
                'max_laser_range': 20.0,
                'scan_queue_size': 200,
                'transform_timeout': 2.0,
                'tf_buffer_duration': 60.0,
                'minimum_travel_distance': 0.0,
                'minimum_travel_heading': 0.0,
                'scan_buffer_size': 10,
                'scan_buffer_maximum_scan_distance': 10.0,
                'link_match_minimum_response_fine': 0.1,
                'link_scan_maximum_distance': 1.5,
                'loop_match_minimum_chain_size': 10,
                'loop_match_maximum_variance_coarse': 3.0,
                'loop_match_minimum_response_coarse': 0.35,
                'loop_match_minimum_response_fine': 0.45,
                'correlation_search_space_dimension': 0.5,
                'correlation_search_space_resolution': 0.01,
                'correlation_search_space_smear_deviation': 0.1,
                'loop_search_space_dimension': 8.0,
                'loop_search_space_resolution': 0.05,
                'loop_search_space_smear_deviation': 0.03,
                'loop_search_maximum_distance': 3.0,
                'stack_size_to_use': 40000000,
                'enable_interactive_mode': True,
            }
        ],
        remappings=slam_remappings,
        condition=IfCondition(slam_enabled)
    )
    
    # ===== Navigation2 Stack =====
    nav2_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'autostart': autostart_nav,
            'params_file': nav2_params_file,
            'map_subscribe_transient_local': 'true',
            'namespace': namespace,
        }.items(),
        condition=IfCondition(nav_enabled)
    )
    
    # ===== Auto Initial Pose Setter =====
    auto_init_pose_process = ExecuteProcess(
        cmd=[
            'python3', os.path.join(bringup_package_path, 'scripts', 'auto_init_pose.py') , 
            '--ros-args',
            '-p', ['use_sim_time:=', use_sim_time]
        ],
        output='screen',
        name='auto_init_pose',
        condition=IfCondition(nav_enabled)
    )
    
    # ===== Static Transform Publisher =====
    static_tf_node = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_laser_to_base',
        arguments=['0', '0', '0.5', '0', '0', '0', base_frame, laser_frame],
        parameters=[{'use_sim_time': is_isaac_sim}],
        condition=IfCondition(
            PythonExpression([
                "'", robot_mode, "' == 'real_robot' and '", 
                use_ouster, "' == 'true'"
            ])
        )
    )
    
    # ===== Log Messages =====
    startup_log = LogInfo(msg=[
        '\n========================================\n',
        'Robot Bringup Configuration:\n',
        '  Mode: ', robot_mode, '\n',
        '  Use Sim Time: ', use_sim_time, '\n',
        '  SLAM: ', slam_enabled, ' (', slam_mode, ')\n',
        '  Nav2: ', nav_enabled, '\n',
        '  TF Bridge: ', use_tf_bridge, '\n',
        f'  Scan topic: {scan_topic}\n',
        f'  Odom topic: {odom_topic}\n',
        f'  Cmd vel topic: {cmd_vel_topic}\n',
        '========================================\n'
    ])
    
    completion_log = LogInfo(msg=[
        '\n========================================\n',
        'Robot Bringup Complete!\n',
        '  Mode: ', robot_mode, '\n',
        '  Use Sim Time: ', use_sim_time, '\n',
        '  All systems ready!\n',
        '\nTo visualize:\n',
        '  ros2 run rviz2 rviz2\n',
        '========================================\n'
    ])
    
    # ===== Build and return LaunchDescription =====
    return LaunchDescription([
        # 1. Declare all arguments first
        declare_robot_mode_arg,
        declare_use_sim_time_arg,
        declare_slam_enabled_arg,
        declare_slam_mode_arg,
        declare_map_file_arg,
        declare_nav_enabled_arg,
        declare_autostart_nav_arg,
        declare_use_sensors_arg,
        declare_use_ouster_arg,
        declare_use_realsense_arg,
        declare_use_tf_bridge_arg,
        declare_namespace_arg,
        
        # 2. Startup log
        startup_log,
        
        # 3. TF Bridge (1초 후 시작)
        TimerAction(
            period=1.0,
            actions=[tf_bridge_group]
        ),
        
        # 4. Sensor drivers and Clearpath platform (2초 후)
        TimerAction(
            period=2.0,
            actions=[sensor_group, clearpath_group]
        ),
        
        # 5. SLAM Toolbox (적절한 딜레이 후)
        TimerAction(
            period=PythonExpression([
                "8.0 if '", robot_mode, "' == 'real_robot' else 3.0"
            ]),
            actions=[
                GroupAction(
                    condition=IfCondition(slam_enabled),
                    actions=[
                        LogInfo(msg=[
                            'Starting SLAM Toolbox:\n',
                            '  Mode: ', slam_mode, '\n',
                            f'  Scan topic: {scan_topic}\n',
                            f'  Odom topic: {odom_topic}\n'
                        ]),
                        slam_toolbox_node
                    ]
                )
            ]
        ),
        
        # 6. Navigation2 (SLAM 이후)
        TimerAction(
            period=PythonExpression([
                "12.0 if '", robot_mode, "' == 'real_robot' else 6.0"
            ]),
            actions=[
                GroupAction(
                    condition=IfCondition(nav_enabled),
                    actions=[
                        LogInfo(msg='Starting Navigation2 stack...'),
                        nav2_include
                    ]
                )
            ]
        ),
        
        # 7. Auto Initial Pose (Nav2 이후)
        TimerAction(
            period=PythonExpression([
                "15.0 if '", robot_mode, "' == 'real_robot' else 8.0"
            ]),
            actions=[
                GroupAction(
                    condition=IfCondition(nav_enabled),
                    actions=[
                        LogInfo(msg='Setting initial pose automatically...'),
                        auto_init_pose_process
                    ]
                )
            ]
        ),
        
        # 8. Static transforms
        static_tf_node,
        
        # 9. Completion message
        TimerAction(
            period=PythonExpression([
                "20.0 if '", robot_mode, "' == 'real_robot' else 10.0"
            ]),
            actions=[completion_log]
        ),
    ])