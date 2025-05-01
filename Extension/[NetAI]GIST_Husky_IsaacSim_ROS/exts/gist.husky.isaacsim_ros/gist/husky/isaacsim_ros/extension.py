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

# Import IMUSensor (경로 확인 필요)
try:
    from isaacsim.sensors.physics import IMUSensor
except ImportError:
    IMUSensor = None

# --- Constants and Configuration ---
PRIM_PATH_OF_HUSKY = "/World/Ni_KI_Husky"
#PRIM_PATH_OF_FOOTPRINT = get_footprint_path(PRIM_PATH_OF_HUSKY)
PRIM_PATH_OF_FRONT_BUMPER = PRIM_PATH_OF_HUSKY + "/front_bumper_link"
PRIM_PATH_OF_LIDAR = PRIM_PATH_OF_HUSKY + "/lidar_link"
LIDAR_CONFIG = "OS1_REV6_32ch10hz2048res" # Example config


class NiKiTestRosExtension(omni.ext.IExt):
    """
    Omniverse Extension UI shell for controlling and monitoring a simulated Husky robot
    in Isaac Sim, integrating with ROS2 Humble. Delegates actions to the 'actions' module.
    """
    def on_startup(self, ext_id: str):
        """Called upon extension startup."""
        print(f"[{ext_id}] NiKiTestRosExtension startup")
        from . import actions  # Import the new actions module
        from . import utils    # Import the utils module        
        utils.print_info() # Display informational message from utils

        self._window = None
        self.label = None
        # Get the USD stage context once for efficiency
        self.stage = get_context().get_stage()
        if not self.stage:
            print("[ERROR] Failed to get USD Stage.")
            # Optionally disable UI or show an error message
            return

        print(f"[DEBUG] Extension Instance ID: {id(self)}")

        # --- Build the User Interface ---
        self._window = ui.Window("Test ROS (Ni-KI)", width=500, height=300)
        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                # Label for providing feedback to the user
                self.label = ui.Label("Extension ready. Press 'Init.' to start.",
                                      height=60, alignment=ui.Alignment.TOP, word_wrap=True)

                # --- UI Buttons ---
                # Buttons trigger functions in the 'actions' module via lambda functions.
                # Necessary context (stage, label widget, paths) is passed as arguments.
                with ui.VStack(spacing=5):
                    with ui.HStack(spacing=5):
                        ui.Button("Init.",
                                  clicked_fn=lambda: actions.initialize_husky(
                                      self.stage, self.label, PRIM_PATH_OF_HUSKY,
                                      PRIM_PATH_OF_FRONT_BUMPER, PRIM_PATH_OF_LIDAR,
                                      LIDAR_CONFIG
                                  ),
                                  tooltip="Initializes sensors, removes root joint, and prepares the robot.")
                        ui.Button("Cease",
                                  clicked_fn=lambda: actions.cease_movement(
                                      self.stage, self.label, PRIM_PATH_OF_HUSKY
                                  ),
                                  tooltip="Stops Husky wheel movement immediately (sets target velocity to 0).")

                    with ui.HStack(spacing=5):
                        ui.Button("Cosmo",
                                  clicked_fn=lambda: actions.start_cosmo_mode(
                                      self.stage, self.label, PRIM_PATH_OF_HUSKY
                                  ),
                                  tooltip="Enables COntrolled Simulated MOtion via external tank control script (ROS2).")
                        ui.Button("Pilot",
                                  clicked_fn=lambda: actions.pilot_forward(
                                      self.stage, self.label, PRIM_PATH_OF_HUSKY
                                  ),
                                  tooltip="Drives the Husky forward using a fixed wheel velocity (simple test).")

    def on_shutdown(self):
        """Called upon extension shutdown."""
        print("[ni.ki.test.ros] NiKiTestRosExtension shutdown")
        # Clean up the UI window if it exists
        if self._window:
            self._window.destroy()
        self._window = None
        self.label = None
        self.stage = None # Release reference, although context manages the stage lifecycle
        print("[DEBUG] Shutdown complete.")