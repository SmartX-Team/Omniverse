# Changelog




- Deprecated version 

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


## [1.0.0] - 2021-04-26
- Initial version of extension UI template with a window

## [1.1.0] - 2024-07-18
- Creation of this test script to gain a deeper grasp on error messages in other extensions.

## [1.2.0] - 2024-08-01
- Added IMU (not working)
- Added LiDAR (working)
- Added Camera
- Started publishing data to ROS2 Humble topics

## [2.0.0] - 2024-08-08
- Two Buttons added (Pilot & Cease)
- Drive now creates a node graph that recives ackermann_msgs to drive the robot
- The new Pilot Button is the old "Drive" Button, enabling the robot to drive in an almost straight line
- The Cease Button stops Husky completly. If there is the wish to resume with either of the drive option they need
to be selected again.
- Refactored a great deal of the functions into their own files for oversight purposes
- Added a cute fox as an intro for the extension >.< (This is disable at the start...)

## [3.0.0] - 2024-08-13
- Added a Tankcontroller Script called CoSMo (Controlled simulated movement), which outputs two velocites in the 
/ackermann_cmd ros2 topic for the left and right drive train. This data can then be called by the appropriatly named
"Cosmo" function inside of Isaac Sim to move Husky with it. (Note: Jerk is missued as the second velocity in this case.)
- The old "Drive" Button was removed, due to it working only with a single controller. The code for it is still there.
- The resoulutions of the cameras were scaled down to enable a stable output of data. (Scalefactor: 1/4)
- Refactoring of the graph based node systems into their own file
- Typo fixes
- Patched: Reconfigured LiDAR to work while driving

## [4.0.0] - 2024-08-21
- Added to standalone scripts for saving to and loading LiDAR PointClouds from Kafka (1 PointCloud/second)
- Refactored all standalone scripts into their own folder and added a README.md
- Rewritten the README.md at the start of the extension for better understanding
- Added pictures to hopefully clarify the process
- Adjusted Tank Controller values



## [6.0.0] - 2025-08-10

Added

Multi-Robot Support with ROS2 Domain ID Configuration

Each robot can now operate on independent ROS2 Domain IDs (0-232)
Enables complete network isolation between robots for swarm/fleet operations
ROS2Context node integration for proper domain management


Enhanced UI for Multi-Robot Management

New "Multi-Robot ROS2 Domain Controller" interface
Domain ID input field for each robot (configurable per robot)
Automatic robot_id assignment (0, 1, 2...) for internal management
Real-time status display showing active domain configuration


Improved Graph Management

Dynamic graph path generation (/husky_ros_graph_{robot_id})
Create/Delete graph operations per robot
Proper cleanup on robot removal