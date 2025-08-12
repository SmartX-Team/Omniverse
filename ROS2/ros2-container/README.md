# ReadMe.md: Isaac Sim (Host) - Container-based ROS 2 Humble Docker Integration Guide

## 1. OverView

This document guides you through setting up a stable communication environment between NVIDIA Isaac Sim (running on host machine) and ROS 2 Humble Docker containers. Using the provided Dockerfile, entrypoint.sh, fastdds_force_udp.xml, and other code files, the goal is to configure and operate a ROS 2 environment based on Docker containers that Isaac Sim publishes.
Pre-built Docker container path: docker pull ttyy441/ros2-container

## 2. Changelog
### v0.5.x (Current) - August 2025
**Major Update: SLAM & Navigation Integration**
* Integrated Nav2 navigation stack with full autonomous navigation capabilities
* Added SLAM Toolbox for real-time mapping and localization
* Restructured project with modular `src/` and `standalone_scripts/` directories
* Added Kafka integration for real-time data streaming
* Introduced `AUTO_LAUNCH` environment variable for automatic bringup
* Added `nav2_params_universal.yaml` for Nav2 stack configuration
* Implemented auto initial pose setter for quick localization
* **Note**: SLAM and Navigation features currently tested only in Isaac Sim environment

### v0.4.x - April 2025
**Unified Control System**
* Implemented single-parameter mode selection for both Isaac Sim and real robot control
* Added `isaac_sim` and `real_robot` modes in entrypoint.sh
* Unified launch system through `robot_bringup.launch.py`
* Simplified Docker run commands with mode parameter


## 3. Prerequisites

### 3.1. Host Machine Environment

- **OS:** Ubuntu 22.04 LTS recommended
- **NVIDIA Isaac Sim:** I tested Isaac-sim 4.5 ;
- **Docker Engine:** Latest version installed
- **NVIDIA Driver:** Tested on version 535
- **NVIDIA Container Toolkit:** If you want using this container in the Isaac-sim, You must need install toolkit 

```
ros2-container <project_root>/
├── Dockerfile                    # Multi-stage Docker build configuration
├── entrypoint.sh                # Container startup script with mode selection
├── README.md                     # English documentation
├── README.kr.md                  # Korean documentation
├── requirements.txt              # Python dependencies
├── simple_subscriber.py          # Test script for Isaac Sim data validation deprecated
│
├── src/                          # ROS2 workspace source
│   └── husky_isaac_bringup/     # Main ROS2 package
│       ├── config/               # Configuration files
│       │   ├── driver_params.yaml           # Sensor driver parameters
│       │   ├── fastdds_force_udp.xml       # DDS configuration for Isaac Sim
│       │   ├── nav2_params_universal.yaml  # Nav2 stack parameters [NEW]
│       │   ├── ouster_param.yaml           # Ouster LiDAR configuration
│       │   └── robot.yaml                  # Husky robot hardware definition
│       │
│       ├── launch/               # ROS2 launch files
│       │   ├── robot_bringup.launch.py          # Main robot bringup
│       │   └── robot_bringup_sensors.launch.py  # Sensor-specific bringup
│       │
│       ├── scripts/              # Python executable scripts
│       │   ├── auto_init_pose.py   # Automatic initial pose setter [NEW]
│       │   ├── isaac_bridge.py     # Isaac Sim <-> ROS2 bridge
│       │   └── __init__.py
│       │
│       ├── resource/             # Package resources
│       │   └── husky_isaac_bringup
│       │
│       ├── package.xml           # ROS2 package manifest
│       └── setup.py              # Python package setup
│
└── standalone_scripts/          # Independent utility scripts [NEW]
    ├── controller/               # Robot control utilities
    │   ├── inyong_joystick.py     # Custom joystick controller
    │   └── sync_mode_kafka.py     # Kafka-based synchronization
    │
    └── data/                    # Data pipeline utilities
        ├── bag_collector_to_kafka.py      # ROS bag to Kafka streaming
        ├── pointcloud_to_kafka.py         # Point cloud data streaming
        └── ros2_camera_to_kafka_agent.py  # Camera feed streaming
```

