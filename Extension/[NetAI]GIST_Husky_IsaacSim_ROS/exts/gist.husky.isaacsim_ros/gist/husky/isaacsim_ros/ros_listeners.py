# Isaac Sim ROS2 Graph Generator for Husky Robot Control
# 
# Current Version: Complete ROS2 graph generation code with integrated IMU, LiDAR, RGB Camera, and Depth Camera
# Implements identical dynamics to physical Husky A200 to ensure simulation-to-real consistency
# 
# Future Plans: Refactoring to support multi-robot coordination (swarm control)
# with independent ROS2 graph generation for multiple robots
#
# Author: Inyong Song

# Complete Integrated ROS2 Graph Generator for Husky A200 Robot in Isaac Sim
# 
# Features:
# - Differential drive control via /cmd_vel (geometry_msgs/Twist) topic
# - IMU sensor data publishing (/imu/virtual)
# - LiDAR point cloud publishing (/pointcloud)  
# - RGB camera image & camera info publishing (/camera/color/*)
# - Depth camera image & camera info publishing (/depth_camera/*)
# - Virtual odometry publishing (/odom/virtual)
# - Dynamic TF transform publishing (all link coordinate frames)
# 
# Physics engine-based implementation with identical dynamics to real Husky A200
# Precise wheel velocity control using DifferentialController  진짜 엔비디아 좀 속성 명좀 통일좀 해라 통일좀

import omni
import omni.graph.core as og
import omni.usd
from omni.usd import get_context # Need get_context for the check
import warnings
from pxr import UsdPhysics
import traceback # 오류 추적 위해 추가
import omni.kit.commands
import carb

