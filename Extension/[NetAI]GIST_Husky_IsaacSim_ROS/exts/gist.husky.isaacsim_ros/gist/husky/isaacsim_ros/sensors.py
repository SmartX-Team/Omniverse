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
import carb
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

def create_imu_sensor(stage: Usd.Stage, path_to_parent: str) -> bool:
    """
    Ensures the IsaacImuSensor prim exists using the corresponding command.
    Applies robust checks and error handling similar to the lidar function.
    Returns True if the sensor prim exists or was successfully created, False otherwise.
    """
    # 1. LiDAR 함수처럼 Stage 유효성 먼저 확인
    if not stage:
        carb.log_error("[sensors.py] Could not get USD stage for IMU creation.")
        return False

    imu_sensor_path = path_to_parent + "/imu_sensor"
    imu_sensor_prim = stage.GetPrimAtPath(imu_sensor_path)

    # 2. 이미 프리즘이 존재하면 성공으로 간주하고 즉시 True 반환
    if imu_sensor_prim.IsValid():
        carb.log_info(f"[sensors.py] IMU sensor prim already exists at {imu_sensor_path}")
        return True

    # 3. LiDAR 함수처럼 try...except 구문으로 안정성 확보
    carb.log_info(f"[sensors.py] IMU sensor prim not found at {imu_sensor_path}. Attempting creation...")
    try:
        success, _ = omni.kit.commands.execute(
            "IsaacSensorCreateImuSensor",
            path="imu_sensor",
            parent=path_to_parent,
            translation=Gf.Vec3d(0, 0, 0),
            orientation=Gf.Quatd(1, 0, 0, 0),
        )

        # 4. 명령 실행 결과(success)에 따라 분기
        if success:
            # 5. (중요) LiDAR 함수처럼 생성 후 프리즘 유효성 재확인
            imu_prim_check = stage.GetPrimAtPath(imu_sensor_path)
            if imu_prim_check.IsValid():
                carb.log_info(f"[sensors.py] IMU prim created successfully at: {imu_sensor_path}")
                # 생성 후 명시적으로 활성화 (추가적인 안정성)
                enabled_attr = imu_prim_check.GetAttribute("enabled")
                if enabled_attr:
                    enabled_attr.Set(True)
                return True
            else:
                carb.log_error(f"[sensors.py] IMU prim creation command succeeded but prim is still invalid at {imu_sensor_path}")
                return False
        else:
            carb.log_error(f"[sensors.py] IsaacSensorCreateImuSensor command failed for parent '{path_to_parent}'.")
            return False
            
    except Exception as e:
        carb.log_error(f"[sensors.py] Exception during IMU prim creation: {e}")
        return False

    # This function now primarily ensures the IMU prim exists.
    # It doesn't return anything explicitly but modifies the stage.
def create_lidar_sensor(parent: str, cfg_name: str) -> bool: # 반환 타입을 bool로 변경
    """
    Ensures the RtxLidar sensor prim exists using IsaacSensorCreateRtxLidar command.
    Does NOT create RenderProduct, Annotator, or Writer.
    Returns True if the sensor prim exists or was successfully created, False otherwise.
    """
    print(f"[DEBUG sensors.py - OmniGraph Mode] Entering create_lidar_sensor. parent='{parent}', cfg_name='{cfg_name}'")
    stage = omni.usd.get_context().get_stage()
    if not stage:
        carb.log_error("[sensors.py] Could not get USD stage.")
        return False

    # 센서 프리미티브 경로 확인 및 생성 시도
    # 참고: extension.py에서 PRIM_PATH_OF_LIDAR (/World/Ni_KI_Husky/lidar_link)를 parent로 전달함
    sensor_prim_path_abs = f"{parent}/lidar_sensor" # 절대 경로
    sensor_prim = stage.GetPrimAtPath(sensor_prim_path_abs)

    if sensor_prim.IsValid():
        carb.log_info(f"[sensors.py] LiDAR sensor prim already exists at {sensor_prim_path_abs}")
        return True # 이미 존재하면 성공으로 간주

    # 존재하지 않으면 생성 시도
    carb.log_info(f"[sensors.py] LiDAR sensor prim not found at {sensor_prim_path_abs}. Attempting creation...")
    try:
        # 인자 이름 확인 (parent, cfg_name 사용)
        success, sensor_prim_obj = omni.kit.commands.execute(
            "IsaacSensorCreateRtxLidar",
            path="lidar_sensor",      # 부모 기준 상대 경로
            parent=parent,            # 부모 프리미티브 경로
            config=cfg_name,          # 설정 이름
            translation=(0, 0, 0),    # 상대 위치
            orientation=Gf.Quatd(1, 0, 0, 0) # 기본 방향 (W,X,Y,Z)
        )

        if success:
            # 생성 후 프리미티브 유효성 재확인
            sensor_prim_check = stage.GetPrimAtPath(sensor_prim_path_abs)
            if sensor_prim_check.IsValid():
                carb.log_info(f"[sensors.py] LiDAR prim created successfully at: {sensor_prim_path_abs}")
                return True
            else:
                carb.log_error(f"[sensors.py] LiDAR prim creation command succeeded but prim is still invalid at {sensor_prim_path_abs}")
                return False
        else:
            carb.log_error(f"[sensors.py] IsaacSensorCreateRtxLidar command failed for parent '{parent}' config '{cfg_name}'.")
            return False
    except Exception as e:
        carb.log_error(f"[sensors.py] Exception during LiDAR prim creation: {e}")
        return False