## 4. Setup and Execution Procedures

### 4.1. Dockerfile
The provided Dockerfile consists of two stages (builder, runtime) and sets up all environments necessary for Husky A200 operation and Isaac Sim, Ouster LiDAR integration.
Note: The robot-related packages for the currently used Husky UGV Clearpath are continuously changing in structure, so please be aware that they may differ from the structure I originally wrote.
Key Installation Packages (Runtime Stage):

ros-humble-clearpath-robot: Core meta-package for Husky A200 operation. This package automatically installs most essential dependencies including ros-humble-clearpath-hardware-interfaces, ros-humble-clearpath-control, ros-humble-clearpath-description, ros-humble-clearpath-msgs, ros-humble-clearpath-sensors, ros-humble-clearpath-generator-robot, etc.
ros-humble-clearpath-simulator: Simulation-related tools (optional inclusion possible)
ros-humble-clearpath-config: Configuration-related tools such as robot.yaml processing
ros-humble-clearpath-generator-common: Common configuration generation tools
ros-humble-robot-upstart: System service-related utilities (meaningful for script provision rather than direct service registration in containers)
ros-humble-xacro: Required for URDF processing

### 4.2 entrypoint.sh
Core script executed when the container starts.

Mode Selection: You can select isaac_sim (or isaac_sim_default) or real_robot mode as the first argument when running docker run. Default value is isaac_sim_default.
Environment Sourcing: Sources necessary setup.bash files in order according to the selected mode.

Common: /opt/ros/humble/setup.bash
isaac_sim mode: Isaac Sim workspace's setup.bash
real_robot mode: /etc/clearpath/setup.bash (Clearpath generated environment), Ouster workspace setup.bash (if exists)

real_robot Mode Auto-execution and Configuration:

MCU Serial Port Symbolic Link Creation: For communication with Husky MCU, automatically creates a symbolic link connecting the host's /dev/ttyUSB0 (or actual connected device name) to /dev/clearpath/prolific inside the container. This prepares for cases where the A200Hardware interface uses hardcoded paths.

#### !!! Please pay attention to modifying this section if serial port numbers change or additional work like joystick connections is added later


### 4.3. Configuration Files

robot.yaml: Located at /etc/clearpath/robot.yaml, defines all hardware configurations of the robot including robot namespace, controller type, mounted sensors and accessories. Clearpath generator scripts reference this file to generate other configurations. This is a very important file. → When installing additional accessories or sensors to Husky URDF, modify this file and rebuild.

fastdds_force_udp.xml: Although the default setting is FastDDS, this is a FastDDS profile that forces UDP usage for stability during DDS communication between Isaac Sim and ROS 2.
ouster_driver_params.yaml: Defines parameters needed when using Ouster LiDAR.



### 5. Preparing Isaac Sim Execution Environment on Host Machine

Although containerized, it's still recommended to perform environment setup work on the host machine where the container runs.
Especially when controlling physical UGV with joysticks or MCU serial ports, you need to check port numbers and reflect them in the container.
Before running Isaac Sim, set the following environment variables in the host terminal that will start Isaac Sim. This ensures Isaac Sim's FastDDS uses the provided XML profile (force UDP) and uses the correct RMW implementation.


