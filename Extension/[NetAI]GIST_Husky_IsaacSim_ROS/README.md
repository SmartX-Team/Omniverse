# GIST Husky Isaac Sim Net-AI ROS Extension

<div align="center">



*Seamless simulation-to-reality robot control for Clearpath Husky UGV*

</div>

## 🚀 Overview

This extension provides a comprehensive interface for controlling Clearpath's Husky UGV robot within Nvidia Isaac Sim 4.5, enabling seamless simulation-to-reality transfer. Originally developed by Niki C. Zils in 2024, the extension has been extensively refactored and enhanced by Inyong Song for Isaac Sim 4.5 compatibility and real-world synchronization.

### ✨ Key Features

- **🎯 Real-time Robot Control**: Direct control interface matching physical Husky behavior
- **📡 Advanced Sensor Integration**: Camera, LiDAR, IMU sensor management with realistic physics
- **🔗 ROS2 Integration**: Full ROS2 Humble compatibility with topic publishing/subscribing
- **🏗️ Modular Architecture**: Clean, extensible codebase for easy customization
- **🚀 Isaac Sim 4.5 Optimized**: Latest Isaac Sim features and performance improvements
- **🐳 Container Ready**: Pre-built Isaac Sim 4.5 (Included Ros2 build) + ROS2 Docker container available
- **🎮 Unified Control Scripts**: Standalone scripts for controlling both virtual and physical robots simultaneously
- **☁️ Kafka Data Streaming**: Multi-robot data management with K8S-based datalake integration
- **🔄 Simulation-Reality Sync**: Seamless control synchronization between Isaac Sim and real Husky robots

### 🏛️ System Architecture

This extension encompasses a complete ecosystem for Husky robot simulation and control:

- **Isaac Sim Integration**: Realistic Husky setup with physics-accurate simulation
- **Unified Robot Control**: Single interface controlling both virtual (Isaac Sim) and physical Husky robots simultaneously
- **Multi-Robot Management**: Kafka-based data streaming supporting multiple robot instances
- **Enterprise Data Pipeline**: Integration with K8S-based datalake for scalable data management
- **Ecosystem Connectivity**: Seamless connections between simulation, real robots, and cloud infrastructure

![System Architecture](docs/Extension_System.png)

## 🏗️ Development History

| Period | Developer | Contribution |
|--------|-----------|-------------|
| **2024** | **Niki C. Zils** (German Intern) | Initial development and core framework for GIST |
| **2025~** | **Inyong Song** | Major refactoring for Isaac Sim 4.5, enhanced real-world synchronization |

## 📋 Prerequisites

### 🥇 Recommended Setup (Container)
**Isaac Sim 4.5 + ROS2 Pre-built Container** *(Recommended)*

We provide a pre-configured Docker container with Isaac Sim 4.5 and ROS2 Humble already built and optimized:
- ✅ Isaac Sim 4.5 with ROS2 Bridge enabled
- ✅ All ROS2 dependencies pre-installed
- ✅ Optimized for Husky simulation-to-reality control
- ✅ Ready-to-use development environment

```bash
# Pull the pre-built container (coming soon)
docker pull gist-netai/isaac-sim-ros2:4.5-humble

# Run the container
docker run -it --gpus all \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  gist-netai/isaac-sim-ros2:4.5-humble
```

Isaac-sim Conatiner :

https://github.com/SmartX-Team/DT-containerized


ROS2 container :

https://github.com/SmartX-Team/Omniverse/tree/main/ROS2/ros2-container

build docker images:



### 🔧 Manual Installation (Alternative)

If you prefer or need to install manually in your environment:

**System Requirements**
- **Isaac Sim**: 4.5 or later
- **ROS2**: Humble distribution  
- **Python**: 3.8 or later
- **CUDA**: Compatible GPU with CUDA support
- **Docker**: Optional but recommended

**Dependencies**
```bash
# ROS2 Humble installation
sudo apt install ros-humble-desktop-full

# Additional ROS2 packages
sudo apt install ros-humble-ackermann-msgs \
                 ros-humble-sensor-msgs \
                 ros-humble-geometry-msgs \
                 ros-humble-nav-msgs \
                 ros-humble-tf2-ros
```

## 🛠️ Installation

### Method 1: Direct GitHub Integration (Hot Reload)

1. **Open Isaac Sim 4.5** with ROS2 Bridge enabled

