"""


이 익스텐션은 GIST(광주과학기술원) 소속 인턴턴 **Niki C. Zils** 님께서 `ni.ki.test.ros` 라는 이름으로 처음 개발하셨습니다. 기반 작업을 해주신 Niki 님께 감사드립니다!

현재 코드베이스는 NVIDIA Isaac Sim 4.5 및 이후 버전과의 호환성을 확보하기 위해 대규모 리팩토링 작업이 진행되었습니다. 이는 Isaac Sim 4.5에서 센서, Replicator 및 기타 핵심 API에 도입된 주요 변경 사항 때문에 필수적이었습니다.

Isaac Sim 4.5 이전 버전을 대상으로 했던 Niki 인턴분이 작성했던 원본 코드베이스는 참고용으로 이 프로젝트 내의 `deprecated/` 디렉토리에 보관되어 있습니다. Isaac Sim 4.5 이상 버전과의 호환성을 위해서는 현재 코드를 참조해 주십시오.

This extension was originally developed by **Niki C. Zils** at GIST (Gwangju Institute of Science and Technology) as `ni.ki.test.ros`. We thank Niki for the foundational work!

Significant refactoring has been performed on this codebase to ensure compatibility with **NVIDIA Isaac Sim 4.5 and later versions**. This was necessary due to major changes introduced in the Sensor, Replicator, and other core APIs in Isaac Sim 4.5.

The original codebase, intended for pre-4.5 versions of Isaac Sim, has been archived in the `deprecated/` directory within this project for reference purposes. Please refer to the current code for Isaac Sim 4.5+ compatibility.

"""

# Links:
# (1) https://ewww.gist.ac.kr/en/main.html
# (2) https://clearpathrobotics.com/husky-unmanned-ground-vehicle-robot/
# (3) https://docs.omniverse.nvidia.com/isaacsim/latest/overview.html
# (4) https://docs.ros.org/en/humble/index.html

# Imports
from pxr import Gf, Usd
import omni.ext
import omni.kit.commands
import omni.ui as ui
from omni.usd import get_context
import omni.usd # For get_world_transform_matrix

# Local Imports (Ensure these files exist and are correct)
from .sensors import create_rgb_camera, create_depth_camera, create_lidar_sensor, create_imu_sensor # .isaac_sensor -> .sensors 로 변경
from .ros_listeners import create_tank_controll_listener # .ros2_recivers -> .ros_listeners 로 변경 (가정)
from .utils import print_info, print_instructions_for_tank_controll
# --- 수정된 부분 끝 ---
import warnings
# Import IMUSensor here for type hinting or potential direct use if needed
try:
    #from omni.isaac.imu import IMUSensor
    from isaacsim.sensors.physics import IMUSensor    
except ImportError:
    IMUSensor = None # Define as None if import fails, handle appropriately later

# 동적으로 읽어오도록 수정
def get_footprint_path(husky_path):
    stage = get_context().get_stage()
    link_path = f"{husky_path}/base_link"
    if stage.GetPrimAtPath(link_path).IsValid(): return link_path
    footprint_path = f"{husky_path}/base_footprint"
    if stage.GetPrimAtPath(footprint_path).IsValid(): return footprint_path
    warnings.warn(f"Neither base_link nor base_footprint found under {husky_path}. Using default base_footprint path.")
    return footprint_path # 기본값 반환 (오류 처리는 함수 내에서)

# --- Constants and Configuration ---
PRIM_PATH_OF_HUSKY = "/World/Ni_KI_Husky"
PRIM_PATH_OF_FOOTPRINT = get_footprint_path(PRIM_PATH_OF_HUSKY)
PRIM_PATH_OF_FRONT_BUMPER = PRIM_PATH_OF_HUSKY + "/front_bumper_link"
PRIM_PATH_OF_LIDAR = PRIM_PATH_OF_HUSKY + "/lidar_link"
LIDAR_CONFIG = "OS1_REV6_32ch10hz2048res.json" # Example config