```

Complete example with SLAM and Navigation enabled:

sudo docker run -it --rm \
    --name ros \
    --network host \
    --ipc=host \
    --privileged \
    --device=/dev/dri:/dev/dri \
    -e ROS_CMD_VEL_TOPIC=/cmd_vel \
    -e ROS_POINTCLOUD_TOPIC=/pointcloud \
    -e ROS_IMU_TOPIC=/imu/virtual \
    -e ROS_BASE_FRAME=base_link \
    -e ROS_LASER_FRAME=lidar_link \
    -e AUTO_LAUNCH=false \
    -e ROS_DOMAIN_ID=1 \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -e XAUTHORITY=$XAUTHORITY \
    -v $XAUTHORITY:$XAUTHORITY:rw \
    -v ~/ros2_maps:/root/maps \
    --security-opt label=disable \
    docker.io/ttyy441/ros2-container:0.5.5 \
    isaac_sim


Environment Variables for SLAM and Navigation:
The following environment variables are required when enabling SLAM and Navigation capabilities:


-e ROS_CMD_VEL_TOPIC=/cmd_vel      # Velocity command topic for robot control
-e ROS_POINTCLOUD_TOPIC=/pointcloud # Point cloud topic from LiDAR sensor
-e ROS_IMU_TOPIC=/imu/virtual      # IMU data topic for sensor fusion
-e ROS_BASE_FRAME=base_link        # Robot base frame for transformations
-e ROS_LASER_FRAME=lidar_link      # LiDAR frame for laser scan data
-e AUTO_LAUNCH=false                # Manual control of launch sequence


Display Configuration for GUI Applications:
The following options are required when running GUI applications (RViz2, controllers) from the host machine:

-e DISPLAY=$DISPLAY                 # X11 display variable passthrough
-v /tmp/.X11-unix:/tmp/.X11-unix:rw # X11 socket mounting for GUI rendering
-e XAUTHORITY=$XAUTHORITY           # X11 authentication token
-v $XAUTHORITY:$XAUTHORITY:rw       # Mount X11 auth file for display permissions


Additional Options:

--device=/dev/dri:/dev/dri - GPU acceleration for visualization
-v ~/ros2_maps:/root/maps - Mount host directory for saving/loading SLAM maps
--security-opt label=disable - Disable SELinux labeling (required on some systems)

```


```bash
 v0.4.x Container Execution (Deprecated)
 Note: The following commands are for v0.4.x containers. For current v0.5.x usage, see section 6.1 above.

# 호스트 터미널에서 실행

# 1. FASTRTPS_DEFAULT_PROFILES_FILE 환경 변수 설정
#    <project_root>를 실제 코드가 위치한 경로로 변경주의 ; SV4000 #1 PC에는 이미 설정해둠
export FASTRTPS_DEFAULT_PROFILES_FILE="<project_root>/fastdds_force_udp.xml"

# 2. RMW_IMPLEMENTATION 환경 변수 설정
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp


컨테이너 필수 파라미터:

docker run -it --rm \
    --network host \
    --ipc=host \
    --privileged \
    isaac_sim_ros2_link_app


그 외 아이작심 내 가상 UGV 컨트롤 모드

docker run -it --rm \
    --network host \
    --ipc=host \
    --privileged \
    -e QT_X11_NO_MITSHM=1 \
    -e DISPLAY=$DISPLAY \
    -e SDL_VIDEODRIVER=x11 \
    -e "ROS_DOMAIN_ID=0" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
ttyy441/ros2-container:0.5.0 \
isaac_sim

# Launch robot bringup directly
docker run -it --rm \
    --network host \
    --ipc=host \
    --privileged \
    -e DISPLAY=$DISPLAY \
    -e ROS_DOMAIN_ID=20 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    --device=/dev:/dev \
    ttyy441/ros2-container:0.5.0 \
    real_robot ros2 launch /root/robot_bringup.launch.py


##### If you made other bring up then Complete real robot control setup
docker run -it --rm \
    --network host \
    --ipc=host \
    --privileged \
    -e DISPLAY=$DISPLAY \
    -e ROS_DOMAIN_ID=20 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    --device=/dev:/dev \
    ttyy441/ros2-container:0.5.0 \
    real_robot <here>
```

6. Testing Commands Inside Container
Test Isaac Sim integration with these commands:
bash# List available ROS 2 topics
ros2 topic list

### Monitor point cloud data from Isaac Sim
ros2 topic echo /pointcloud

### Check robot status (for real robot mode)
ros2 topic echo /robot_status

### Monitor joint states
ros2 topic echo /joint_states

Serial Port Access: Ensure /dev/ttyUSB0 or relevant device is accessible and has proper permissions
ROS Domain ID: Make sure ROS_DOMAIN_ID matches between host Isaac Sim and container
Network Configuration: Use --network host for simplest setup
Device Access: Use --device=/dev:/dev for full hardware access in real robot mode