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
import time # time.sleep 사용을 위해 필요
import omni
import warnings # 다른 곳에서 사용할 수 있으므로 유지

# Local Imports (파일 경로 확인 필요)
from .sensors import create_rgb_camera, create_depth_camera, create_lidar_sensor, create_imu_sensor
from .ros_listeners import create_tank_controll_listener
from .utils import print_info, print_instructions_for_tank_controll

# Import IMUSensor (경로 확인 필요)
try:
    from isaacsim.sensors.physics import IMUSensor
except ImportError:
    IMUSensor = None

# get_footprint_path 함수
def get_footprint_path(husky_path):
    stage = get_context().get_stage()
    link_path = f"{husky_path}/base_link"
    if stage.GetPrimAtPath(link_path).IsValid(): return link_path
    footprint_path = f"{husky_path}/base_footprint"
    if stage.GetPrimAtPath(footprint_path).IsValid(): return footprint_path
    # warnings.warn(...) # 필요 시 print로 대체 가능
    print(f"[Warning] Neither base_link nor base_footprint found under {husky_path}. Using default base_footprint path.")
    return footprint_path

# --- Constants and Configuration ---
PRIM_PATH_OF_HUSKY = "/World/Ni_KI_Husky"
PRIM_PATH_OF_FOOTPRINT = get_footprint_path(PRIM_PATH_OF_HUSKY)
PRIM_PATH_OF_FRONT_BUMPER = PRIM_PATH_OF_HUSKY + "/front_bumper_link"
PRIM_PATH_OF_LIDAR = PRIM_PATH_OF_HUSKY + "/lidar_link"
LIDAR_CONFIG = "OS1_REV6_32ch10hz2048res" # Example config


