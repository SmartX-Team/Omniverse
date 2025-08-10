import omni.kit.commands
import omni.usd
import omni.ui as ui
from pxr import Usd, UsdPhysics
import time
import warnings

# Local Imports
from .sensors import create_rgb_camera, create_depth_camera, create_lidar_sensor, create_imu_sensor
from .ros_listeners import create_twist_control_listener_with_domain

# Attempt to import IMUSensor, handle failure gracefully
try:
    from isaacsim.sensors.physics import IMUSensor
except ImportError:
    warnings.warn("Could not import IMUSensor from isaacsim.sensors.physics. IMU functionality will be limited.")
    IMUSensor = None

# --- Action Functions ---

def initialize_husky(stage: Usd.Stage, label_widget: ui.Label, husky_path: str, 
                    front_bumper_path: str, lidar_path: str, lidar_config: str, 
                    robot_id: int = 0) -> bool:
    """
    Initializes the Husky simulation environment: sensors, root joint removal.
    
    Args:
        stage: The current USD stage
        label_widget: The UI label to display feedback
        husky_path: The USD path to the main Husky prim
        front_bumper_path: The USD path to the front bumper link (for cameras)
        lidar_path: The USD path to the lidar link (for lidar and IMU)
        lidar_config: The configuration name for the LiDAR sensor
        robot_id: Unique identifier for this robot
        
    Returns:
        True if initialization sequence completed, False otherwise
    """
    print(f"[DEBUG] Initializing robot {robot_id} at: {husky_path}")
    
    if not label_widget or not stage:
        print("[ERROR] Stage or Label Widget not provided for initialization.")
        return False

    label_widget.text = f"Initializing Robot {robot_id}..."
    start_time = time.time()
    initialization_steps = []

    # --- 1. IMU Initialization ---
    imu_sensor_path = lidar_path + "/imu_sensor"
    try:
        if create_imu_sensor(stage, lidar_path):
            initialization_steps.append("IMU Prim: OK")
            print(f"[Info] IMU sensor created for robot {robot_id}")
        else:
            raise Exception("create_imu_sensor returned False")
    except Exception as e:
        error_msg = f"IMU Failed: {e}"
        print(f"[ERROR] Robot {robot_id}: {error_msg}")
        initialization_steps.append(error_msg)

    # --- 2. Camera Initialization ---
    husky_cam_rgb_path = front_bumper_path + "/husky_rgb_cam"
    husky_cam_depth_path = front_bumper_path + "/husky_depth_cam"
    
    rgb_cam_prim = stage.GetPrimAtPath(husky_cam_rgb_path)
    if not rgb_cam_prim or not rgb_cam_prim.IsValid():
        try:
            create_rgb_camera(stage=stage, prim_path=husky_cam_rgb_path)
            create_depth_camera(stage=stage, prim_path=husky_cam_depth_path)
            
            if not stage.GetPrimAtPath(husky_cam_rgb_path).IsValid() or \
               not stage.GetPrimAtPath(husky_cam_depth_path).IsValid():
                raise Exception("Camera prims not valid after creation")
            initialization_steps.append("Cameras: Created")
        except Exception as e:
            error_msg = f"Cameras Failed: {e}"
            print(f"[ERROR] Robot {robot_id}: {error_msg}")
            initialization_steps.append(error_msg)
    else:
        initialization_steps.append("Cameras: Already Exist")

    # --- 3. LiDAR Initialization ---
    try:
        if create_lidar_sensor(lidar_path, lidar_config):
            initialization_steps.append("LiDAR Prim: OK")
            print(f"[Info] LiDAR sensor created for robot {robot_id}")
        else:
            raise Exception("create_lidar_sensor returned False")
    except Exception as e:
        error_msg = f"LiDAR Failed: {e}"
        print(f"[ERROR] Robot {robot_id}: {error_msg}")
        initialization_steps.append(error_msg)

    # --- 4. IMU Read Check ---
    imu_prim_for_read = stage.GetPrimAtPath(imu_sensor_path)
    if imu_prim_for_read and imu_prim_for_read.IsValid():
        if IMUSensor:
            try:
                imu_sensor_instance = IMUSensor(prim_path=imu_sensor_path)
                initialization_steps.append("IMU Read Check: Ready")
            except Exception as e:
                initialization_steps.append(f"IMU Read Check Failed: {e}")
        else:
            initialization_steps.append("IMU Read Check: Skipped (Module not imported)")
    else:
        initialization_steps.append("IMU Read Check: Skipped (No Prim)")

    # --- 5. Root Joint Removal ---
    path_to_root_joint = husky_path + "/root_joint"
    root_joint_prim = stage.GetPrimAtPath(path_to_root_joint)
    
    if root_joint_prim and root_joint_prim.IsValid():
        try:
            if stage.RemovePrim(path_to_root_joint):
                print(f"[Info] Root joint removed for robot {robot_id}")
                initialization_steps.append("RootJoint: Removed")
            else:
                initialization_steps.append("RootJoint: Removal Failed")
        except Exception as e:
            initialization_steps.append(f"RootJoint Removal Failed: {e}")
    else:
        initialization_steps.append("RootJoint: Not Found")

    # --- Final Update ---
    end_time = time.time()
    duration = end_time - start_time
    
    label_widget.text = f"Robot {robot_id} Init Summary:\n"
    label_widget.text += "\n".join(f"- {s}" for s in initialization_steps)
    label_widget.text += f"\n\nCompleted in {duration:.2f}s"
    
    print(f"[Info] Robot {robot_id} initialization completed in {duration:.2f} seconds")
    return True


