# Imports
# Basic Import
import numpy as np

# Used for working with the USD File Format
from pxr import Gf, Usd, UsdGeom

# Basic Imports from Omniverse (Most of them are installed with Omniverse KIT)
# import omni.ext # 이 파일에서는 사용되지 않음
import omni.kit.commands

# Used for working with the sensors and creating renders (LiDAR)
import omni.replicator.core as rep

# Actual Sensor import
# from omni.isaac.sensor import _sensor, Camera # Removed _sensor
# Camera import: This might be outdated. If errors occur, check modern API.
# Potential modern alternatives: omni.isaac.core.objects.CameraPrim or command-based creation.
from omni.isaac.sensor import Camera
import omni.isaac.core.utils.numpy.rotations as rot_utils

# Publisher for ROS2 Humble (Assuming this file exists and works)
from .camera_publishers import *
import warnings
import time

# Publisher for Kafka (Imported but not used directly in this file)
# from kafka import KafkaProducer # If not used by camera_ros_publisher, consider removing

# Creates the required sensors
def create_rgb_camera(stage: Usd.Stage, prim_path: str) -> Camera: # Return type hints Camera object
    """
    Creates an RGB Camera using the omni.isaac.sensor.Camera class.
    Note: This class usage might be outdated depending on the Isaac Sim version.
    Initializes and starts publishing RGB data.
    """
    # WARNING: omni.isaac.sensor.Camera might be deprecated.
    # Consider using command-based creation or omni.isaac.core.objects.CameraPrim for newer Isaac Sim versions.
    camera = Camera(
        prim_path= prim_path,
        # frequency=20, # Frequency might be set differently in newer APIs or via simulation time steps
        translation = Gf.Vec3d(0, 0, 0), # Position relative to parent prim
        resolution= (480, 260),  # (1920, 1080), # Resolution is lowered for better performance
        orientation=rot_utils.euler_angles_to_quats(np.array([0, 0, 0]), degrees=True), # Initial orientation
    )
    camera.initialize() # Initialize the camera object

    # TODO: Verify if approx_freq is needed or if publisher should use actual sensor frequency/simulation rate
    approx_freq = 30 # Approximate frequency for publisher rate limiting?

    # Start ROS publishers (assuming these functions exist in camera_ros_publisher.py)
    # publish_camera_info(camera, approx_freq) # Camera info publisher (optional)
    publish_rgb(camera, approx_freq) # RGB image publisher

    return camera

def create_depth_camera(stage: Usd.Stage, prim_path: str) -> Camera: # Return type hints Camera object
    """
    Creates a Depth Camera using the omni.isaac.sensor.Camera class.
    Note: This class usage might be outdated depending on the Isaac Sim version.
    Initializes and starts publishing Depth, TF, and PointCloud data.
    """
    # WARNING: omni.isaac.sensor.Camera might be deprecated. See create_rgb_camera comments.
    depth_camera = Camera(
        prim_path= prim_path,
        # frequency=20, # Frequency might be set differently
        translation = Gf.Vec3d(0, 0, 0), # Position relative to parent prim
        resolution= (340, 180),  # (1280, 720), # Resolution is lowered for better performance
        orientation=rot_utils.euler_angles_to_quats(np.array([0, 0, 0]), degrees=True), # Initial orientation
    )
    depth_camera.initialize() # Initialize the camera object

    # TODO: Verify approx_freq usage (see create_rgb_camera)
    approx_freq = 30

    # Start ROS publishers (assuming these functions exist in camera_ros_publisher.py)
    # publish_camera_info(depth_camera, approx_freq) # Camera info publisher (optional)
    publish_depth(depth_camera, approx_freq) # Depth image publisher
    publish_camera_tf(depth_camera) # Camera TF publisher
    publish_pointcloud_from_depth(depth_camera, approx_freq) # Pointcloud publisher derived from depth

    return depth_camera

