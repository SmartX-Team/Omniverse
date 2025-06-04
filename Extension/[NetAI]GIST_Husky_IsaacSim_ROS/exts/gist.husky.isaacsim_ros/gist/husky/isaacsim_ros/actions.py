import omni.kit.commands # Potentially needed for specific commands
import omni.usd
import omni.ui as ui # For type hinting label_widget
from pxr import Usd, Gf , UsdPhysics # USD Prim, Vec3f/d, Quatf/d
import time
import warnings

# Local Imports (using relative paths)
from .sensors import create_rgb_camera, create_depth_camera, create_lidar_sensor, create_imu_sensor
from .ros_listeners import create_tank_controll_listener
from .utils import print_instructions_for_tank_controll, get_footprint_path # Import required utils



# 멀티 로봇으로 변경할꺼면 꼭 지우삼; 구현하다가 시간 없어서 중단했었음
GRAPH_PATH = "/husky_ros_graph"

# Attempt to import IMUSensor, handle failure gracefully
try:
    from isaacsim.sensors.physics import IMUSensor
except ImportError:
    warnings.warn("Could not import IMUSensor from isaacsim.sensors.physics. IMU functionality will be limited.")
    IMUSensor = None # Define as None if import fails

# --- Action Functions ---

def initialize_husky(stage: Usd.Stage, label_widget: ui.Label, husky_path: str, front_bumper_path: str, lidar_path: str, lidar_config: str) -> bool:
    """
    Initializes the Husky simulation environment: sensors, root joint removal.
    Updates the provided label widget with status messages.

    Args:
        stage: The current USD stage.
        label_widget: The UI label to display feedback.
        husky_path: The USD path to the main Husky prim.
        front_bumper_path: The USD path to the front bumper link (for cameras).
        lidar_path: The USD path to the lidar link (for lidar and IMU).
        lidar_config: The configuration name for the LiDAR sensor.

    Returns:
        True if initialization sequence completed (doesn't guarantee success of all steps), False otherwise.
    """
    print(f"[DEBUG actions.py] Entered initialize_husky for: {husky_path}")
    if not label_widget or not stage:
        print("[ERROR actions.py] Stage or Label Widget not provided for initialization.")
        return False

    label_widget.text = "Initializing Husky...\n"
    print(f"[DEBUG actions.py] initialize_husky called for {husky_path}")
    start_time = time.time()
    initialization_steps = [] # Keep track of steps for summary

    # --- 1. IMU Initialization ---
    imu_sensor_path = lidar_path + "/imu_sensor"
    try:

        if create_imu_sensor(stage, lidar_path):
            initialization_steps.append("IMU Prim: OK")
            print("[Info] create_imu_sensor reported success.")
        else:
            raise Exception("create_imu_sensor function returned False, indicating failure.")
            
    except Exception as e:
        error_msg = f"IMU Failed ({type(e).__name__}: {e})"
        print(f"[ERROR] {error_msg}")
        initialization_steps.append(error_msg)

    # --- 2. Camera Initialization ---
    husky_cam_rgb_path = front_bumper_path + "/husky_rgb_cam"
    husky_cam_depth_path = front_bumper_path + "/husky_depth_cam"
    # Check if cameras already exist
    rgb_cam_prim = stage.GetPrimAtPath(husky_cam_rgb_path)
    if not rgb_cam_prim or not rgb_cam_prim.IsValid():
        try:
            # Pass stage if required by the creation functions
            create_rgb_camera(stage=stage, prim_path=husky_cam_rgb_path)
            create_depth_camera(stage=stage, prim_path=husky_cam_depth_path)
            # Verify creation
            if not stage.GetPrimAtPath(husky_cam_rgb_path).IsValid() or \
               not stage.GetPrimAtPath(husky_cam_depth_path).IsValid():
                raise Exception("Camera prims not valid after creation calls.")
            initialization_steps.append("Cameras: Created")
        except Exception as e:
            error_msg = f"Cameras Failed ({type(e).__name__}: {e})"
            print(f"[ERROR] {error_msg}")
            initialization_steps.append(error_msg)
    else:
        initialization_steps.append("Cameras: Existed")

    # --- 3. LiDAR Initialization ---
    lidar_prim_creation_success = False
    try:
        # create_lidar_sensor handles prim creation and graph setup
        lidar_prim_creation_success = create_lidar_sensor(lidar_path, lidar_config)
        if lidar_prim_creation_success:
             initialization_steps.append("LiDAR Prim: OK")
             print(f"[DEBUG Init] create_lidar_sensor reported success for {lidar_path}")
        else:
             # The function might return False without raising an exception
             raise Exception("create_lidar_sensor returned False, indicating failure.")
    except Exception as e:
        error_msg = f"LiDAR Failed ({type(e).__name__}: {e})"
        print(f"[ERROR] {error_msg}")
        initialization_steps.append(error_msg)
        lidar_prim_creation_success = False # Ensure flag is False

    # --- 4. Attempt IMU Data Read (Post-Initialization Check) ---
    # Note: Reading data immediately might not yield results if simulation hasn't stepped.
    imu_prim_for_read = stage.GetPrimAtPath(imu_sensor_path)
    if imu_prim_for_read and imu_prim_for_read.IsValid():
        if IMUSensor: # Check if the class was imported successfully
            try:
                imu_sensor_instance = IMUSensor(prim_path=imu_sensor_path)
                # Optional: Attempt to get data, but expect it might be empty initially
                # imu_data = imu_sensor_instance.get_current_frame()
                # if isinstance(imu_data, dict) and imu_data:
                #     print("IMU Initial Data (Frame):", imu_data)
                #     initialization_steps.append("IMU Read Check: OK (See Console)")
                # else:
                #     initialization_steps.append("IMU Read Check: No Data Yet")
                initialization_steps.append("IMU Read Check: Ready (Instantiated)") # More realistic check
            except Exception as e:
                error_msg = f"IMU Read Check Failed ({type(e).__name__}: {e})"
                print(f"[ERROR] {error_msg}")
                initialization_steps.append(error_msg)
        else:
             initialization_steps.append("IMU Read Check: Skipped (IMUSensor not imported)")
    else:
        initialization_steps.append("IMU Read Check: Skipped (No Prim)")

    # --- 5. Root Joint Removal ---
    path_to_root_joint = husky_path + "/root_joint"
    root_joint_prim = stage.GetPrimAtPath(path_to_root_joint)
    if root_joint_prim and root_joint_prim.IsValid():
        try:
            if stage.RemovePrim(path_to_root_joint):
                print(f"[Info] Root Joint '{path_to_root_joint}' was removed.")
                initialization_steps.append("RootJoint: Removed")
            else:
                # This case might be rare if IsValid passed
                print(f"[Warning] Failed to remove root_joint '{path_to_root_joint}'.")
                initialization_steps.append("RootJoint: Removal Failed")
        except Exception as e:
             error_msg = f"RootJoint Removal Failed ({type(e).__name__}: {e})"
             print(f"[ERROR] {error_msg}")
             initialization_steps.append(error_msg)
    else:
        print(f"[Info] Root joint '{path_to_root_joint}' not found (or already removed).")
        initialization_steps.append("RootJoint: Not Found")

    # --- Final Update ---
    end_time = time.time()
    duration = end_time - start_time
    label_widget.text = "Initialization Summary:\n" + "\n".join(f"- {s}" for s in initialization_steps)
    label_widget.text += f"\n\nInit finished in {duration:.2f} seconds."
    print(f"[Info] Initialization sequence completed in {duration:.2f} seconds.")

    return True