class NiKiTestRosExtension(omni.ext.IExt):
    """
    Omniverse Extension for controlling and monitoring a simulated Husky robot
    in Isaac Sim, integrating with ROS2 Humble.
    """
    def on_startup(self, ext_id):
        print("[ni.ki.test.ros] ni ki test ros startup")
        print_info()  # Creates Info Box

        # --- Initialize class attributes ---
        self._window = None
        self.label = None # UI Label for status messages
        self.matrix = None # Husky transform matrix
        self.translate = None # Husky translation
        self.rotation = None # Husky rotation
        self.husky_cam_prim = None # Prim for the RGB camera
        self.husky_cam = None # Camera object for RGB
        self.husky_cam_depth = None # Camera object for Depth
        self.lidar_sensor = None # Prim for the LiDAR sensor
        self.wheels = [] # List to store wheel joint prims

        # --- Build the UI ---
        self._window = ui.Window("Test ROS (Ni-KI)", width=500, height=180)
        with self._window.frame:
            with ui.VStack():
                # Create the label and assign it to the class attribute
                self.label = ui.Label("Extension not initialised.", height=60, alignment=ui.Alignment.TOP, word_wrap=True)

                # UI Buttons - Use self.method_name for callbacks
                with ui.VStack():
                    with ui.HStack():
                        ui.Button("Init.", clicked_fn=self.on_initialize, tooltip="Sets up the robot sensors and position.")
                        ui.Button("Cease", clicked_fn=self.on_cease, tooltip="Stops wheel movement by setting target velocity to 0.")
                    with ui.HStack():
                        ui.Button("Cosmo", clicked_fn=self.on_cosmo,
                                  tooltip="Enables driving via external tank control script. (COntrolled Simulated MOtion)")
                        ui.Button("Pilot", clicked_fn=self.on_pilot,
                                  tooltip="Drives Husky forward by setting wheel target velocity.")
        # Optional: Automatically initialize when the extension starts
        # self.on_initialize()

    def on_shutdown(self):
        print("[ni.ki.test.ros] ni ki test ros shutdown")
        # Clean up resources if necessary (e.g., remove listeners, stop threads)
        # Destroy the UI window
        if self._window:
            self._window.destroy()
        self._window = None
        self.label = None # Clear reference
        # Add cleanup for ROS listeners if needed

    # --- Class Methods for Functionality ---

    def on_initialize(self):

        if not self.label:
            return False
        stage = get_context().get_stage()

        self.label.text = "Start of initialization\n"
        """Initializes the Husky simulation environment, sensors, and position."""
        try:
            # Create/ensure IMU prim exists (using command in create_imu_sensor)
            create_imu_sensor(stage, PRIM_PATH_OF_LIDAR)
            imu_sensor_path = PRIM_PATH_OF_LIDAR + "/imu_sensor"
            imu_prim = stage.GetPrimAtPath(imu_sensor_path)

            if not imu_prim.IsValid():
                raise Exception("IMU prim '/imu_sensor' not valid after creation call.")

            # IMU Prim 생성 확인됨
            self.label.text += " | IMU: Prim Created"
            # >>> 데이터 읽기 시도 로직은 여기서 제거 <<<
            # (읽기는 시뮬레이션 업데이트 루프나 ROS2 Publisher에서 처리 필요)

        except ImportError as e: # 'isaacsim.sensors.physics' import 실패 시
             print(f"IMU Error: {e}. Is 'isaacsim.sensors.physics' extension enabled?")
             self.label.text += " | IMU: Failed (Import Error)"
             warnings.warn(f"IMU functionality unavailable: {e}")
        except Exception as e:
             print(f"Error during IMU setup: {e}")
             self.label.text += f" | IMU: Failed ({type(e).__name__})"
             warnings.warn(f"IMU setup/reading failed: {e}")
            # Continue or return?

        # --- Sensor Initialization ---
        # Husky RGB/Depth Cam
        husky_cam_path = PRIM_PATH_OF_FRONT_BUMPER + "/husky_rgb_cam"
        husky_depth_cam_path = PRIM_PATH_OF_FRONT_BUMPER + "/husky_depth_cam"
        self.husky_cam_prim = stage.GetPrimAtPath(husky_cam_path)
        if not self.husky_cam_prim.IsValid():
            try:
                self.husky_cam = create_rgb_camera(stage=stage, prim_path=husky_cam_path)
                self.husky_cam_depth = create_depth_camera(stage=stage, prim_path=husky_depth_cam_path)
                self.husky_cam_prim = stage.GetPrimAtPath(husky_cam_path) # Re-get after creation
                self.label.text += " | Husky Cam: Created"
            except Exception as e:
                self.label.text += f" | Husky Cam: Creation Failed ({type(e).__name__})"
                warnings.warn(f"Failed to create Husky cameras: {e}")
        else:
            # Optionally re-initialize publishers if needed for existing cameras
            self.label.text += " | Husky Cam: Exists"

        # LiDAR and IMU
        self.lidar_sensor = stage.GetPrimAtPath(PRIM_PATH_OF_LIDAR + "/lidar_sensor")
        lidar_ready = self.lidar_sensor.IsValid()
        if not lidar_ready:
            try:
                # create_lidar_sensor should return True on prim creation success
                if create_lidar_sensor(PRIM_PATH_OF_LIDAR, LIDAR_CONFIG):
                    self.lidar_sensor = stage.GetPrimAtPath(PRIM_PATH_OF_LIDAR + "/lidar_sensor")
                    lidar_ready = self.lidar_sensor.IsValid()
                else:
                    lidar_ready = False
            except Exception as e:
                 warnings.warn(f"Exception during LiDAR creation: {e}")
                 lidar_ready = False

        if not lidar_ready:
            self.label.text += " | LiDAR: Failed"
        else:
            self.label.text += " | LiDAR: Valid"
            # --- If LiDAR is ready, proceed with IMU ---
            try:
                # Create/ensure IMU prim exists
                create_imu_sensor(stage, PRIM_PATH_OF_LIDAR)
                imu_sensor_path = PRIM_PATH_OF_LIDAR + "/imu_sensor"
                imu_prim = stage.GetPrimAtPath(imu_sensor_path)

                if not imu_prim.IsValid():
                    raise Exception("IMU prim not valid after creation call.")

                if IMUSensor is None:
                    raise ImportError("IMUSensor class could not be imported.")

                # Get reading using the object
                imu_sensor_instance = IMUSensor(prim_path=imu_sensor_path)
                # imu_sensor_instance.initialize() # If needed
                #imu_data = imu_sensor_instance.get_current_reading()
                imu_data = imu_sensor_instance.get_current_frame()

                if isinstance(imu_data, dict) and imu_data: # 데이터가 비어있지 않은 사전인지 확인
                    print("IMU Data (Frame):", imu_data)
                    self.label.text += " | IMU: Valid (Frame Read)"
                else:
                    self.label.text += " | IMU: Failed (No Frame Data)"

            except ImportError as e:
                print(f"IMU Error: {e}")
                self.label.text += " | IMU: Failed (Import Error)"
                warnings.warn(f"IMU functionality unavailable: {e}")
            except Exception as e:
                print(f"Error during IMU setup or reading: {e}")
                self.label.text += f" | IMU: Failed ({type(e).__name__})"
                warnings.warn(f"IMU setup/reading failed: {e}")
            # --- End of IMU Handling ---

        # Remove root_joint
        path_to_root_joint = PRIM_PATH_OF_HUSKY + "/root_joint"
        root_of_all_evil = stage.GetPrimAtPath(path_to_root_joint)
        if root_of_all_evil.IsValid():
            if stage.RemovePrim(path_to_root_joint):
                warnings.warn("Root Joint was removed! - NI.KI.Test.ROS")
                print("Root joint removed.")
            else:
                warnings.warn("Failed to remove root_joint. Please delete manually.")
                print("Failed to remove root_joint.")
        else:
            print("Root joint not found (which is good).")

        self.label.text += "\nInit finished."
        return True

    def on_cosmo(self):
        """Sets up the robot for tank control via external script."""
        if not self.label: return
        self.on_cease() # Stop previous movement first

        self.label.text = "Starting Tank Control mode.\nPlease run the control script."
        try:
            create_tank_controll_listener(PRIM_PATH_OF_HUSKY)
            print_instructions_for_tank_controll()
        except Exception as e:
            self.label.text = f"Failed to start Tank Control: {e}"
            warnings.warn(f"Failed to create tank control listener: {e}")

    def on_pilot(self):
        """Drives the Husky forward by setting wheel velocities."""
        if not self.label: return
        self.label.text = "Engaging Pilot Mode (Forward Movement)"

        stage = get_context().get_stage()

        # Define wheel joint paths
        wheel_joints = [
            PRIM_PATH_OF_HUSKY + "/base_link/back_left_wheel_joint",
            PRIM_PATH_OF_HUSKY + "/base_link/back_right_wheel_joint",
            PRIM_PATH_OF_HUSKY + "/base_link/front_left_wheel_joint",
            PRIM_PATH_OF_HUSKY + "/base_link/front_right_wheel_joint"
        ]
        target_velocity = 1000.0
        stiffness = 0.0
        self.wheels = [] # Reset wheel list

        for joint_path in wheel_joints:
            wheel_prim = stage.GetPrimAtPath(joint_path)
            if wheel_prim.IsValid():
                try:
                    # Check and set stiffness
                    if wheel_prim.HasAttribute("drive:angular:physics:stiffness"):
                         wheel_prim.GetAttribute("drive:angular:physics:stiffness").Set(stiffness)
                    else: warnings.warn(f"Stiffness attr missing on {joint_path}")
                    # Check and set target velocity
                    if wheel_prim.HasAttribute("drive:angular:physics:targetVelocity"):
                         wheel_prim.GetAttribute("drive:angular:physics:targetVelocity").Set(target_velocity)
                    else: warnings.warn(f"TargetVelocity attr missing on {joint_path}")
                    self.wheels.append(wheel_prim)
                except Exception as e:
                    warnings.warn(f"Failed to set attributes for {joint_path}: {e}")
            else:
                 warnings.warn(f"Wheel joint prim not found: {joint_path}")

    def on_cease(self):
        """Stops Husky movement by setting wheel velocities to zero."""
        if not self.label: return
        self.label.text = "Ceasing Movement"

        stage = get_context().get_stage()
        wheel_joints = [
            PRIM_PATH_OF_HUSKY + "/base_link/back_left_wheel_joint",
            PRIM_PATH_OF_HUSKY + "/base_link/back_right_wheel_joint",
            PRIM_PATH_OF_HUSKY + "/base_link/front_left_wheel_joint",
            PRIM_PATH_OF_HUSKY + "/base_link/front_right_wheel_joint"
        ]
        target_velocity = 0.0
        stiffness = 0.0 # Keep stiffness 0? Or reset?

        for joint_path in wheel_joints:
            wheel_prim = stage.GetPrimAtPath(joint_path)
            if wheel_prim.IsValid():
                try:
                    if wheel_prim.HasAttribute("drive:angular:physics:stiffness"):
                         wheel_prim.GetAttribute("drive:angular:physics:stiffness").Set(stiffness)
                    # else: warnings.warn(f"Stiffness attr missing on {joint_path}") # Less critical when stopping
                    if wheel_prim.HasAttribute("drive:angular:physics:targetVelocity"):
                         wheel_prim.GetAttribute("drive:angular:physics:targetVelocity").Set(target_velocity)
                    else: warnings.warn(f"TargetVelocity attr missing on {joint_path}")
                except Exception as e:
                    warnings.warn(f"Failed to set attributes for {joint_path}: {e}")
            # else: warnings.warn(f"Wheel joint prim not found: {joint_path}") # Less critical when stopping

        self.label.text += "\nMovement ceased."

