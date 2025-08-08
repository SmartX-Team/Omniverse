#!/usr/bin/env python3
"""
Sensor Drivers Launch File
This file handles all physical sensor drivers for real robot mode
Separated to avoid package dependency issues in simulation mode

Author: InYong Song
Version: 1.0
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, 
    IncludeLaunchDescription,
    TimerAction,
    LogInfo
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.conditions import IfCondition

def generate_launch_description():
    # Launch Arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    use_ouster = LaunchConfiguration('use_ouster', default='true')
    use_realsense = LaunchConfiguration('use_realsense', default='true')
    
    # Configuration files
    ouster_params_file = '/configs/ouster_param.yaml'
    
    # Environment variables for topic remapping
    ouster_scan_topic = os.environ.get('ROS_SCAN_TOPIC', '/scan')
    camera_points_topic = os.environ.get('ROS_CAMERA_POINTS_TOPIC', '/camera/points')
    
    return LaunchDescription([
        # Declare arguments
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('use_ouster', default_value='true'),
        DeclareLaunchArgument('use_realsense', default_value='true'),
        
        # Log sensor configuration
        LogInfo(msg='=== Starting Physical Sensor Drivers ==='),
        LogInfo(msg=f'  Ouster enabled: {use_ouster.variable_name}'),
        LogInfo(msg=f'  RealSense enabled: {use_realsense.variable_name}'),
        LogInfo(msg=f'  Scan topic: {ouster_scan_topic}'),
        LogInfo(msg=f'  Camera points topic: {camera_points_topic}'),
        
        # Ouster LiDAR Driver
        TimerAction(
            period=2.0,
            actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource([
                        os.path.join(get_package_share_directory('ouster_ros'), 'launch'),
                        '/driver.launch.py'
                    ]),
                    launch_arguments={
                        'params_file': ouster_params_file,
                        'viz': 'false',
                        'use_sim_time': use_sim_time,
                    }.items(),
                    condition=IfCondition(use_ouster)
                ),
            ]
        ),
        
        # Topic relay for Ouster if needed
        Node(
            package='topic_tools',
            executable='relay',
            name='ouster_scan_relay',
            output='screen',
            arguments=['/ouster/scan', ouster_scan_topic],
            condition=IfCondition(use_ouster) if ouster_scan_topic != '/ouster/scan' else None
        ) if ouster_scan_topic != '/ouster/scan' else LogInfo(msg='Using default Ouster scan topic'),
        
        # RealSense Camera Driver
        TimerAction(
            period=5.0,
            actions=[
                Node(
                    package='realsense2_camera',
                    executable='realsense2_camera_node',
                    name='realsense_camera',
                    output='screen',
                    parameters=[{
                        'use_sim_time': use_sim_time,
                        'enable_color': True,
                        'enable_depth': True,
                        'enable_infra1': False,
                        'enable_infra2': False,
                        'enable_sync': True,
                        'align_depth.enable': True,
                        'pointcloud.enable': True,
                        'pointcloud.stream_filter': 2,  # depth only
                        'pointcloud.ordered_pc': False,
                        'depth_module.profile': '640x480x30',
                        'rgb_camera.profile': '640x480x30',
                    }],
                    remappings=[
                        ('/camera/depth/color/points', camera_points_topic),
                        ('/camera/depth/image_rect_raw', '/camera/depth/image'),
                        ('/camera/color/image_raw', '/camera/color/image'),
                    ],
                    condition=IfCondition(use_realsense)
                ),
            ]
        ),
        
        # Completion message
        TimerAction(
            period=8.0,
            actions=[
                LogInfo(msg='=== Sensor drivers initialization complete ==='),
            ]
        ),
    ])