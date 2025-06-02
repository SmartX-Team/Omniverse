# GIST Husky Isaac Sim ROS Extension - 코드 구조 설명

# GIST Husky Isaac Sim ROS Extension - Code Structure Explanation

This document describes the internal code structure of the `gist.husky.isaacsim_ros` Python package.

## Directory Structure (Expected)


gist/husky/isaacsim_ros/
├── init.py         # Package initialization and main class exposure
├── extension.py        # Omniverse extension lifecycle (startup/shutdown), UI window creation and management
├── actions.py          # Implementation of actual action logic triggered by UI button clicks
├── utils.py            # Collection of utility functions commonly used across multiple modules
├── sensors.py          # Logic for creating and managing Husky robot sensors (Camera, LiDAR, IMU)
├── ros_listeners.py    # Logic for creating/managing OmniGraph for ROS 2 topic subscription (ros2 graph)
├── camera_publishers.py # Logic for creating/managing OmniGraph for publishing camera data to ROS 2 topics
├── config.py           # (Optional Improvement) Definition of main configuration values (Prim paths, topic names, etc.)
└── Standalone_Scripts/ # Scripts runnable independently of the extension (e.g., external controllers)
└── ...


## Main Module Descriptions

* **`__init__.py`**:
    * Initializes the package and exposes the main extension class (`NiKiTestRosExtension`) so Omniverse can recognize it.
    * Avoids importing other modules directly to prevent circular references.

* **`extension.py`**:
    * Contains the main class (`NiKiTestRosExtension`) implementing the `omni.ext.IExt` interface.
    * `on_startup`: Called when the extension starts. Creates the UI window (`omni.ui`), loads necessary modules (actions, utils), and connects button clicks to functions in `actions.py`.
    * `on_shutdown`: Called when the extension shuts down. Cleans up created UI resources.

* **`actions.py`**:
    * Implements the actual functionalities linked to the UI buttons defined in `extension.py` as functions (e.g., `initialize_husky`, `start_cosmo_mode`, `pilot_forward`, `cease_movement`).
    * Calls functions from other modules like `sensors.py`, `ros_listeners.py`, `utils.py`, `config.py` as needed to perform tasks.
    * Receives necessary information like the USD Stage object and UI Label widget as arguments from `extension.py`.

* **`utils.py`**:
    * Contains functions that are not specific to a particular feature and can be reused across multiple modules (e.g., `get_footprint_path`, `print_info`, `print_instructions_for_tank_controll`).

* **`sensors.py`**:
    * Includes functions for creating and configuring sensor primitives (Camera, LiDAR, IMU) to be attached to the Husky robot.
    * May also include logic for setting up OmniGraph nodes required for sensor operation.

* **`ros_listeners.py`**:
    * Contains functions to create and manage OmniGraphs for subscribing to ROS 2 topics to control the robot within Isaac Sim (e.g., a graph that takes `/ackermann_cmd` topic and controls the Articulation Controller).

* **`camera_publishers.py`**:
    * Contains functions to create and manage OmniGraphs for publishing camera sensor data from within Isaac Sim to ROS 2 topics.