# --- Function to check and create Tank Control Listener ---
# --- 메인 함수: Husky 로봇용 완전한 ROS2 그래프 생성 ---
# 센서 검증(USD 존재하는지 경로등) 이후 노드 생성 → 초기 value 설정 → 연결 설정의 3단계 프로세스로 구성
def create_tank_controll_listener(prim_path_of_husky):
    LIDAR_SENSOR_PRIM_PATH = prim_path_of_husky + "/lidar_link/lidar_sensor"
    LIDAR_FRAME_ID = "lidar_link"
    LIDAR_TOPIC_NAME = "/pointcloud"

    # --- RGB Camera Configuration (이미지 기반) ---
    RGB_CAMERA_SENSOR_PRIM_PATH = prim_path_of_husky + "/front_bumper_link/husky_rgb_cam"
    RGB_CAMERA_FRAME_ID = "front_bumper_link"
    RGB_IMAGE_TOPIC_NAME = "/camera/color/image_raw"  # RGB 이미지 토픽 이름
    RGB_INFO_TOPIC_NAME = "/camera/color/camera_info"   # RGB 카메라 정보 토픽 이름
    RGB_CAMERA_RESOLUTION_WIDTH = 640 # 해상도는 실제 해상도에 맞춰서 수정 
    RGB_CAMERA_RESOLUTION_HEIGHT = 480 # 해상도는 실제 해상도에 맞춰서 수정 

    # --- Depth Camera Configuration (이미지 기반으로 수정) ---
    DEPTH_CAMERA_SENSOR_PRIM_PATH = prim_path_of_husky + "/front_bumper_link/husky_depth_cam"
    DEPTH_CAMERA_FRAME_ID = "front_bumper_link"

    DEPTH_RGB_TOPIC_NAME = "/depth_camera/color/image_raw"
    DEPTH_IMAGE_TOPIC_NAME = "/depth_camera/depth/image_rect_raw" # Depth image
    DEPTH_DEPTH_INFO_TOPIC_NAME = "/depth_camera/depth/camera_info" # CameraInfo for Depth
    DEPTH_CAMERA_RESOLUTION_WIDTH = 640 # 해상도는 실제 해상도에 맞춰서 수정 
    DEPTH_CAMERA_RESOLUTION_HEIGHT = 480 # 해상도는 실제 해상도에 맞춰서 수정 

    IMU_SENSOR_PRIM_PATH = prim_path_of_husky + "/lidar_link/imu_sensor"
    IMU_FRAME_ID = "lidar_link" # 실제 IMU의 frame_id와 일치시킴
    IMU_TOPIC_NAME = "/imu/virtual"
    
    ODOM_TOPIC_NAME = "/odom/virtual"
    ODOM_FRAME_ID = "odom" # 가상 Odometry 좌표계
    BASE_FRAME_ID = "base_link" # 로봇의 기준 좌표계
    graph_path = "/husky_ros_graph" # 그래프 경로 일관성 유지

    stage = omni.usd.get_context().get_stage()
    if not stage:
        carb.log_error("Error: Could not get USD stage.")
        return

    print("Validating required prim paths and APIs...")
    valid_paths = {}
    validation_passed = True

    husky_prim = stage.GetPrimAtPath(prim_path_of_husky)
    husky_base_link_path = f"{prim_path_of_husky}/base_link"
    husky_base_link_prim = stage.GetPrimAtPath(husky_base_link_path)
    controller_target_path = None

    if husky_base_link_prim.IsValid() and husky_base_link_prim.HasAPI(UsdPhysics.ArticulationRootAPI):
        controller_target_path = husky_base_link_path
        valid_paths["husky_root"] = prim_path_of_husky # TF에는 상위 경로 사용 가능
        print(f"  [OK] Controller Target Path (ArticulationRootAPI on base_link): {controller_target_path}")
        print(f"  [OK] Husky Root Path for TF: {valid_paths['husky_root']}")
    elif husky_prim.IsValid() and husky_prim.HasAPI(UsdPhysics.ArticulationRootAPI):
        controller_target_path = prim_path_of_husky
        valid_paths["husky_root"] = prim_path_of_husky
        print(f"  [OK] Controller Target Path (ArticulationRootAPI on husky_prim): {controller_target_path}")
        print(f"  [OK] Husky Root Path for TF: {valid_paths['husky_root']}")
    else:
        print(f"Error: Prim at {prim_path_of_husky} or {husky_base_link_path} does not exist or does not have ArticulationRootAPI.")
        validation_passed = False

    if "husky_root" not in valid_paths:
        print(f"Error: Could not determine a valid 'husky_root' path for TF.")
        validation_passed = False

    lidar_link_path = f"{prim_path_of_husky}/lidar_link"
    front_bumper_link_path = f"{prim_path_of_husky}/front_bumper_link" # 예시, 다른 환경에서 사용시 실제 경로 확인 필요
    imu_sensor_path = f"{lidar_link_path}/imu_sensor" # imu_link 하위 또는 base_link 하위일 수 있음, 경로 확인

    paths_to_check_for_dynamic_tf = {
        "lidar_link": lidar_link_path,
        "front_bumper_link": front_bumper_link_path,
        "imu_sensor": imu_sensor_path,
    }
    valid_tf_sensor_paths = []
    if validation_passed: # husky_root가 유효할 때만 센서 경로 구성
        for name, path in paths_to_check_for_dynamic_tf.items():
            prim = stage.GetPrimAtPath(path)
            if prim.IsValid():
                print(f"  [OK] Dynamic TF Target Candidate Path Valid: {path}")
                # valid_paths[name] = path # valid_paths는 이제 사용 안 함
                valid_tf_sensor_paths.append(path)
            else:
                print(f"  [Warning] Prim for Dynamic TF Target {name} not found at {path}. It will be excluded from dynamic TF.")

        # dynamic_tf_targets는 husky_root와 유효한 센서 경로들로 구성
        dynamic_tf_targets = [valid_paths["husky_root"]] + valid_tf_sensor_paths
        if len(dynamic_tf_targets) <= 1 and valid_tf_sensor_paths: # husky_root 외 유효 센서가 있었어야 함
             print("[Warning] Dynamic TF target list only contains husky_root. No additional sensor links found or validated for dynamic TF.")
        elif not valid_tf_sensor_paths :
             print("[Info] No additional sensor links found or validated for dynamic TF, only husky_root will be published.")
        print(f"  [Info] Dynamic TF Targets: {dynamic_tf_targets}")


    lidar_sensor_valid = False
    if stage.GetPrimAtPath(LIDAR_SENSOR_PRIM_PATH).IsValid():
        print(f"  [OK] LiDAR Sensor Prim Path Valid: {LIDAR_SENSOR_PRIM_PATH}")
        lidar_sensor_valid = True
    else:
        carb.log_error(f"Error: LiDAR Sensor Prim not found or invalid at expected path: {LIDAR_SENSOR_PRIM_PATH}. LiDAR publishing will be disabled.")
        lidar_sensor_valid = False
    # --- RGB Camera Sensor Validation ---
    rgb_camera_sensor_valid = False # 먼저 False로 초기화
    if RGB_CAMERA_SENSOR_PRIM_PATH: # 경로가 정의되었는지 확인
        rgb_camera_prim_check = stage.GetPrimAtPath(RGB_CAMERA_SENSOR_PRIM_PATH)
        if rgb_camera_prim_check.IsValid() and rgb_camera_prim_check.GetTypeName() == 'Camera':
            print(f"  [OK] RGB Camera Sensor Prim Path Valid: {RGB_CAMERA_SENSOR_PRIM_PATH}")
            rgb_camera_sensor_valid = True
        else:
            carb.log_error(f"Warning: RGB Camera Sensor Prim not found, invalid, or not type 'Camera' at {RGB_CAMERA_SENSOR_PRIM_PATH}. RGB publishing will be disabled.")
    else:
        carb.log_error("Warning: RGB_CAMERA_SENSOR_PRIM_PATH is not defined. RGB publishing will be disabled.")

    # IMU Sensor Validation ---
    imu_sensor_valid = False
    if stage.GetPrimAtPath(IMU_SENSOR_PRIM_PATH).IsValid():
        print(f"  [OK] IMU Sensor Prim Path Valid: {IMU_SENSOR_PRIM_PATH}")
        imu_sensor_valid = True
    else:
        carb.log_error(f"Error: IMU Sensor Prim not found at {IMU_SENSOR_PRIM_PATH}. IMU publishing will be disabled.")

    # --- Depth Camera Sensor Validation ---
    depth_camera_sensor_valid = False # 먼저 False로 초기화
    if DEPTH_CAMERA_SENSOR_PRIM_PATH: # 경로가 정의되었는지 확인 (선택적이지만 안전)
        depth_camera_prim_check = stage.GetPrimAtPath(DEPTH_CAMERA_SENSOR_PRIM_PATH)
        if depth_camera_prim_check.IsValid() and depth_camera_prim_check.GetTypeName() == 'Camera':
            print(f"  [OK] Depth Camera Sensor Prim Path Valid: {DEPTH_CAMERA_SENSOR_PRIM_PATH}")
            depth_camera_sensor_valid = True
        else:
            carb.log_error(f"Warning: Depth Camera Sensor Prim not found, invalid, or not type 'Camera' at {DEPTH_CAMERA_SENSOR_PRIM_PATH}. Depth publishing will be disabled.")
    else:
        carb.log_error("Warning: DEPTH_CAMERA_SENSOR_PRIM_PATH is not defined. Depth publishing will be disabled.")

    print(f"--- DEBUG: Preparing to create graph. LiDAR: {lidar_sensor_valid}, RGB Cam: {rgb_camera_sensor_valid}, Depth Cam: {depth_camera_sensor_valid} ---")



    if not validation_passed:
        carb.log_error("Critical validation failed (Controller Target/Husky Root path). Cannot create OmniGraph.")
        return
    print("Path validation finished.")

    if stage.GetPrimAtPath(graph_path).IsValid():
        print(f"Deleting existing graph at {graph_path} for fresh start.")
        omni.kit.commands.execute("DeletePrims", paths=[graph_path])

    print(f"--- DEBUG: Preparing to create graph. Including LiDAR nodes: {lidar_sensor_valid} ---")
    keys = og.Controller.Keys
    try:
        # --- 노드 정의 (조향 로직 변경 및 LiDAR 조건부 추가) ---
        nodes_to_create = [
            ("phys_step", "isaacsim.core.nodes.OnPhysicsStep"),
            # ("ack_sub", "isaacsim.ros2.bridge.ROS2SubscribeAckermannDrive"), # 기존 Ackermann 구독 노드 삭제
            ("twist_sub", "isaacsim.ros2.bridge.ROS2SubscribeTwist"),       # Twist 구독 노드로 변경
            ("diff_ctrl", "isaacsim.robot.wheeled_robots.DifferentialController"), # 차동 컨트롤러 추가

            ("break_linear_velocity", "omni.graph.nodes.BreakVector3"),
            ("break_angular_velocity", "omni.graph.nodes.BreakVector3"),

            ("rotation_multiplier", "omni.graph.nodes.Multiply"),
            ("rotation_correction_factor", "omni.graph.nodes.ConstantDouble"),

            #("get_linear_x", "omni.graph.nodes.ArrayIndex"),      # Twist 메시지에서 linear.x 추출
            #("get_angular_z", "omni.graph.nodes.ArrayIndex"),     # Twist 메시지에서 angular.z 추출


            ("get_v_left", "omni.graph.nodes.ArrayIndex"),        # DifferentialController 출력에서 왼쪽 바퀴 속도 추출
            ("get_v_right", "omni.graph.nodes.ArrayIndex"),       # DifferentialController 출력에서 오른쪽 바퀴 속도 추출
            ("initial_command_array", "omni.graph.nodes.ConstructArray"), # 최종 바퀴 속도 배열 생성
            ("insert_val_at_idx0", "omni.graph.nodes.ArrayInsertValue"),
            ("insert_val_at_idx1", "omni.graph.nodes.ArrayInsertValue"),
            ("insert_val_at_idx2", "omni.graph.nodes.ArrayInsertValue"),
            ("insert_val_at_idx3", "omni.graph.nodes.ArrayInsertValue"),

            *([
            ("imu_sensor_reader", "isaacsim.sensors.physics.IsaacReadIMU"),  # imu updated 
            ("imu_pub", "isaacsim.ros2.bridge.ROS2PublishImu")
            ] if imu_sensor_valid else []),
            ("compute_odom", "isaacsim.core.nodes.IsaacComputeOdometry"),
            ("odom_pub", "isaacsim.ros2.bridge.ROS2PublishOdometry"),

            ("controller", "isaacsim.core.nodes.IsaacArticulationController"),
            ("sim_time", "isaacsim.core.nodes.IsaacReadSimulationTime"),
            ("tf_static_pub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
            ("tf_dynamic_pub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
            *([("rp_creator", "isaacsim.core.nodes.IsaacCreateRenderProduct")] if lidar_sensor_valid else []),
            *([("lidar_pub", "isaacsim.ros2.bridge.ROS2RtxLidarHelper")] if lidar_sensor_valid else []),
            # RGB Camera Helper Node (Conditional)
            *([ ("rp_creator_rgb", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("rgb_camera_helper", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("rgb_camera_info_helper", "isaacsim.ros2.bridge.ROS2CameraInfoHelper")
                ] if rgb_camera_sensor_valid else []),
                

            # Depth Camera Helper Node (Conditional)
            *([ ("rp_creator_depth", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("depth_camera_helper", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("depth_camera_info_helper", "isaacsim.ros2.bridge.ROS2CameraInfoHelper")
                ] if depth_camera_sensor_valid else []),            
        ]
        print(f"--- DEBUG: nodes_to_create defined: {nodes_to_create}")

        # --- 값 설정 (조향 로직 변경 및 LiDAR 조건부 추가) ---
        # Husky A200 매뉴얼 기준 값 
        #HUSKY_WHEEL_RADIUS = 0.165  # 바퀴 반지름 (m) - 330mm 타이어
        #HUSKY_WHEEL_BASE = 0.555    # 바퀴 간 거리 (m) - 트랙 폭 (허브-허브)
        HUSKY_WHEEL_RADIUS =0.165  # 바퀴 반지름 (m) - 330mm 타이어
        HUSKY_WHEEL_BASE = 0.67   # 바퀴 간 거리 (m) - 트랙 폭 (허브-허브)        
        HUSKY_MAX_ANGULAR_SPEED = 6.06 # 예시: 1.5 rad/s (후에 필요에 따라 조절하삼)

        ROTATION_SCALING_FACTOR = 1.5

        # Articulation Controller에 사용될 조인트 이름 순서 (USD 모델과 일치해야 함)
        # 순서: [후방 우측, 후방 좌측, 전방 우측, 전방 좌측]
        # DifferentialController 출력: [v_left, v_right]
        # 따라서 initial_command_array 입력은 [v_right, v_left, v_right, v_left] 순서로 매핑 지금 버그로 복잡해보이는 Chain 형태로 사용해야함
        husky_joint_names = [
            "back_right_wheel_joint", "back_left_wheel_joint",
            "front_right_wheel_joint", "front_left_wheel_joint"
        ]

        values_to_set = [
            ("twist_sub.inputs:topicName", "/cmd_vel"), # 구독 토픽 변경
            ("diff_ctrl.inputs:wheelRadius", HUSKY_WHEEL_RADIUS),
            ("diff_ctrl.inputs:wheelDistance", HUSKY_WHEEL_BASE), # 아이작심에서는 속성 이름 wheelDistance 임
            ("diff_ctrl.inputs:maxAngularSpeed", HUSKY_MAX_ANGULAR_SPEED),
            #("get_linear_x.inputs:index", 0),
            #("get_angular_z.inputs:index", 2),
            ("rotation_correction_factor.inputs:value", ROTATION_SCALING_FACTOR),

            ("get_v_left.inputs:index", 0),  # DifferentialController 출력의 첫 번째 요소 (왼쪽 바퀴)
            ("get_v_right.inputs:index", 1), # DifferentialController 출력의 두 번째 요소 (오른쪽 바퀴)

            ("initial_command_array.inputs:arraySize", 0), # 4개 바퀴 속도
            ("initial_command_array.inputs:arrayType", "double[]"),

            ("insert_val_at_idx0.inputs:index", 0),
            ("insert_val_at_idx1.inputs:index", 1),
            ("insert_val_at_idx2.inputs:index", 2),
            ("insert_val_at_idx3.inputs:index", 3),

            *([
                ("imu_sensor_reader.inputs:imuPrim", IMU_SENSOR_PRIM_PATH),
                ("imu_pub.inputs:topicName", IMU_TOPIC_NAME),
                ("imu_pub.inputs:frameId", IMU_FRAME_ID),
                ] if imu_sensor_valid else []),

            ("compute_odom.inputs:chassisPrim", controller_target_path),
            ("odom_pub.inputs:topicName", ODOM_TOPIC_NAME),
            ("odom_pub.inputs:odomFrameId", ODOM_FRAME_ID),
            ("odom_pub.inputs:chassisFrameId", BASE_FRAME_ID),

            ("controller.inputs:robotPath", controller_target_path),
            ("controller.inputs:jointNames", husky_joint_names),

            ("tf_static_pub.inputs:targetPrims", [valid_paths.get("husky_root")]),
            ("tf_static_pub.inputs:topicName", "/tf_static"),
            ("tf_static_pub.inputs:staticPublisher", True),
            ("tf_dynamic_pub.inputs:targetPrims", dynamic_tf_targets),
            ("tf_dynamic_pub.inputs:topicName", "/tf"),
            ("tf_dynamic_pub.inputs:staticPublisher", False),
            # LiDAR Values
            *([
                ("rp_creator.inputs:cameraPrim", LIDAR_SENSOR_PRIM_PATH),
                ("rp_creator.inputs:width", 1), # RTX Lidar는 Render Product 해상도 1x1로 충분
                ("rp_creator.inputs:height", 1),
                ("lidar_pub.inputs:topicName", LIDAR_TOPIC_NAME),
                ("lidar_pub.inputs:frameId", LIDAR_FRAME_ID),
                ("lidar_pub.inputs:type", "point_cloud"),
             ] if lidar_sensor_valid else []),
            # RGB Camera Values
            *([
                ("rp_creator_rgb.inputs:cameraPrim", RGB_CAMERA_SENSOR_PRIM_PATH),
                ("rp_creator_rgb.inputs:width", RGB_CAMERA_RESOLUTION_WIDTH),
                ("rp_creator_rgb.inputs:height", RGB_CAMERA_RESOLUTION_HEIGHT),
                ("rgb_camera_helper.inputs:frameId", RGB_CAMERA_FRAME_ID),
                ("rgb_camera_helper.inputs:topicName", RGB_IMAGE_TOPIC_NAME),
                ("rgb_camera_helper.inputs:type", "rgb"),
                # Added RGB Camera Info
                ("rgb_camera_info_helper.inputs:frameId", RGB_CAMERA_FRAME_ID),
                ("rgb_camera_info_helper.inputs:topicName", RGB_INFO_TOPIC_NAME),
             ] if rgb_camera_sensor_valid else []),

            # Depth Camera Values (Conditional & NEW)
            *([
                ("rp_creator_depth.inputs:cameraPrim", DEPTH_CAMERA_SENSOR_PRIM_PATH),
                ("rp_creator_depth.inputs:width", DEPTH_CAMERA_RESOLUTION_WIDTH),
                ("rp_creator_depth.inputs:height", DEPTH_CAMERA_RESOLUTION_HEIGHT),
                ("depth_camera_helper.inputs:frameId", DEPTH_CAMERA_FRAME_ID),
                ("depth_camera_helper.inputs:topicName", DEPTH_IMAGE_TOPIC_NAME),
                ("depth_camera_helper.inputs:type", "depth"),

                # Added Depth Camera Info
                ("depth_camera_info_helper.inputs:frameId", DEPTH_CAMERA_FRAME_ID),
                ("depth_camera_info_helper.inputs:topicName", DEPTH_DEPTH_INFO_TOPIC_NAME),
             ] if depth_camera_sensor_valid else [])             
        ]
        print(f"--- DEBUG: values_to_set defined: {values_to_set}")

        # --- 연결 설정 (조향 로직 변경 및 LiDAR 조건부 추가) ---
        connections = [
            ("phys_step.outputs:step", "twist_sub.inputs:execIn"),
            ("phys_step.outputs:deltaSimulationTime", "diff_ctrl.inputs:dt"), # OnPhysicsStep의 deltaSimulationTime 사용


            ("twist_sub.outputs:linearVelocity", "break_linear_velocity.inputs:tuple"),
            ("twist_sub.outputs:angularVelocity", "break_angular_velocity.inputs:tuple"),
            ("break_linear_velocity.outputs:x", "diff_ctrl.inputs:linearVelocity"),
           # ("break_angular_velocity.outputs:z", "diff_ctrl.inputs:angularVelocity"),

            ("break_angular_velocity.outputs:z", "rotation_multiplier.inputs:a"),
            # ConstantDouble 노드의 출력을 Multiply 노드의 입력 b로 연결합니다.
            ("rotation_correction_factor.inputs:value", "rotation_multiplier.inputs:b"),
            # Multiply 결과를 컨트롤러 입력으로 연결합니다.
            ("rotation_multiplier.outputs:product", "diff_ctrl.inputs:angularVelocity"),

            ("phys_step.outputs:step", "diff_ctrl.inputs:execIn"), # DifferentialController도 실행 신호 필요할 수 있음

            ("diff_ctrl.outputs:velocityCommand", "get_v_left.inputs:array"),
            ("diff_ctrl.outputs:velocityCommand", "get_v_right.inputs:array"),

            # === 배열 구성 로직: 모든 요소를 ArrayInsertValue로만 추가 ===
            # 1. 첫 번째 요소 (v_right)를 인덱스 0에 삽입
            ("initial_command_array.outputs:array", "insert_val_at_idx0.inputs:array"), # 빈 배열을 첫 번째 insert 노드로
            ("get_v_right.outputs:value", "insert_val_at_idx0.inputs:value"),

            # 2. 두 번째 요소 (v_left)를 인덱스 1에 삽입
            ("insert_val_at_idx0.outputs:array", "insert_val_at_idx1.inputs:array"),
            ("get_v_left.outputs:value", "insert_val_at_idx1.inputs:value"),

            # 3. 세 번째 요소 (v_right)를 인덱스 2에 삽입
            ("insert_val_at_idx1.outputs:array", "insert_val_at_idx2.inputs:array"),
            ("get_v_right.outputs:value", "insert_val_at_idx2.inputs:value"),

            # 4. 네 번째 요소 (v_left)를 인덱스 3에 삽입
            ("insert_val_at_idx2.outputs:array", "insert_val_at_idx3.inputs:array"),
            ("get_v_left.outputs:value", "insert_val_at_idx3.inputs:value"),

            # --- IMU 및 Odometry 연결 ---
            *([
                ("phys_step.outputs:step", "imu_sensor_reader.inputs:execIn"),
                ("imu_sensor_reader.outputs:execOut", "imu_pub.inputs:execIn"),
                
                ("imu_sensor_reader.outputs:angVel", "imu_pub.inputs:angularVelocity"),
                ("imu_sensor_reader.outputs:linAcc", "imu_pub.inputs:linearAcceleration"),
                ("imu_sensor_reader.outputs:orientation", "imu_pub.inputs:orientation"),

                ("imu_sensor_reader.outputs:sensorTime", "imu_pub.inputs:timeStamp"),
                ] if imu_sensor_valid else []),
      
            ("phys_step.outputs:step", "compute_odom.inputs:execIn"),
            
            ("compute_odom.outputs:execOut", "odom_pub.inputs:execIn"),
            ("sim_time.outputs:simulationTime", "odom_pub.inputs:timeStamp"),
            ("compute_odom.outputs:position", "odom_pub.inputs:position"),
            ("compute_odom.outputs:orientation", "odom_pub.inputs:orientation"),
            ("compute_odom.outputs:linearVelocity", "odom_pub.inputs:linearVelocity"),
            ("compute_odom.outputs:angularVelocity", "odom_pub.inputs:angularVelocity"),
             # --- IMU 및 Odometry 연결 끄읏 ---

            # === 최종 배열을 controller에 연결 ===
            ("insert_val_at_idx3.outputs:array", "controller.inputs:velocityCommand"),
            ("phys_step.outputs:step", "controller.inputs:execIn"),

            ("phys_step.outputs:step", "tf_static_pub.inputs:execIn"),
            ("phys_step.outputs:step", "tf_dynamic_pub.inputs:execIn"),
            ("sim_time.outputs:simulationTime", "tf_dynamic_pub.inputs:timeStamp"),
            *([
                ("phys_step.outputs:step", "rp_creator.inputs:execIn"),
                ("rp_creator.outputs:renderProductPath", "lidar_pub.inputs:renderProductPath"),
                ("rp_creator.outputs:execOut", "lidar_pub.inputs:execIn"),
             ] if lidar_sensor_valid else []),

            # RGB Camera Connections
            *([
                ("phys_step.outputs:step", "rp_creator_rgb.inputs:execIn"),
                ("rp_creator_rgb.outputs:renderProductPath", "rgb_camera_helper.inputs:renderProductPath"),
                ("rp_creator_rgb.outputs:execOut", "rgb_camera_helper.inputs:execIn"),

                # RGB Camera Info Connections
                ("phys_step.outputs:step", "rgb_camera_info_helper.inputs:execIn"),
                # 동일 RenderProductPath 재사용
                ("rp_creator_rgb.outputs:renderProductPath", "rgb_camera_info_helper.inputs:renderProductPath"),

             ] if rgb_camera_sensor_valid else []),

            # Depth Camera Connections

            *([
                ("phys_step.outputs:step", "rp_creator_depth.inputs:execIn"),
                ("rp_creator_depth.outputs:renderProductPath", "depth_camera_helper.inputs:renderProductPath"),
                ("rp_creator_depth.outputs:execOut", "depth_camera_helper.inputs:execIn"),

                ("phys_step.outputs:step", "depth_camera_info_helper.inputs:execIn"),
                ("rp_creator_depth.outputs:renderProductPath", "depth_camera_info_helper.inputs:renderProductPath"),
             ] if depth_camera_sensor_valid else [])            
        ]
        print(f"--- DEBUG: connections defined (length: {len(connections)}): {connections}")

        og.Controller.edit(
            {
              "graph_path": graph_path,
              "evaluator_name": "execution",
              "pipeline_stage": og.GraphPipelineStage.GRAPH_PIPELINE_STAGE_ONDEMAND,
            },
            {
              keys.CREATE_NODES: nodes_to_create,
              keys.SET_VALUES: values_to_set,
              keys.CONNECT: connections,
            }
        )
        print(f"Successfully created/updated graph at {graph_path} with Twist control!")

    except Exception as e:
        error_msg = f"Error during graph creation/modification for '{graph_path}': {e}"
        print(error_msg)
        traceback.print_exc()

# --- Function to check and create Joystick Listener (Placeholder) ---
def create_joystick_listener(prim_path_of_husky):
    print("Joystick listener function is a placeholder and not implemented in this version.")
    pass

# --- Example Usage (Illustrative) ---
# if __name__ == "__main__":
#     # This part is typically run from an Isaac Sim extension or script editor
#     # Ensure a Husky robot prim exists at the specified path in your USD stage
#     HUSKY_PRIM_PATH = "/World/Husky" # Adjust this to your actual Husky prim path
#
#     # It's usually better to call this from an extension's on_startup or a UI button
#     # For direct script execution, ensure the simulation is ready.
#     # omni.timeline.get_timeline_interface().play() # Or wait for physics step
#
#     # Check if the prim exists before attempting to create the graph
#     stage = omni.usd.get_context().get_stage()
#     if stage and stage.GetPrimAtPath(HUSKY_PRIM_PATH).IsValid():
#         create_tank_controll_listener(HUSKY_PRIM_PATH)
#     else:
#         carb.log_error(f"Husky prim not found at '{HUSKY_PRIM_PATH}'. Cannot create control graph.")
#
#     # To ensure the script runs after the stage is loaded, you might use:
#     # def on_stage_event(e):
#     #     if e.type == omni.usd.StageEventType.OPENED:
#     #         # Now it's safer to access the stage and prims
#     #         if stage.GetPrimAtPath(HUSKY_PRIM_PATH).IsValid():
#     #            create_tank_controll_listener(HUSKY_PRIM_PATH)
#     # stage_event_sub = omni.usd.get_context().get_stage_event_stream().create_subscription_to_pop(on_stage_event)