def start_cosmo_mode(stage: Usd.Stage, label_widget: ui.Label, husky_path: str):
    """
    Sets up the robot for tank control via an external ROS2 script.
    Calls cease_movement first and then creates the ROS listener graph.

    Args:
        stage: The current USD stage.
        label_widget: The UI label to display feedback.
        husky_path: The USD path to the main Husky prim.
    """
    print(f"[DEBUG actions.py] Entered start_cosmo_mode for: {husky_path}")
    if not label_widget or not stage:
        print("[ERROR actions.py] Stage or Label Widget not provided for Cosmo mode.")
        return
    print(f"[DEBUG actions.py] start_cosmo_mode called for {husky_path}")

    # 1. Stop any existing movement
    print("[Info] Ceasing existing movement before enabling Cosmo mode.")
    cease_movement(stage, label_widget, husky_path, update_label=False) # Avoid intermediate label update

    # 2. Update UI and print instructions
    label_widget.text = "Starting Tank Control (Cosmo) mode..."
    print_instructions_for_tank_controll() # Show console instructions

    # 3. Wait briefly for ROS bridge components to potentially initialize (adjust as needed)
    delay_seconds = 2.0
    print(f"[Info] Waiting {delay_seconds} seconds before creating ROS listener graph...")
    # NOTE: time.sleep() blocks the main thread. For long delays or complex apps,
    # consider omni.kit.app.get_app().next_update_async() or asyncio.
    time.sleep(delay_seconds)

    # 4. Create the ROS listener OmniGraph
    try:
        print("[Info] Creating Tank Control listener graph...")
        # Ensure create_tank_controll_listener takes necessary args (currently just husky_path)
        create_tank_controll_listener(husky_path)
        label_widget.text += "\nListener graph created. Ready for external script."
        print("[Info] Tank Control listener graph created successfully.")
    except Exception as e:
        error_msg = f"Failed to start Tank Control: {type(e).__name__}: {e}"
        label_widget.text = error_msg
        print(f"[ERROR] {error_msg}")