2. **Add Extension Search Path**
   - Navigate to **Window → Extensions**
   - Click **☰ (Hamburger Menu) → Settings → Extension Search Path**
   - Click the **+** button in the edit column
   - Add this GitHub link:
   ```
   git://github.com/SmartX-Team/Omniverse.git?branch=main&dir=Extension/[NetAI]GIST_Husky_IsaacSim_ROS/exts
   ```
   - This enables hot reloading when GitHub updates

3. **Enable Extension**
   - Search for "NetAI GIST Husky" in the Extension Manager
   - Enable the extension (should appear in Third Party tab)

### Method 2: Local Installation

1. **Download Extension**
   ```bash
   git clone https://github.com/SmartX-Team/Omniverse.git
   cd Omniverse/Extension/[NetAI]GIST_Husky_IsaacSim_ROS
   ```

2. **Add Local Path**
   - In Isaac Sim: **Window → Extensions → ☰ → Settings → Extension Search Path**
   - Add the full path to the `exts` folder
   - Enable hot reloading for local development

3. **Configure ROS2 Environment**
   ```bash
   source /opt/ros/humble/setup.bash
   export ROS_DOMAIN_ID=0  # Adjust as needed
   ```

## 🎮 Usage

### Quick Start

1. **Launch Extension**
   - Open Isaac Sim 4.5 with ROS2 Bridge enabled
   - Ensure the extension is enabled in Extension Manager
   - Extension UI will appear in the main window

2. **Initialize Husky Robot**
   - Click **"Initialize Husky"** button in the extension panel
   - Robot model loads with all sensors (Camera, LiDAR, IMU) attached
   - Physics simulation begins automatically

3. **Enable ROS2 Communication**
   - Click **"Start ROS2 Bridge"** 
   - Extension establishes ROS2 topic connections
   - Verify topics with: `ros2 topic list`

4. **Control Options**
   - **Extension UI**: Use built-in control buttons
   - **ROS2 Commands**: Publish to `/ackermann_cmd` topic
   - **COSMO Mode**: Tank-style controller interface
   - **Virtual Joystick**: 4-wheel velocity control

### 🕹️ Control Modes

#### Manual Control (Extension UI)
- **Pilot Forward/Backward**: Basic movement controls
- **Steering**: Left/right turn commands  
- **Emergency Stop**: Immediate cessation of movement
- **Reset Position**: Return robot to origin

#### ROS2 Topic Control
```bash
# Primary control method - Velocity commands
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist '{
  linear: {x: 1.0, y: 0.0, z: 0.0},
  angular: {x: 0.0, y: 0.0, z: 0.5}
}'
```

> **Note**: The original `ackermann_cmd` interface from Niki's implementation has been deprecated. Current version uses `cmd_vel` for all robot control. For legacy ackermann functionality, refer to the archived original implementation in the deprecated section.

#### inyong joystick
- Activate **"Start COSMO Mode"** for cme_vel

You can adjust your robot speed ;

### 📡 ROS2 Topic Interface

#### Published Topics
| Topic | Type | Description |
|-------|------|-------------|
| `/husky/camera/image_raw` | `sensor_msgs/Image` | RGB camera feed |
| `/husky/camera/depth` | `sensor_msgs/Image` | Depth camera data |
| `/husky/lidar/scan` | `sensor_msgs/LaserScan` | LiDAR point cloud |
| `/husky/imu/data` | `sensor_msgs/Imu` | IMU sensor data |
| `/husky/odom` | `nav_msgs/Odometry` | Robot odometry |
| `/husky/joint_states` | `sensor_msgs/JointState` | Wheel joint states |

#### Subscribed Topics  
| Topic | Type | Description |
|-------|------|-------------|
| `/cmd_vel` | `geometry_msgs/Twist` | **Primary control interface** - Velocity commands |
| `/husky/joint_commands` | `sensor_msgs/JointState` | Direct joint control |

> **Deprecated**: `/ackermann_cmd` (ackermann_msgs/AckermannDriveStamped) - See archived Niki's original implementation for legacy support

### 🔧 Standalone Scripts

> **Note**: These are newly developed standalone utilities by Inyong Song, replacing the original framework.


#### Data Management Scripts
```bash
# Script 1
python3 Standalone_Scripts/[script_name].py

# Script 2  
python3 Standalone_Scripts/[script_name].py
```
*[Description to be added]*

