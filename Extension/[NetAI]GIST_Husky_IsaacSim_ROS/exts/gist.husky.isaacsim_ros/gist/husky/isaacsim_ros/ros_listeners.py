# Creates graph based node systems in Isaac Sim for the purpose of listening to ROS2 Topics
# and moving husky in accordance with those.
# It's important to note that *ONLY ONE* of the two should be active and *NOT BOTH* at once!
# The options are: Joystick or Tank Controll

# Used to create a graph node
import omni
import omni.graph.core as og
import omni.usd
from omni.usd import get_context # Need get_context for the check
import warnings
from pxr import UsdPhysics
import traceback # 오류 추적 위해 추가
import omni.kit.commands

# --- get_py_script_node_type 함수는 현재 사용하지 않음 ---
# def get_py_script_node_type(): ...


# --- Function to check and create Tank Control Listener ---
def create_tank_controll_listener(prim_path_of_husky, lidar_render_product_actual_path=None):
    print(f"[DEBUG Listener - Received] lidar_render_product_actual_path: {lidar_render_product_actual_path}")

    graph_path = "/tank_control_graph"
    stage = omni.usd.get_context().get_stage()
    if not stage: print("Error: Could not get USD stage."); return

    # --- 경로 유효성 검사 로직 ---
    print("Validating required prim paths and APIs...")
    valid_paths = {}
    validation_passed = True
    lidar_publishing_possible = False # 초기화

    # ... (Controller 경로, husky_root 경로, 동적 TF 경로 확인 로직) ...
    husky_prim = stage.GetPrimAtPath(prim_path_of_husky)
    husky_base_link_path = f"{prim_path_of_husky}/base_link"
    husky_base_link_prim = stage.GetPrimAtPath(husky_base_link_path)
    controller_target_path = None
    if husky_base_link_prim.IsValid() and husky_base_link_prim.HasAPI(UsdPhysics.ArticulationRootAPI):
        controller_target_path = husky_base_link_path
        valid_paths["husky_root"] = prim_path_of_husky
        print(f"  [OK] Controller Target Path: {controller_target_path}")
        print(f"  [OK] Husky Root Path for TF: {valid_paths['husky_root']}")
    elif husky_prim.IsValid() and husky_prim.HasAPI(UsdPhysics.ArticulationRootAPI):
        controller_target_path = prim_path_of_husky
        valid_paths["husky_root"] = prim_path_of_husky
        print(f"  [OK] Controller Target Path: {controller_target_path}")
        print(f"  [OK] Husky Root Path for TF: {valid_paths['husky_root']}")
    else:
        print(f"Error: Prim at {prim_path_of_husky} or {husky_base_link_path} does not exist or does not have ArticulationRootAPI.")
        validation_passed = False
    if "husky_root" not in valid_paths:
        print(f"Error: Could not determine a valid 'husky_root' path for TF.")
        validation_passed = False

    lidar_link_path = f"{prim_path_of_husky}/lidar_link"
    front_bumper_link_path = f"{prim_path_of_husky}/front_bumper_link"
    imu_sensor_path = f"{lidar_link_path}/imu_sensor"
    paths_to_check_for_dynamic_tf = {
        "lidar_link": lidar_link_path, "front_bumper_link": front_bumper_link_path, "imu_sensor": imu_sensor_path,
    }
    valid_tf_sensor_paths = []
    for name, path in paths_to_check_for_dynamic_tf.items():
        prim = stage.GetPrimAtPath(path)
        if prim.IsValid():
            print(f"  [OK] Dynamic TF Target Candidate Path Valid: {path}")
            valid_paths[name] = path
            valid_tf_sensor_paths.append(path)
        else:
            # warnings.warn(...) # print로 대체
            print(f"  [Warning] Prim for Dynamic TF Target {name} not found at {path}. It will be excluded.")
    dynamic_tf_targets = []
    if validation_passed:
        dynamic_tf_targets = [valid_paths["husky_root"]] + valid_tf_sensor_paths
        if len(dynamic_tf_targets) <= 1:
            # warnings.warn(...) # print로 대체
             print("[Warning] Dynamic TF target list only contains husky_root. No additional sensor links found or validated.")
        print(f"  [Info] Dynamic TF Targets: {dynamic_tf_targets}")


    # --- LiDAR 경로 유효성 검사 ---
    if lidar_render_product_actual_path and isinstance(lidar_render_product_actual_path, str) and stage.GetPrimAtPath(lidar_render_product_actual_path).IsValid():
        print(f"  [OK] LiDAR RenderProduct Path Valid: {lidar_render_product_actual_path}")
        valid_paths["lidar_render_product"] = lidar_render_product_actual_path
        lidar_publishing_possible = True
    else:
        print(f"  [Warning - Skipping LiDAR] Received path type: {type(lidar_render_product_actual_path)}, value: '{lidar_render_product_actual_path}'")
        print(f"  [Warning] Valid LiDAR RenderProduct path ('{lidar_render_product_actual_path}') was not provided or prim not found. LiDAR publishing will be skipped.")
        lidar_publishing_possible = False

    if not validation_passed:
        print("Critical validation failed (Controller/husky_root path). Cannot create OmniGraph.")
        return
    print("Path validation finished.")

    # --- 그래프 삭제 로직 ---
    if stage.GetPrimAtPath(graph_path).IsValid():
        print(f"Deleting existing graph at {graph_path} for fresh start.")
        omni.kit.commands.execute("DeletePrims", paths=[graph_path])

    # --- 단일 og.Controller.edit 호출 ---
    print(f"--- DEBUG: Preparing to create graph. lidar_publishing_possible = {lidar_publishing_possible} ---") # 디버그 메시지 수정
    keys = og.Controller.Keys
    try:
        # --- ★★★ 디버깅 Print 추가 ★★★ ---
        print(f"--- DEBUG: Defining nodes_to_create. Including lidar_pub: {lidar_publishing_possible} ---")
        nodes_to_create = [
            # Controller, TF 노드들
            ("phys_step", "isaacsim.core.nodes.OnPhysicsStep"),
            ("ack_sub", "isaacsim.ros2.bridge.ROS2SubscribeAckermannDrive"),
            ("array", "omni.graph.nodes.ConstructArray"),
            ("array_add1", "omni.graph.nodes.ArrayInsertValue"),
            ("array_add2", "omni.graph.nodes.ArrayInsertValue"),
            ("array_add3", "omni.graph.nodes.ArrayInsertValue"),
            ("controller", "isaacsim.core.nodes.IsaacArticulationController"),
            ("sim_time", "isaacsim.core.nodes.IsaacReadSimulationTime"),
            ("tf_static_pub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
            ("tf_dynamic_pub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
            # 조건부 LIDAR 노드 생성
            *([("lidar_pub", "isaacsim.ros2.bridge.ROS2RtxLidarHelper")] if lidar_publishing_possible else [])
        ]
        print(f"--- DEBUG: nodes_to_create defined: {nodes_to_create}")

        print(f"--- DEBUG: Defining values_to_set. Including lidar_pub values: {lidar_publishing_possible and 'lidar_render_product' in valid_paths} ---")
        values_to_set = [
            # Controller, TF 값 설정
            ("array.inputs:arraySize", 1),
            ("controller.inputs:robotPath", controller_target_path),
            ("controller.inputs:jointNames", ["back_right_wheel_joint", "back_left_wheel_joint", "front_right_wheel_joint", "front_left_wheel_joint"]),
            ("ack_sub.inputs:topicName", "/ackermann_cmd"),
            ("tf_static_pub.inputs:targetPrims", [valid_paths.get("husky_root")]),
            ("tf_static_pub.inputs:topicName", "/tf_static"),
            ("tf_static_pub.inputs:staticPublisher", True),
            ("tf_dynamic_pub.inputs:targetPrims", dynamic_tf_targets),
            ("tf_dynamic_pub.inputs:topicName", "/tf"),
            ("tf_dynamic_pub.inputs:staticPublisher", False),
            # 조건부 LIDAR 값 설정
            *([
                ("lidar_pub.inputs:renderProductPath", valid_paths.get("lidar_render_product")),
                ("lidar_pub.inputs:topicName", "/pointcloud"),
                ("lidar_pub.inputs:frameId", "lidar_link"),
             ] if lidar_publishing_possible and "lidar_render_product" in valid_paths else [])
        ]
        print(f"--- DEBUG: values_to_set defined: {values_to_set}")

        print(f"--- DEBUG: Defining connections. Including lidar_pub connections: {lidar_publishing_possible and 'lidar_render_product' in valid_paths} ---")
        connections = [
            # Controller, TF 연결
            ("phys_step.outputs:step", "ack_sub.inputs:execIn"),
            ("phys_step.outputs:step", "controller.inputs:execIn"),
            ("array.outputs:array", "array_add1.inputs:array"),
            ("ack_sub.outputs:speed", "array.inputs:input0"),
            ("ack_sub.outputs:speed", "array_add2.inputs:value"),
            ("ack_sub.outputs:jerk", "array_add1.inputs:value"),
            ("ack_sub.outputs:jerk", "array_add3.inputs:value"),
            ("array_add1.outputs:array", "array_add2.inputs:array"),
            ("array_add2.outputs:array", "array_add3.inputs:array"),
            ("array_add3.outputs:array","controller.inputs:velocityCommand"),
            ("phys_step.outputs:step", "tf_static_pub.inputs:execIn"),
            ("sim_time.outputs:simulationTime", "tf_static_pub.inputs:timeStamp"),
            ("phys_step.outputs:step", "tf_dynamic_pub.inputs:execIn"),
            ("sim_time.outputs:simulationTime", "tf_dynamic_pub.inputs:timeStamp"),
            # 조건부 LIDAR 연결
            *([
                ("phys_step.outputs:step", "lidar_pub.inputs:execIn"),
                ("sim_time.outputs:simulationTime", "lidar_pub.inputs:timeStamp"),
             ] if lidar_publishing_possible and "lidar_render_product" in valid_paths else [])
        ]
        print(f"--- DEBUG: connections defined: {connections}")
        # --- 디버깅 Print 끝 ---

        og.Controller.edit(
            { # Graph settings
                "graph_path": graph_path,
                "evaluator_name": "execution",
                "pipeline_stage": og.GraphPipelineStage.GRAPH_PIPELINE_STAGE_ONDEMAND,
            },
            { # Edits
                keys.CREATE_NODES: nodes_to_create,
                keys.SET_VALUES: values_to_set,
                keys.CONNECT: connections,
            }
        )
        print(f"Successfully created comprehensive graph at {graph_path}!")

    except Exception as e:
        error_msg = f"Error during comprehensive graph creation for '{graph_path}': {e}"
        print(error_msg)
        traceback.print_exc()

# --- Function to check and create Joystick Listener ---
# 이 함수는 현재 호출되지 않으므로, 그대로 두거나 삭제해도 무방합니다.
# 만약 사용한다면 내부의 delete 로직도 수정해야 합니다.
def create_joystick_listener(prim_path_of_husky):
    # ... (기존 Joystick Listener 코드) ...
    # 내부의 og.delete_graph 부분도 stage.RemovePrim으로 바꿔야 함
    pass # 임시로 비워둠