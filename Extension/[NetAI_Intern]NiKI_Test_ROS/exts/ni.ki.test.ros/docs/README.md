# Test Ros [ni.ki.test.ros]

This extension was orignally created to be used as a test project in order to gain a deeper understanding of omniverse 
and its capiabilties. Furthermore it was deployed as a playground to prove concepts or test for error messages.
Later on it changed into a full-fleged extension, but due to keepsake the name was not changed.

As of now, it boots a variety of diffrent features that make it appeling for using it in combination with clearpath's
UAV Husky. These mentioned features are:

- Setting up Husky in Isaac Sim (Adjusting 3D Model Issues, etc.)
- Generating realistic Sensors (Camera, LiDAR, etc.)
- Handeling the data of these discuessed Sensors and publishing it to ROS2 topics
- Enabling multiple ways of driving the robot, mainly:

    * Controll via the /ackermann_cmd topic and message protocol
    * Controll via a linear Joystick
    * Controll via Tank Controller Cosmo - with two drive trains

Additonly, it also owns a few slice of life features for creating an easier working enviroment with Isaac Sim.

In the case you want to run this extension on your server or localhost there needs to be a few prerequists. For most of
them you will find an easy way to install them online or via popular installers as "pip".

## Basic Requirements:
- Isaac Sim 2023.1 or later (https://docs.omniverse.nvidia.com/isaacsim/latest/installation/install_workstation.html)
- ROS 2 Bridge extension needs to be enabled before launch of the app
- ROS 2 Humble (https://docs.ros.org/en/humble/index.html)
- Ackermann_Msgs (`sudo apt install ros-humble-ackermann-msgs` - only available on linux)
- numpy (`pip install numpy`)

## Further Requirements to use the entirty of the implemented code
- PyGame (for visulisation of the Cosmo Tank Controller and Joystick; `pip install pygame==2.6.0`)
- Kafka (`pip3 uninstall kafka && pip3 install kafka-python`)

## If you are using windows, please refer to the WSL2 installation guide for ROS2 Humble
https://docs.omniverse.nvidia.com/isaacsim/latest/installation/install_ros.html#running-native-ros


#### Please note that this is list might be incomplet and that there might be more packages required to be installed, before you can use it.

## Separate Standalone Scripts:
This extension includes a total of 4 separate Scripts that can be used in combination with or without this extension.
Two of them, "tank_controller_cosmo.py" and "virtual_joystick_2.py", enable you to drive Husky in Isaac Sim via
Ackermann Messages on the "/ackermann_cmd" topic.

The other two, "ros2_kafka_producer.py" and "ros2_kafka_reader.py", are used to save (produce) LiDAR PointClouds
from the ROS 2 topic "/point_cloud_hydra" to Kafka and read them out from Kafka to ROS 2 respectivly.

In the README.md (in the same folder "Standalone_Scripts"), you will be able to find a more indepth explanation of each of the mentioned scripts.

## Husky USD File
Under the folder "Husky_USD" you will be able to find the required USD file of Husky,  which has been tested to work with this extension.
To use it, just drag the file into the viewport of Isaac Sim at the location you want Husky to be.
