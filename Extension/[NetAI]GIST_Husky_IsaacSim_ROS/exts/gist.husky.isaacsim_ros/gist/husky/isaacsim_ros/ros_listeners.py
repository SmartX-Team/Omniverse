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
def create_tank_controll_listener(prim_path_of_husky):
    LIDAR_SENSOR_PRIM_PATH = prim_path_of_husky + "/lidar_link/lidar_sensor" # <<< 이 경로가 정확한지 최종 확인!
    LIDAR_FRAME_ID = "lidar_link" # <<< 사용할 TF Frame ID, 이것도 최종 확인!
    LIDAR_TOPIC_NAME = "/pointcloud" # <<< 발행할 토픽 이름

    graph_path = "/husky_ros_graph"

    stage = omni.usd.get_context().get_stage()
    if not stage:
        carb.log_error("Error: Could not get USD stage.")
        return

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


    # --- LiDAR 센서 프리미티브 경로 확인 및 lidar_sensor_valid 변수 정의 ---
    lidar_sensor_valid = False # <<< 변수 정의 및 초기화
    if stage.GetPrimAtPath(LIDAR_SENSOR_PRIM_PATH).IsValid():
        print(f"  [OK] LiDAR Sensor Prim Path Valid: {LIDAR_SENSOR_PRIM_PATH}")
        lidar_sensor_valid = True # <<< 확인 후 True 로 설정
    else:
        carb.log_error(f"Error: LiDAR Sensor Prim not found or invalid at expected path: {LIDAR_SENSOR_PRIM_PATH}. LiDAR publishing will be disabled.")
        lidar_sensor_valid = False # <<< 확인 후 False 로 설정 (LiDAR 노드 추가 안 함)


    if not validation_passed:
        carb.log_error("Critical validation failed (Controller/husky_root path). Cannot create OmniGraph.")
        return
    print("Path validation finished.")


    # --- 그래프 삭제 로직 ---
    if stage.GetPrimAtPath(graph_path).IsValid():
        print(f"Deleting existing graph at {graph_path} for fresh start.")
        omni.kit.commands.execute("DeletePrims", paths=[graph_path])


    # --- 단일 og.Controller.edit 호출 ---
    print(f"--- DEBUG: Preparing to create graph. Including LiDAR nodes: {lidar_sensor_valid} ---")
    keys = og.Controller.Keys
    try:
        # --- 노드 정의 (LiDAR 관련 노드 조건부 추가) ---
        nodes_to_create = [
            # 기존 노드들
            ("phys_step", "isaacsim.core.nodes.OnPhysicsStep"),
            ("ack_sub", "isaacsim.ros2.bridge.ROS2SubscribeAckermannDrive"),
            ("array", "omni.graph.nodes.ConstructArray"),
            ("array_add1", "omni.graph.nodes.ArrayInsertValue"),
            ("array_add2", "omni.graph.nodes.ArrayInsertValue"),
            ("array_add3", "omni.graph.nodes.ArrayInsertValue"),
            ("controller", "isaacsim.core.nodes.IsaacArticulationController"),
            ("sim_time", "isaacsim.core.nodes.IsaacReadSimulationTime"), # 익스텐션 활성화 필수
            ("tf_static_pub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
            ("tf_dynamic_pub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
            # LiDAR 관련 노드 추가 (lidar_sensor_valid 값 사용)
            *([("rp_creator", "isaacsim.core.nodes.IsaacCreateRenderProduct")] if lidar_sensor_valid else []),
            *([("lidar_pub", "isaacsim.ros2.bridge.ROS2RtxLidarHelper")] if lidar_sensor_valid else []),
        ]
        print(f"--- DEBUG: nodes_to_create defined: {nodes_to_create}")

        # --- 값 설정 (LiDAR 관련 노드 값 조건부 추가) ---
        values_to_set = [
            # 기존 값 설정
            ("array.inputs:arraySize", 1),
            ("controller.inputs:robotPath", controller_target_path),
            ("controller.inputs:jointNames", ["back_right_wheel_joint", "back_left_wheel_joint", "front_right_wheel_joint", "front_left_wheel_joint"]),
            ("ack_sub.inputs:topicName", "/ackermann_cmd"),
            ("tf_static_pub.inputs:targetPrims", [valid_paths.get("husky_root")]), # husky_root 유효성 검사 필요
            ("tf_static_pub.inputs:topicName", "/tf_static"),
            ("tf_static_pub.inputs:staticPublisher", True),
            ("tf_dynamic_pub.inputs:targetPrims", dynamic_tf_targets), # dynamic_tf_targets 리스트 사용
            ("tf_dynamic_pub.inputs:topicName", "/tf"),
            ("tf_dynamic_pub.inputs:staticPublisher", False),
            # LiDAR 관련 노드 값 설정 추가 (lidar_sensor_valid 값 사용)
            *([
                ("rp_creator.inputs:cameraPrim", LIDAR_SENSOR_PRIM_PATH), # LiDAR 센서 경로 직접 지정
                ("rp_creator.inputs:width", 1),
                ("rp_creator.inputs:height", 1),
                ("lidar_pub.inputs:topicName", LIDAR_TOPIC_NAME), # 상수 사용
                ("lidar_pub.inputs:frameId", LIDAR_FRAME_ID),     # 상수 사용
                ("lidar_pub.inputs:type", "point_cloud"),       # 발행 타입 지정
             ] if lidar_sensor_valid else [])
        ]
        print(f"--- DEBUG: values_to_set defined: {values_to_set}")

        # --- 연결 설정 (LiDAR 관련 연결 조건부 추가) ---
        connections = [
            # 기존 연결
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
            ("phys_step.outputs:step", "tf_dynamic_pub.inputs:execIn"),
            ("sim_time.outputs:simulationTime", "tf_dynamic_pub.inputs:timeStamp"),
            # LiDAR 관련 연결 추가 (lidar_sensor_valid 값 사용)
            *([
                ("phys_step.outputs:step", "rp_creator.inputs:execIn"),
                ("rp_creator.outputs:renderProductPath", "lidar_pub.inputs:renderProductPath"), # RP 경로 전달
                ("rp_creator.outputs:execOut", "lidar_pub.inputs:execIn"), # 순차 실행
             ] if lidar_sensor_valid else [])
        ]
        print(f"--- DEBUG: connections defined: {connections}")

        # --- og.Controller.edit 호출 ---
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
        print(f"Successfully created/updated graph at {graph_path}!")

    except Exception as e:
        error_msg = f"Error during graph creation/modification for '{graph_path}': {e}"
        print(error_msg)
        traceback.print_exc()


# --- Function to check and create Joystick Listener ---
# 이 함수는 현재 호출되지 않으므로, 그대로 두거나 삭제해도 무방합니다.
# 만약 사용한다면 내부의 delete 로직도 수정해야 합니다.
def create_joystick_listener(prim_path_of_husky):
    # ... (기존 Joystick Listener 코드) ...
    # 내부의 og.delete_graph 부분도 stage.RemovePrim으로 바꿔야 함
    pass # 임시로 비워둠