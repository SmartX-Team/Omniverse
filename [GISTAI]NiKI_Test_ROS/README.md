# Intro
Hi!

This extension was created by the Gwangju Institute of Science and Technology (GIST) [^1] to faccilitate a 
myriad of diffrent functions sourounding the UGV Husky [^2] created by Clearpath Robotics for the intendet usage in 
tandem with Issac Sim [^3] by Nvidia and the Robot Operating System 2 Humble [^4] (from now on referred as ROS 2 or
Humble).

[^1] https://ewww.gist.ac.kr/en/main.html
[^2] https://clearpathrobotics.com/husky-unmanned-ground-vehicle-robot/
[^3] https://docs.omniverse.nvidia.com/isaacsim/latest/overview.html
[^4] https://docs.ros.org/en/humble/index.html

This extension encompasses:
- Features for setting up Husky in Isaac Sim to be as realistic as possible
- Driving Husky in Isaac Sim as well in the real world
- Enabling connections between various diffrent parts of the ecosystem "Husky"
- An additonal 4 standalone scripts used for:
    - Steering and controlling Husky via a virtual Tank Controller called COSMO
    - Adjusting the velocity of all 4 wheels at the same time via a virtual joystick
    - and two scripts for saving and reading data to and from Kafka for data storage

The following image is an explenation of the system architecture:
![alt text](/exts/ni.ki.test.ros/data/Extension_System.png)

(All of the dotted lines are showing connections that have not yet been connected, but are in the planning.)

The folder tree below depicts the conntent of all files in the `exts` folder:
```
exts
└───ni.ki.test.ros
    ├───config (Used for apperance and tracking purposes for the extension in Isaac Sim)
    ├───data  (folder for .png)
    ├───docs  (contains a README and the Changelog of the extension)
    └───ni
        └───ki
            └───test
                └───ros
                    ├───Husky_USD (Contains the USD used in Isaac Sim to represent Husky)
                    ├───Out_Dated (Used for reference purposes)
                    ├───Standalone_Scripts  (Contains the aforementioned standalone scripts)
                    ├───tests  (generated automatically)
                    │   └───__pycache__ (Needed for VS code and Isaac Sim)
                    └───__pycache__ (Needed for VS code and Isaac Sim)
```  

For further explanations about the extension, please refer to the README in `exts > ni.ki.test.ros > docs`.

## Installation Guide
The following shows a guide of how to install the prerequists for this extension.

(Will be worked on soon)

## Seting up the Extension
To set up the extension, after everything has been installed you need to open up Isaac Sim with the ROS2 Bridge enabled.

Afterwards go into: Windows -> Extensions -> Three Horizontal Lines -> Settings -> Extension Search Path
When opeing up the extension search path tab, please click on the plus button in the edit column.

1. Use the github link:
Then copy this link for the current extension: `https://github.com/CosmoAdAstra/NI-KI-Test-ROS/tree/main/exts/`
And that paste it into the now new empty column.

2. Use the files:
Download the complete 'exts'-folder into a folder on your localhost or server. 
(You can use services as https://minhaskamal.github.io/DownGit/#/home for this purpose.)
Then copy the path to the 'exts'-folder and paste it into the now new empty column.

Finally, look for "ni.ki.test.ros" extension in extension manager and enable it, it should be in the tap for third parties.

Done.

Now you can use this extension!