def create_imu_sensor(stage: Usd.Stage, path_to_parent: str): # Renamed arg for clarity
    """
    Creates an IMU sensor prim using the IsaacSensorCreateImuSensor command.
    Data reading is handled externally (e.g., in extension.py using IMUSensor object).
    """
    imu_sensor_path = path_to_parent + "/imu_sensor"
    imu_sensor_prim = stage.GetPrimAtPath(imu_sensor_path)

    if not imu_sensor_prim.IsValid():
        print(f"IMU sensor not found at {imu_sensor_path}, attempting creation...")
        success, _ = omni.kit.commands.execute(
            "IsaacSensorCreateImuSensor",
            path="imu_sensor", # Relative path for the new prim
            parent=path_to_parent, # Parent prim path where the IMU will be attached
            # sensor_period=1, # Period might be controlled by simulation time or physics settings now. Check API.
            # linear_acceleration_filter_size=10, # Filter sizes might be properties now
            # angular_velocity_filter_size=10,
            # orientation_filter_size=10,
            translation = Gf.Vec3d(0, 0, 0), # Relative position
            orientation = Gf.Quatd(1, 0, 0, 0), # Relative orientation (W, X, Y, Z - identity)
            # visualizer_enable=True # Optional: visualize sensor in viewport
        )

        if success:
            print(f"IMU sensor created successfully at {imu_sensor_path}")
            # Re-verify prim creation
            imu_sensor_prim = stage.GetPrimAtPath(imu_sensor_path)
            if not imu_sensor_prim.IsValid():
                 print(f"Error: IMU prim still not valid after creation command at {imu_sensor_path}")
        else:
            print(f"Error: Failed to execute IsaacSensorCreateImuSensor command at {path_to_parent}")

        # --- Removed Deprecated Code ---
        # The following block used the old _sensor interface for reading data,
        # which is now handled in extension.py using the IMUSensor object.
        # if success:
        #     _imu_sensor_interface = _sensor.acquire_imu_sensor_interface()
        #     _imu_sensor_interface.get_sensor_reading(path_to_parent + "/imu_sensor", use_latest_data = True, read_gravity = True)
        # --- End of Removed Code ---
    else:
        print(f"IMU sensor already exists at {imu_sensor_path}")

    # This function now primarily ensures the IMU prim exists.
    # It doesn't return anything explicitly but modifies the stage.

def create_lidar_sensor(path_to_parent: str, lidar_config: str) -> bool:
    """
    Ensures the RTX Lidar sensor prim exists.
    Does NOT create a RenderProduct or use Replicator.
    Returns True if the sensor prim exists or was successfully created, False otherwise.
    """
    lidar_sensor_path = f"{path_to_parent}/lidar_sensor"
    stage = omni.usd.get_context().get_stage()
    if not stage:
        print("Error inside create_lidar_sensor: Could not get USD stage.")
        return False
    lidar_prim = stage.GetPrimAtPath(lidar_sensor_path)

    if lidar_prim.IsValid():
        print(f"LiDAR sensor already exists at {lidar_sensor_path}")
        return True # 센서 프리미티브가 존재함

    print(f"LiDAR sensor not found at {lidar_sensor_path}, attempting creation...")
    success, _ = omni.kit.commands.execute(
        "IsaacSensorCreateRtxLidar",
        path="/lidar_sensor",
        parent=path_to_parent,
        config=lidar_config,
        translation=(0.0, 0.0, 0.0),
        orientation=Gf.Quatd(1.0, 0.0, 0.0, 0.0),
    )

    if not success:
        print(f"Error: Failed to execute IsaacSensorCreateRtxLidar command at {path_to_parent}")
        return False

    # 생성 후 다시 확인
    lidar_prim = stage.GetPrimAtPath(lidar_sensor_path)
    if lidar_prim.IsValid():
        print(f"RTX Lidar sensor prim created successfully at {lidar_sensor_path}")
        return True # 생성 성공
    else:
        print(f"Error: Lidar prim invalid after creation command at {lidar_sensor_path}")
        return False