def create_ros2_control_graph(stage: Usd.Stage, label_widget: ui.Label, 
                             robot_path: str, robot_id: int = 0, 
                             domain_id: int = 0) -> bool:
    """
    Create ROS2 control graph for a robot with specified Domain ID.
    
    Args:
        stage: The current USD stage
        label_widget: The UI label to display feedback
        robot_path: The USD path to the robot
        robot_id: Unique identifier for this robot
        domain_id: ROS2 Domain ID for network isolation
        
    Returns:
        True if graph created successfully, False otherwise
    """
    print(f"[DEBUG] Creating ROS2 control graph for robot {robot_id} with domain {domain_id}")
    
    if not stage:
        print("[ERROR] Stage not provided")
        return False
    
    # Dynamic graph path based on robot_id
    graph_path = f"/husky_ros_graph_{robot_id}"
    
    # Delete existing graph if present
    if stage.GetPrimAtPath(graph_path).IsValid():
        print(f"[Info] Deleting existing graph at {graph_path}")
        try:
            omni.kit.commands.execute("DeletePrims", paths=[graph_path])
            time.sleep(0.1)  # Brief pause for cleanup
        except Exception as e:
            print(f"[Error] Failed to delete existing graph: {e}")
    
    if label_widget:
        label_widget.text = f"Creating Graph (Domain: {domain_id})..."
    
    try:
        # Call the modified listener function with domain support
        success = create_twist_control_listener_with_domain(
            prim_path_of_husky=robot_path,
            robot_id=robot_id,
            domain_id=domain_id
        )
        
        if success:
            if label_widget:
                label_widget.text = f"Graph Active (Domain: {domain_id})"
            print(f"[Info] ROS2 control graph created successfully for robot {robot_id}")
            return True
        else:
            if label_widget:
                label_widget.text = "Graph Creation Failed"
            print(f"[Error] Failed to create ROS2 control graph for robot {robot_id}")
            return False
            
    except Exception as e:
        error_msg = f"Graph creation error: {e}"
        if label_widget:
            label_widget.text = error_msg
        print(f"[ERROR] {error_msg}")
        return False


def delete_ros2_control_graph(stage: Usd.Stage, label_widget: ui.Label, 
                             robot_path: str, robot_id: int = 0) -> bool:
    """
    Delete the ROS2 control graph for a specific robot.
    
    Args:
        stage: The current USD stage
        label_widget: The UI label to display feedback (optional)
        robot_path: The USD path to the robot
        robot_id: Unique identifier for this robot
        
    Returns:
        True if graph deleted successfully or didn't exist, False on error
    """
    print(f"[DEBUG] Deleting ROS2 control graph for robot {robot_id}")
    
    if not stage:
        print("[ERROR] Stage not provided")
        return False
    
    # Dynamic graph path based on robot_id
    graph_path = f"/husky_ros_graph_{robot_id}"
    
    if stage.GetPrimAtPath(graph_path).IsValid():
        try:
            omni.kit.commands.execute("DeletePrims", paths=[graph_path])
            
            if label_widget:
                label_widget.text = "Graph Deleted"
            
            print(f"[Info] ROS2 control graph deleted for robot {robot_id}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete graph: {e}"
            if label_widget:
                label_widget.text = error_msg
            print(f"[ERROR] {error_msg}")
            return False
    else:
        print(f"[Info] No graph found at {graph_path} to delete")
        if label_widget:
            label_widget.text = "No graph to delete"
        return True