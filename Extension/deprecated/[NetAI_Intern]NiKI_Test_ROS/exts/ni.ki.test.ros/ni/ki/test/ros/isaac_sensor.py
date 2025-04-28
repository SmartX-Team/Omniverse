# Imports
# Basic Import
import numpy as np

# Used for working with the USD File Format
from pxr import Gf, Usd, UsdGeom

# Basic Imports from Omniverse (Most of them are installed with Omniverse KIT)
import omni.ext
import omni.kit.commands

# Used for working with the sensors and creating renders
import omni.replicator.core as rep

# Actuall Sensor import
from omni.isaac.sensor import _sensor, Camera
import omni.isaac.core.utils.numpy.rotations as rot_utils

# Publisher for ROS2 Humble
from .camera_ros_publisher import *

# Publisher for Kafka
from kafka import KafkaProducer

# Creates the required sensors
def create_rgb_camera(stage: Usd.Stage, prim_path: str) -> UsdGeom.Camera:
    camera = Camera(
        prim_path= prim_path,
        frequency=20,
        translation = Gf.Vec3d(0, 0, 0),
        resolution= (480, 260),  #  (1920, 1080), # Resolution is lowered for better performance
        orientation=rot_utils.euler_angles_to_quats(np.array([0, 0, 0]), degrees=True),
    )
    camera.initialize()
    approx_freq = 30

    
    # publish_camera_info(camera, approx_freq)
    publish_rgb(camera, approx_freq)

    return camera

def create_depth_camera(stage: Usd.Stage, prim_path: str) -> UsdGeom.Camera:
    depth_camera = Camera(
        prim_path= prim_path,
        frequency=20,
        translation = Gf.Vec3d(0, 0, 0),
        resolution= (340, 180),  # (1280, 720), # Resolution is lowered for better performance
        orientation=rot_utils.euler_angles_to_quats(np.array([0, 0, 0]), degrees=True),
    )
    depth_camera.initialize()
    approx_freq = 30

    
    # publish_camera_info(camera, approx_freq)
    publish_depth(depth_camera, approx_freq)
    publish_camera_tf(depth_camera)
    publish_pointcloud_from_depth(depth_camera, approx_freq)

    return depth_camera

def create_imu_sensor(stage: Usd.Stage, path_to_husky: str):
    # The IMU is build into the LiDAR - refer to its datasheet
    imu_sensor = stage.GetPrimAtPath(path_to_husky + "/imu_sensor")
    if not imu_sensor.IsValid():
        success, _isaac_sensor_prim = omni.kit.commands.execute(
            "IsaacSensorCreateImuSensor",
            path="imu_sensor",
            parent=path_to_husky,
            sensor_period=1,
            linear_acceleration_filter_size=10,
            angular_velocity_filter_size=10,
            orientation_filter_size=10,
            translation = Gf.Vec3d(0, 0, 0),
            orientation = Gf.Quatd(1, 0, 0, 0),
        )

        # Starts publishing the data
        if success:
            _imu_sensor_interface = _sensor.acquire_imu_sensor_interface()
            _imu_sensor_interface.get_sensor_reading(path_to_husky + "/imu_sensor", use_latest_data = True, read_gravity = True)

def create_lidar_sensor(path_to_husky: str, lidar_config: str):
    # LiDAR Specs - https://data.ouster.io/downloads/datasheets/datasheet-revd-v2p0-os1.pdf
    # 1. Create The Camera
    success, sensor = omni.kit.commands.execute(
        "IsaacSensorCreateRtxLidar",
        path="/lidar_sensor",
        parent=path_to_husky,
        config=lidar_config,
        translation=(0, 0, 0),
        orientation=Gf.Quatd(0,0,0,0.10),
    )

    # Starts publising data
    if success:
        # 1. Create and Attach a render product
        render_product = rep.create.render_product(sensor.GetPath(), [1, 1])

        # 2. Create Annotator to read the data from with annotator.get_data()
        annotator = rep.AnnotatorRegistry.get_annotator("RtxSensorCpuIsaacCreateRTXLidarScanBuffer")
        annotator.attach(render_product)

        # 3. Create a Replicator Writer that "writes" points to be read by rviz
        writer = rep.writers.get("RtxLidar" + "ROS2PublishPointCloud")# "RtxLidarDebugDrawPointCloudBuffer")
        writer.initialize(topicName="point_cloud", frameId="sim_lidar")
        writer.attach(render_product)

        # 3.5 Creates a second writer that publishes a hydra_texture
        hydra_texture = rep.create.render_product(sensor.GetPath(), [1, 1], name="Isaac")
        writer_hydra = rep.writers.get("" + "RtxLidar" + "ROS2PublishPointCloud" + "Buffer")
        writer_hydra.initialize(topicName="point_cloud_hydra", frameId="sim_lidar")
        writer_hydra.attach([hydra_texture])
        
    return success
