# Standalone Scripts
These are scripts that are not necerally needed to run the extension, but can be used to extend the capabilities of it.
They are also not activated automatically by the program, due to them
- potenatlly being CPU/ GPU expensive.
- creating hughe amounts of data that could overflow the targeted systems.
- straying to far away from the goal of the extension.

There as of right now only two typed of standalone scripts included in this extension:
- Movement oriented scripts (e.g. Tank Controller COSMO, Joystick)
- Data management oriented scripts (e.g. ROS2 Kafka Publisher/Reader)

### How to use them
For easier usage move/copy all included scripts to a folder/point of easy access (`e.g. ~/scripts`).
Then make sure that all requirements of the individual scripts have been fullfiled.
In the case of the "Tank Controller Script - COSMO" pygame needs to be installed. (`pip3 install pygame`)

Afterwards open up a new terminal and move to the folder containg all the scripts.
In this case: `cd ~/scripts`

Now start up Isaac Sim and setup this extension if you have not done so beforehanded. (This only applies if you want to use the extensions with the scripts in tandem.)

Then source your local installation of ROS 2 Humble(other versions of ROS 2 have not been tested and likley won't work).
If you have build it from source: `~/ros2_humble/install/local_setup.bash`
If you have installed it from the debian package: `source /opt/ros/humble/setup.bash` [^1]

[^1] Please reference this link to install ROS 2 Humble: https://docs.ros.org/en/humble/Installation.html

At last, start the script that you want to run.
Python3: `python3 [NameOfScript]` [^2]

[^2] As an example, you could run the "Tank Controller Cosmo" like this: `python3 tank_controller_cosmo.py`

## Tank Controller Script - COSMO
This scripts emulates a tank controller that can be used for steering and controll Husky.

### Requirements
Python3 Libraries: pygame, time

All other things are optional:
- "rclpy and ackermann_msgs" for use in tandem with Isaac Sim and/or the real Husky
- "warnings" for warnings in Isaac Sim that appear on the Interface

### How to use
#### How to read the display
```
  __     __
 |  |   |  |   ^ Anything above denotes a positive (+) velocity
 |  |   |  |   |
 |██|   |██|  <- The dots start out here - They show the current speed of the left and right side
 |  |   |  |   |
 |__|   |__|   V Anything below means a negative (-) velocity
```

#### How it works
```
 As the main input source you use your mouse. (represented by this triangle: ▲)
 
  ____((______                                __     __
 |    _\\     |  With a left click the left  |  |   |  |
 |   |█|_|    |  wheel speed is determined.  |██| ▲ |  |
 |   |   |    |                              |  |   |██|
 |   |___|    |  Where as the right speed    |  |   |  |
 |____________|  stays untouched.            |__|   |__|
 
 
  ____((______                                __     __
 |    _\\     |  With a right click the      |  |   |  |
 |   |_|█|    |  rigth wheel speed is        |██|   |  |
 |   |   |    |  determined.                 |  |   |  |
 |   |___|    |  Where as the left speed     |  |   |  |
 |____________|  stays untouched.            |__| ▲ |██|
 
 
  ____((______                                __     __
 |    _\\     |  With a press on the mouse   |██| ▲ |██|
 |   |_█_|    |  wheel the speed on both     |  |   |  |
 |   |   |    |  sides gets changed to the   |  |   |  |
 |   |___|    |  same level.                 |  |   |  |
 |____________|                              |__|   |__|
 
 It's important to note that this controller won't send any signal until both sides have been changed at least once.
 
*TL;DR There also exist "Advanced Movement", which won't be explained here, since it requires additional buttons on the mouse.
Try experimenting, if you want to use them or search via (Ctrl+F) for "Advanced Movement" in the script.*
```
## Virtual Joystick - End Of Life (EOL)
This scripts emulates a joystick that can be used for adjusting the speed of all wheels at the same time.
It sadly is unable to turn on will with this script and the speed is set to high.

## Requirements
Python3 Libraries: pygame, time, rclpy, ackermann_msgs, math

## How to use
1. Start up the extension
2. Move the curser and click somewhere in the circle
3. The robot will move forward or backwards accordignly with how far up or down it is from the center of the circle


## ROS 2 Kafka Producer
This scripts publishes every second a PointCloud Data that it recives on the topic "/point_cloud_hydra" to Kafka.
While doing so it splits the data to upload the data, due to size limitations.

## Requirements
Python3 Libraries: time, rclpy, kafka, json, sensor_msgs

## How to use
1. Start up the extension
2. As soon as numbers are getting printed in the terminal the script is working (The number shows the amount of points published)

## ROS 2 Kafka Reader - Unfinished
This scripts reads out all the data that gets published to Kafka in real time and forwards it to the ROS 2 topic "/point_cloud_hydra".
This script was never tested...

## Requirements
Python3 Libraries: time, rclpy, kafka, json, sensor_msgs, threading

## How to use
1. Start up the extension
2. As soon as numbers are getting printed in the terminal the script is working (The number shows the amount of points recived)


# TODO - Scripts
- [ ] Write a script that converts ackermann into twist cmd, so that Husky can be moved IRL
- [ ] Update the Kafka reader, due to it being very unusable for its intended purpose
- [ ] Create another saving system that dosen't rely on Kafka