class NiKiTestRosExtension(omni.ext.IExt):
    """
    Omniverse Extension for controlling and monitoring a simulated Husky robot
    in Isaac Sim, integrating with ROS2 Humble.
    """
    def on_startup(self, ext_id):
        print("[ni.ki.test.ros] ni ki test ros startup")
        print_info()  # Creates Info Box
        print("[DEBUG] id(self) =", id(self))

        # --- Initialize class attributes ---
        self._window = None
        self.label = None
        self.matrix = None
        self.translate = None
        self.rotation = None
        self.husky_cam_prim = None
        self.husky_cam = None
        self.husky_cam_depth = None
        self.lidar_sensor = None
        self.wheels = []
        #self.lidar_rp_actual_path = None # Lidar RenderProduct 경로 저장용

        # --- Build the UI ---
        self._window = ui.Window("Test ROS (Ni-KI)", width=500, height=180)
        with self._window.frame:
            with ui.VStack():
                self.label = ui.Label("Extension not initialised.", height=60, alignment=ui.Alignment.TOP, word_wrap=True)
                with ui.VStack():
                    with ui.HStack():
                        ui.Button("Init.", clicked_fn=self.on_initialize, tooltip="Sets up the robot sensors and position.")
                        ui.Button("Cease", clicked_fn=self.on_cease, tooltip="Stops wheel movement by setting target velocity to 0.")
                    with ui.HStack():
                        ui.Button("Cosmo", clicked_fn=self.on_cosmo,
                                  tooltip="Enables driving via external tank control script. (COntrolled Simulated MOtion)")
                        ui.Button("Pilot", clicked_fn=self.on_pilot,
                                  tooltip="Drives Husky forward by setting wheel target velocity.")

    def on_shutdown(self):
        print("[ni.ki.test.ros] ni ki test ros shutdown")
        if self._window:
            self._window.destroy()
        self._window = None
        self.label = None

    # --- Class Methods for Functionality ---

    def on_initialize(self):
        """Initializes the Husky simulation environment, sensors, and position."""
        if not self.label: return False
        stage = get_context().get_stage()
        self.label.text = "Start of initialization\n"
        #lidar_sensor_prim_path_ref = PRIM_PATH_OF_LIDAR + "/lidar_sensor" # 함수 시작 시 초기화
        lidar_prim_creation_success = False
        print("[DEBUG] id(self) =", id(self))

        # --- IMU 초기화 ---
        try:
            create_imu_sensor(stage, PRIM_PATH_OF_LIDAR)
            imu_prim = stage.GetPrimAtPath(PRIM_PATH_OF_LIDAR + "/imu_sensor")
            if not imu_prim.IsValid(): raise Exception("IMU prim '/imu_sensor' not valid after creation call.")
            self.label.text += " | IMU: Prim Created"
        except ImportError as e:
            print(f"IMU Error: {e}. Is 'isaacsim.sensors.physics' extension enabled?")
            self.label.text += " | IMU: Failed (Import Error)"
        except Exception as e:
            print(f"Error during IMU setup: {e}")
            self.label.text += f" | IMU: Failed ({type(e).__name__})"

        # --- 카메라 초기화 ---
        husky_cam_path = PRIM_PATH_OF_FRONT_BUMPER + "/husky_rgb_cam"
        husky_depth_cam_path = PRIM_PATH_OF_FRONT_BUMPER + "/husky_depth_cam"
        self.husky_cam_prim = stage.GetPrimAtPath(husky_cam_path)
        if not self.husky_cam_prim.IsValid():
            try:
                self.husky_cam = create_rgb_camera(stage=stage, prim_path=husky_cam_path)
                self.husky_cam_depth = create_depth_camera(stage=stage, prim_path=husky_depth_cam_path)
                self.husky_cam_prim = stage.GetPrimAtPath(husky_cam_path)
                self.label.text += " | Husky Cam: Created"
            except Exception as e:
                self.label.text += f" | Husky Cam: Creation Failed ({type(e).__name__})"
                print(f"[Warning] Failed to create Husky cameras: {e}") # warnings 대신 print
        else:
            self.label.text += " | Husky Cam: Exists"

        # --- LiDAR 및 RenderProduct 안정화 --
        try:
            lidar_prim_creation_success = create_lidar_sensor(PRIM_PATH_OF_LIDAR, LIDAR_CONFIG) # <<< 반환값 저장 방식 변경
            print(f"[DEBUG Init] create_lidar_sensor (for OmniGraph) returned: {lidar_prim_creation_success}")

            # --- RP 경로 처리 로직 **모두 제거** ---
            # if isinstance(returned_rp_path, str): ... 부터
            # print("create_lidar_sensor did not return a valid path string.") 까지 모두 제거

        except Exception as e:
            self.label.text += f" | LiDAR Prim Creation Exception: ({type(e).__name__})"
            print(f"[Warning] Exception during LiDAR prim creation call: {e}")
            lidar_prim_creation_success = False
         # --- 최종 LiDAR 상태 UI 레이블 업데이트 ---    
        lidar_status_str = "OK" if lidar_prim_creation_success else "Failed"
        self.label.text += f" | LiDAR Prim Creation: {lidar_status_str}"

        # --- IMU 데이터 읽기 시도 ---
        if stage.GetPrimAtPath(PRIM_PATH_OF_LIDAR + "/imu_sensor").IsValid():
             try:
                 if IMUSensor is None: raise ImportError("IMUSensor class could not be imported.")
                 imu_sensor_instance = IMUSensor(prim_path=PRIM_PATH_OF_LIDAR + "/imu_sensor")
                 imu_data = imu_sensor_instance.get_current_frame()
                 if isinstance(imu_data, dict) and imu_data:
                     print("IMU Data (Frame):", imu_data)
                     self.label.text += " | IMU Read: OK"
                 else: self.label.text += " | IMU Read: No Data"
             except ImportError as e:
                 print(f"IMU Reading Error: {e}")
                 self.label.text += " | IMU Read: Import Error"
             except Exception as e:
                 print(f"Error during IMU reading: {e}")
                 self.label.text += f" | IMU Read: Failed ({type(e).__name__})"
        else: self.label.text += " | IMU Read: Skipped (No Prim)"

        # --- Root Joint 제거 ---
        path_to_root_joint = PRIM_PATH_OF_HUSKY + "/root_joint"
        root_of_all_evil = stage.GetPrimAtPath(path_to_root_joint)
        if root_of_all_evil.IsValid():
            if stage.RemovePrim(path_to_root_joint):
                print("[Warning] Root Joint was removed! - NI.KI.Test.ROS")
                print("Root joint removed.")
            else:
                print("[Warning] Failed to remove root_joint. Please delete manually.")
                print("Failed to remove root_joint.")
        else: print("Root joint not found (which is good).")

        self.label.text += "\nInit finished."
        return True

    def on_cosmo(self):
        """Sets up the robot for tank control via external script."""
        if not self.label: return
        self.on_cease()

        self.label.text = "Starting Tank Control mode.\nPlease run the control script."
        print("[DEBUG] id(self) =", id(self))
        #print(f"[DEBUG Cosmo - Before Call] Value of self.lidar_rp_actual_path: {self.lidar_rp_actual_path}") # 전달 전 값 확인

        try:
            # ROS2 브릿지 초기화 시간 확보를 위해 유지 (값 조절 가능)
            delay_seconds = 2.0
            print(f"Waiting {delay_seconds} seconds before creating graph (for ROS2 bridge)...")
            time.sleep(delay_seconds)
            print("Now creating graph...")

            create_tank_controll_listener(
                PRIM_PATH_OF_HUSKY,
            )
            print_instructions_for_tank_controll()
        except Exception as e:
            self.label.text = f"Failed to start Tank Control: {e}"
            print(f"[WARN] Error creating OmniGraph: {e}")

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