"""
This launch file is designed to bring up various sensors within a ROS2 environment.
It includes configurations for an Ouster LiDAR and an Intel RealSense camera.
Depending on the specific sensors installed and their requirements,
you may need to modify the launch arguments or include/exclude certain sensor configurations.

InYong Song

"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
    # 1. Ouster LiDAR ROS2 Node Create Exec
    ouster_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('ouster_ros'), 'launch'),
            '/driver.launch.py'
        ]),
        launch_arguments={
            'params_file': '/configs/ouster_driver_params.yaml',
            'viz': 'false'
        }.items()
    )

    # 2. Intel RealSense ROS2 Node Create Exec
    #
    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('clearpath_sensors'), 'launch'),
            '/intel_realsense.launch.py'
        ]),
        # 포인트클라우드 데이터를 발행하도록 설정합니다.
        launch_arguments={'pointcloud.enable': 'true'}.items()
    )

    # 3. Execute the launch description
    return LaunchDescription([
        ouster_launch,
        realsense_launch
    ])