## 🏗️ Extension Structure

```
Extension/
└── [NetAI]GIST_Husky_IsaacSim_ROS/
    ├── .vscode/                     # VS Code configuration
    └── exts/
        └── gist.husky.isaacsim_ros/
            ├── config/              # Extension appearance & tracking
            ├── data/                # Assets and images (.png files)
            ├── docs/                # Documentation and changelog
            └── gist/
                └── husky/
                    └── isaacsim_ros/
                        ├── __pycache__/         # Python cache
                        ├── Standalone_Scripts/  # Independent control scripts
                        │   ├── inyong_joystick_to_kafka.py
                        │   ├── inyong_joystick.py
                        │   ├── kafka_data_saver.py
                        │   └── kafka_data_reader.py
                        ├── __init__.py          # Package initialization
                        ├── actions.py           # Action implementations
                        ├── camera_publishers.py # Camera data publishing
                        ├── extension.py         # Extension lifecycle & UI
                        ├── ros_listeners.py     # ROS2 subscription handling
                        ├── sensors.py           # Sensor management
                        └── utils.py             # Utility functions
```

### 📁 Directory Overview

| Directory/File | Description |
|----------------|-------------|
| `config/` | Extension metadata for Isaac Sim recognition |
| `data/` | System architecture diagrams and assets |
| `docs/` | README files and development changelog |
| `Standalone_Scripts/` | Independent utilities (COSMO, joystick, Kafka) |
| `extension.py` | Main extension class and UI management |
| `actions.py` | Robot control logic and button implementations |
| `sensors.py` | Camera, LiDAR, IMU creation and configuration |
| `ros_listeners.py` | ROS2 topic subscription and command processing |
| `camera_publishers.py` | Camera data streaming to ROS2 topics |
| `utils.py` | Common functions and helper utilities |

## 🔧 Configuration

Edit `config.py` to customize:

```python
# Robot configuration
HUSKY_USD_PATH = "/path/to/husky.usd"
ROBOT_NAMESPACE = "husky"

# ROS2 settings
ROS_DOMAIN_ID = 0
ACKERMANN_TOPIC = "/ackermann_cmd"
CAMERA_TOPIC = "/husky/camera/image_raw"

# Sensor parameters
CAMERA_RESOLUTION = (1920, 1080)
LIDAR_RANGE = 30.0
IMU_FREQUENCY = 100.0
```

## 🤖 Integration with Physical Husky

### Simulation-to-Reality Synchronization

This extension supports seamless control of both simulated and physical Husky robots:

1. **Network Configuration**
   ```bash
   # Set ROS_DOMAIN_ID to match between simulation and robot
   export ROS_DOMAIN_ID=0
   
   # Configure robot network (on physical Husky)
   export ROS_MASTER_URI=http://ROBOT_IP:11311
   export ROS_IP=ROBOT_IP
   ```

2. **Launch Physical Robot**
   ```bash
   # On the physical Husky robot
   roslaunch husky_bringup husky_bringup.launch
   
   # Bridge ROS1 to ROS2 (if needed)
   ros2 run ros1_bridge dynamic_bridge
   ```

3. **Enable Dual Control**
   - Activate **"Real Robot Sync"** mode in extension
   - Commands sent in Isaac Sim automatically mirror to physical robot
   - Real-time sensor data flows bidirectionally

### Safety Features
- **Emergency Stop**: Immediate halt for both sim and real robot
- **Latency Monitoring**: Real-time communication delay tracking  
- **Failsafe Modes**: Automatic fallback if connection lost
- **Collision Avoidance**: Shared safety protocols between environments

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **GIST (Gwangju Institute of Science and Technology)** - Research institution where Inyong Song completed his Master's degree and Niki C. Zils conducted his internship program, providing the foundation and support for this robotics research
- **Niki C. Zils** for the initial development and foundation
- **Clearpath Robotics** for the Husky platform
- **NVIDIA** for Isaac Sim and robotics simulation tools
- **Open Robotics** for ROS2 framework

## 📞 Contact & Support

- **Current Maintainer**: Inyong Song (Net-AI Lab)
- **Institution**: GIST Net-AI Team
- **Issues**: Please use GitHub Issues for bug reports and feature requests

---

<div align="center">
<i>Built with ❤️ for the robotics community</i>
</div>