def _apply_wheel_drive(stage: Usd.Stage, husky_path: str, target_velocity_component: float, stiffness: float) -> tuple[int, int]:
    """Internal helper to apply drive settings to Husky wheels."""
    # Determine base link/footprint path robustly
    base_path = get_footprint_path(husky_path) # Use the utility function
    if not stage.GetPrimAtPath(base_path).IsValid():
        print(f"[ERROR] Base path '{base_path}' not found for Husky.")
        return 0, 4 # 0 wheels set, 4 expected

    wheel_joint_names = [
        "back_left_wheel_joint", "back_right_wheel_joint",
        "front_left_wheel_joint", "front_right_wheel_joint"
    ]
    wheel_paths = [f"{base_path}/{name}" for name in wheel_joint_names]
    expected_wheels = len(wheel_paths)
    wheels_set_count = 0

    # IMPORTANT: Determine the correct rotation axis for the wheels in your USD asset.
    # Common axes are X or Y. If wheels rotate around Y: Gf.Vec3f(0, vel, 0)
    # If wheels rotate around X: Gf.Vec3f(vel, 0, 0)
    # Assuming Y-axis rotation for this example:
    target_velocity_float = float(target_velocity_component) # Using Float precision

    for joint_path in wheel_paths:
        wheel_prim = stage.GetPrimAtPath(joint_path)
        if wheel_prim and wheel_prim.IsValid():
            try:
                # Use DriveAPI - Apply ensures it exists
                # Use "angular" drive type for rotation
                drive_api = UsdPhysics.DriveAPI.Apply(wheel_prim, "angular")

                # Set Stiffness
                stiffness_attr = drive_api.CreateStiffnessAttr() # Creates if doesn't exist
                stiffness_attr.Set(stiffness)

                # Husky 모터 사양에 맞춘 damping 값은 120~200 정도라고 하는데데
                # 실제 Husky PM45L-048 모터의 최대 토크(49.3 Nm)를 고려한 값
                #However, it seems there is an issue between the models, as the force values must be set significantly higher than in reality to achieve smooth operation.
                damping = 6000  #  지속적으로 교정 작업 진행중중
                damping_attr = drive_api.CreateDampingAttr()
                damping_attr.Set(damping)

                # Set Target Velocity
                target_vel_attr = drive_api.CreateTargetVelocityAttr()
                target_vel_attr.Set(target_velocity_float)

                # Set Max Force - This is crucial for the drive to work properly
                # Husky PM45L-048 모터의 최대 토크: 49.3 N·m 이나 지금 여러 문제로 값을 상당히 많이 높여야함
                #However, it seems there is an issue between the models, as the force values must be set significantly higher than in reality to achieve smooth operation.
                max_force_attr = drive_api.CreateMaxForceAttr()
                max_force_attr.Set(100000)  

                wheels_set_count += 1
                # print(f"[DEBUG] Applied drive to {joint_path}")

            except Exception as e:
                print(f"[Warning] Failed to apply drive attributes to {joint_path}: {type(e).__name__}: {e}")
        else:
            print(f"[Warning] Wheel joint prim not found or invalid: {joint_path}")

    return wheels_set_count, expected_wheels