# --- Helper Function (outside class) ---
def update_scaling_orientation(prim: Usd.Prim, stage: Usd.Stage, translation: Gf.Vec3d):
    """Adjusts the Husky prim's vertical position and resets orientation."""
    footprint_prim = stage.GetPrimAtPath(PRIM_PATH_OF_FOOTPRINT)
    adj_height = 0.0 # Default height

    if not footprint_prim.IsValid():
        warnings.warn(f"Base footprint prim not found at {PRIM_PATH_OF_FOOTPRINT}. Using default height (0.0).")
    else:
        try:
            if footprint_prim.HasAttribute("xformOp:translate"):
                footprint_translate = footprint_prim.GetAttribute("xformOp:translate").Get()
                if footprint_translate is not None:
                    adj_height = -float(footprint_translate[2]) # Use negative Z value, ensure float
                else:
                    warnings.warn(f"'xformOp:translate' on {PRIM_PATH_OF_FOOTPRINT} has no value. Using default height.")
            else:
                warnings.warn(f"'xformOp:translate' not found on {PRIM_PATH_OF_FOOTPRINT}. Using default height.")
        except Exception as e:
            warnings.warn(f"Error getting footprint height: {e}. Using default height.")

    # Update prim transform
    if prim.HasAttribute('xformOp:orient'):
        #prim.GetAttribute('xformOp:orient').Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0)) # Reset rotation (W,X,Y,Z)
        prim.GetAttribute('xformOp:orient').Set(Gf.Quatd(1.0, 0.0, 0.0, 0.0))
    else:
        warnings.warn(f"'xformOp:orient' not found on {prim.GetPath()}. Cannot reset orientation.")

    if prim.HasAttribute("xformOp:translate"):
        prim.GetAttribute("xformOp:translate").Set(Gf.Vec3f(float(translation[0]), float(translation[1]), adj_height))
    else:
        warnings.warn(f"'xformOp:translate' not found on {prim.GetPath()}. Cannot set position.")

    print(f"Set prim position to: ({translation[0]:.2f}, {translation[1]:.2f}, {adj_height:.2f})")
    return adj_height