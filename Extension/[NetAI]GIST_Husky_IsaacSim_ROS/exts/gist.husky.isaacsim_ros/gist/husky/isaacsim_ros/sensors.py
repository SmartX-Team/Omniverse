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

def create_lidar_sensor(path_to_parent: str, lidar_config: str) -> bool: # Renamed arg, added return type hint
    """
    Creates an RTX Lidar sensor using the IsaacSensorCreateRtxLidar command
    and sets up Replicator pipelines for ROS2 publishing.
    Returns True if the sensor prim creation command was successful, False otherwise.
    """
    lidar_prim_path = path_to_parent + "/lidar_sensor" # Define full path for clarity
    stage = omni.usd.get_context().get_stage() # Get stage context
    lidar_prim = stage.GetPrimAtPath(lidar_prim_path)

    if lidar_prim.IsValid():
        print(f"LiDAR sensor already exists at {lidar_prim_path}")
        # Decide if existing setup needs modification or just return True
        # For now, assume existing is okay. Replicator setup might need checking/resetting.
        return True # Indicate sensor prim exists

    print(f"LiDAR sensor not found at {lidar_prim_path}, attempting creation...")
    # 1. Create The Lidar Sensor Prim
    success, sensor_prim_path_or_obj = omni.kit.commands.execute(
        "IsaacSensorCreateRtxLidar",
        path="/lidar_sensor", # Relative path for the new prim
        parent=path_to_parent, # Parent prim path
        config=lidar_config, # Lidar configuration name
        translation=(0.0, 0.0, 0.0), # Relative position (use floats)
        orientation=Gf.Quatd(1.0, 0.0, 0.0, 0.0), # Relative orientation (W, X, Y, Z - identity, corrected from original)
        # IMPORTANT: Original orientation Gf.Quatd(0,0,0,0.10) was likely incorrect/invalid quaternion. Using identity. Adjust if needed.
    )

    # Starts publishing data via Replicator if creation was successful
    if success:
        print(f"RTX Lidar sensor created successfully at {lidar_prim_path}")
        lidar_prim = stage.GetPrimAtPath(lidar_prim_path) # Get the created prim
        if not lidar_prim or not lidar_prim.IsValid():
             print(f"Error: Lidar prim invalid after creation command at {lidar_prim_path}")
             return False # Indicate failure despite command success report

        try:
            lidar_path_str = lidar_prim.GetPath().pathString # Get path as string for Replicator

            # --- Replicator Setup ---
            # Ensure render product names are unique if called multiple times or handle existing ones
            render_product_name = f"{lidar_prim.GetName()}_rp"
            hydra_texture_name = f"{lidar_prim.GetName()}_hydra_rp"

            # 1. Create and Attach a render product for point cloud data
            # Use resolution [1, 1] for non-camera sensors typically
            render_product = rep.create.render_product(lidar_path_str, [1, 1], name=render_product_name)

            # 2. Get point cloud data annotator
            annotator = rep.AnnotatorRegistry.get_annotator("RtxSensorCpuIsaacCreateRTXLidarScanBuffer")
            annotator.attach(render_product) # Attach to the render product

            # 3. Create ROS2 PointCloud Writer
            # Ensure writer names/types are correct for your Isaac Sim version
            writer_type_pc = "RtxLidar" + "ROS2PublishPointCloud"
            writer_pc = rep.writers.get(writer_type_pc)
            if writer_pc:
                writer_pc.initialize(topicName="/point_cloud", frameId="lidar_link") # Use appropriate frame_id
                writer_pc.attach(render_product)
                print("Attached ROS2 PointCloud writer.")
            else:
                print(f"Error: Could not get Replicator writer type: {writer_type_pc}")


            # 3.5 (Optional) Create a second writer that publishes a hydra_texture (if needed)
            # This part seems less standard, verify if "ROS2PublishPointCloudBuffer" writer exists/is needed.
            # hydra_texture = rep.create.render_product(lidar_path_str, [1, 1], name=hydra_texture_name)
            # writer_type_hydra = "RtxLidar" + "ROS2PublishPointCloud" + "Buffer" # Verify this writer type
            # writer_hydra = rep.writers.get(writer_type_hydra)
            # if writer_hydra:
            #     writer_hydra.initialize(topicName="/point_cloud_hydra", frameId="lidar_link") # Use appropriate frame_id
            #     writer_hydra.attach([hydra_texture]) # Attach to the hydra render product
            #     print("Attached Hydra Texture PointCloud writer.")
            # else:
            #     print(f"Error: Could not get Replicator writer type: {writer_type_hydra}")
            # --- End of Replicator Setup ---

        except Exception as e:
            print(f"Error setting up Replicator pipeline for LiDAR: {e}")
            # Decide if failure to set up replicator means overall failure
            # return False # Uncomment if Replicator setup is critical

    else:
        print(f"Error: Failed to execute IsaacSensorCreateRtxLidar command at {path_to_parent}")

    return success # Return the success status of the prim creation command