def pilot_forward(stage: Usd.Stage, label_widget: ui.Label, husky_path: str):
    """
    Drives the Husky forward by setting a fixed target velocity on wheel joints
    using the Usd.DriveAPI.

    Args:
        stage: The current USD stage.
        label_widget: The UI label to display feedback.
        husky_path: The USD path to the main Husky prim.
    """
    print(f"[DEBUG actions.py] Entered pilot_forward for: {husky_path}")
    if not label_widget or not stage:
        print("[ERROR actions.py] Stage or Label Widget not provided for Pilot mode.")
        return
    print(f"[DEBUG actions.py] pilot_forward called for {husky_path}")

    if stage.GetPrimAtPath(GRAPH_PATH).IsValid():
        print(f"[Info] Deleting existing OmniGraph '{GRAPH_PATH}' before entering Pilot mode.")
        try:
            omni.kit.commands.execute("DeletePrims", paths=[GRAPH_PATH])
            # 그래프 삭제 후 안정적으로 반영될 시간 추가
            # time.sleep(0.1)
        except Exception as e:
            print(f"[Error] Failed to delete graph '{GRAPH_PATH}': {e}")

    # 문서에 따른 현실적 목표 속도
    # Husky 최대 선속도 1.0 m/s, 바퀴 반지름 0.165m
    # 최대 각속도: 1.0 / 0.165 ≈ 6.06 rad/s
    # 테스트를 위해 절반 정도의 속도 사용
    target_velocity = 6.06
    stiffness = 0     # Low stiffness for velocity control
    label_widget.text = f"Engaging Pilot Mode (Target Vel: {target_velocity:.1f})"

    wheels_set, expected_wheels = _apply_wheel_drive(stage, husky_path, target_velocity, stiffness)

    if wheels_set == expected_wheels:
        label_widget.text += f"\nApplied drive to {wheels_set}/{expected_wheels} wheels."
        print(f"[Info] Pilot mode engaged for {wheels_set} wheels.")
    else:
        label_widget.text += f"\nWarning: Applied drive to only {wheels_set}/{expected_wheels} wheels."
        print(f"[Warning] Pilot mode: Could only apply drive to {wheels_set}/{expected_wheels} wheels.")


def cease_movement(stage: Usd.Stage, label_widget: ui.Label, husky_path: str, update_label: bool = True):
    """
    Stops Husky movement by setting wheel target velocities to zero using Usd.DriveAPI.

    Args:
        stage: The current USD stage.
        label_widget: The UI label to display feedback.
        husky_path: The USD path to the main Husky prim.
        update_label: Whether to update the label widget (set False if called internally).
    """
    print(f"[DEBUG actions.py] Entered cease_movement for: {husky_path}")
    if update_label and not label_widget:
        print("[ERROR actions.py] Label Widget not provided for Cease movement.")
        return
    if not stage:
        print("[ERROR actions.py] Stage not provided for Cease movement.")
        return

    print(f"[DEBUG actions.py] cease_movement called for {husky_path}")
    if update_label:
        label_widget.text = "Ceasing Movement..."

    if stage.GetPrimAtPath(GRAPH_PATH).IsValid():
        print(f"[Info] Deleting existing OmniGraph '{GRAPH_PATH}' before entering Pilot mode.")
        try:
            omni.kit.commands.execute("DeletePrims", paths=[GRAPH_PATH])
            # 그래프 삭제 후 안정적으로 반영될 시간 추가
            # time.sleep(0.1)
        except Exception as e:
            print(f"[Error] Failed to delete graph '{GRAPH_PATH}': {e}")

    graph_path = "/husky_ros_graph"
    if stage.GetPrimAtPath(graph_path).IsValid():
        print(f"[Info] Deleting existing OmniGraph '{graph_path}' before entering Pilot mode.")
        omni.kit.commands.execute("DeletePrims", paths=[graph_path])
    target_velocity = 0.0 # Stop
    stiffness = 0.0     # Maintain low stiffness

    wheels_set, expected_wheels = _apply_wheel_drive(stage, husky_path, target_velocity, stiffness)

    if update_label:
        label_widget.text += f"\nMovement ceased ({wheels_set}/{expected_wheels} wheels stopped)."
    print(f"[Info] Cease movement: Applied zero velocity to {wheels_set}/{expected_wheels} wheels.")