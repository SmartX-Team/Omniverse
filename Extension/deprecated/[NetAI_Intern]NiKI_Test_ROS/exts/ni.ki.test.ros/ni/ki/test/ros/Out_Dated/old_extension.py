# Unsuported Older Version of the code!!!
# Used for reference purposes only!

#
#   ___   _      _  __     __                  _
#  / _ \ | |  __| | \ \   / /  ___  _ __  ___ (_)  ___   _ __
# | | | || | / _` |  \ \ / /  / _ \| '__|/ __|| | / _ \ | '_ \
# | |_| || || (_| |   \ V /  |  __/| |   \__ \| || (_) || | | |
#  \___/ |_| \__,_|    \_/    \___||_|   |___/|_| \___/ |_| |_|
# 

# =======================================================================================
#  |  _   _  ___         _  __ ___   _____  _____  ____   _____   ____    ___   ____   |
#  | | \ | ||_ _|       | |/ /|_ _| |_   _|| ____|/ ___| |_   _| |  _ \  / _ \ / ___|  |
#  | |  \| | | |  _____ | ' /  | |    | |  |  _|  \___ \   | |   | |_) || | | |\___ \  |
#  | | |\  | | | |_____|| . \  | |    | |  | |___  ___) |  | |   |  _ < | |_| | ___) | |
#  | |_| \_||___|       |_|\_\|___|   |_|  |_____||____/   |_|   |_| \_\ \___/ |____/  |
#  |                                                                                   |
#  |  Written by Niki C. Zils for the Gwangju Institute of Science and Technology (1)  |
#  | - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - |
#  | This extension is exclusivly written for Clearpath's UGV Husky (2) with the       |
#  | intention of it being used in combination with Nvidia's Isaac Sim (3) and ROS2    |
#  | Humble (4).                                                                       |
# ========================================================================================

# Links:
# (1) https://ewww.gist.ac.kr/en/main.html
# (2) https://clearpathrobotics.com/husky-unmanned-ground-vehicle-robot/
# (3) https://docs.omniverse.nvidia.com/isaacsim/latest/overview.html
# (4) https://docs.ros.org/en/humble/index.html

# Imports
# Basic Import
import numpy as np

# Used for working with the USD File Format
from pxr import Gf, Usd, Sdf, UsdGeom

# Basic Imports from Omniverse (Most of them are installed with Omniverse KIT)
import omni.ext
import omni.kit.commands
import omni.ui as ui
from omni.usd import get_context
import omni.graph.core as og
import omni.syntheticdata._syntheticdata as sd  # Creates synthetic Data for the Sensors

# Used for working with the sensors and creating renders
import omni.replicator.core as rep

# Actuall Sensor import
from omni.isaac.sensor import _sensor, Camera

# Additional Helper functions from Isaac Sim (for convenience purposes only)
import omni.isaac.core.utils.numpy.rotations as rot_utils
from omni.isaac.core.utils.prims import is_prim_path_valid
from omni.isaac.core_nodes.scripts.utils import set_target_prims

# Please change the specification of Husky to be as precise as possible.
# TODO: Use the robot.yaml file from clearpath to automaticly do it.

# The prim path of Husky in Isaac Sim
# The prim_path is viewable by selecting the entire robot and looking into the inspector.
# TODO: Make it selectable in the Sim, which prim you want to choose.
prim_path_of_husky = "/World/husky_3d_model"  

# Please refer to the actual robot to double check if the correct lidar is being selected.
# The following link refers to the possible configurations:
# https://docs.omniverse.nvidia.com/isaacsim/latest/features/sensors_simulation/isaac_sim_sensors_rtx_based_lidar.html#lidar-config-files
lidar_config = "OS1_32ch10hz2048res"

# The following variables should not be changed!
# using_isaac_sim: enables certain features of the program if running in Isaac Sim -> Most of the functionality
# Never expects to run in Isaac, since errors could get caused by running in the wrong directory.
using_isaac_sim = False


# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.
class NiKiTestRosExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def on_startup(self, ext_id):
        print("[ni.ki.test.ros] ni ki test ros startup")

        self._window = ui.Window("Test ROS (Ni-KI)", width=500, height=180)
        with self._window.frame:
            with ui.VStack():
                label = ui.Label("")
                label.text = "Extension not initalised."

                def on_initalize():
                    global height_adjusted
                    label.text = f"Start of initalisation\n"

                    # Gets the required prim of the husky
                    stage = get_context().get_stage()
                    prim = stage.GetPrimAtPath(prim_path_of_husky)

                    # Error Handelling - No Prim
                    if not prim.IsValid():
                        label.text += f"Prim: NOT VALID - Searched for: {prim_path_of_husky}"
                        return None
                    
                    label.text += "Prim: Valid"

                    # Get initial Data - not used as of right now
                    self.matrix = omni.usd.get_world_transform_matrix(prim)
                    self.translate = self.matrix.ExtractTranslation()
                    self.rotation = self.matrix.ExtractRotation()

                    label.text += " | Matrix: Valid"

                    height = update_scaling_orientation(prim, self.translate)

                    label.text += "| Position: Valid "

                    # Husky Cam
                    husky_cam_path = prim_path_of_husky + "/husky_cam"
                    self.husky_cam_prim = stage.GetPrimAtPath(husky_cam_path)
                    if not self.husky_cam_prim.IsValid():
                        self.husky_cam = create_perspective_camera(stage=stage, prim_path=husky_cam_path)
                        self.husky_cam_prim = stage.GetPrimAtPath(husky_cam_path)

                        # Does a second position update if the camerqa didn't exist
                        prim.GetAttribute("xformOp:translate").Set(Gf.Vec3f(self.translate[0], 
                                                                            self.translate[1],
                                                                            self.translate[2] + height))

                    self.husky_cam_prim.GetAttribute("xformOp:translate").Set(Gf.Vec3f(0.0, 0.0, -50.0))
                    

                    label.text += " | Husky Cam: Valid"

                    # LiDAR
                    lidar_sensor_path = prim_path_of_husky + "/lidar_sensor"
                    self.lidar_sensor = stage.GetPrimAtPath(lidar_sensor_path)
                    lidar_created = True
                    if not self.lidar_sensor.IsValid():
                        lidar_created = create_lidar_sensor()
                        self.lidar_sensor = stage.GetPrimAtPath(lidar_sensor_path)
                    
                    if not lidar_created:
                        label.text += " | LiDAR: Failed"
                    else:
                        label.text += " | LiDAR: Valid"
                        
                        # Creates the IMU only if the LiDAR worked.
                        if using_isaac_sim:
                            create_imu_sensor(stage, prim_path_of_husky + "/imu_sensor")
                            

                            # Get the data of the IMU
                            _imu_sensor_interface = _sensor.acquire_imu_sensor_interface()
                            data = _imu_sensor_interface.get_sensor_reading(prim_path_of_husky + "/imu_sensor", use_latest_data = True, read_gravity = True)
                            print("Data is valid: ", data.is_valid)

                            label.text += " | IMU: Valid"

                    label.text += "\n\nInit finished."
                
                def on_drive():
                    label.text = "LET'S GO HUSKY!"
                    label.text += "\n..."
                    label.text += "\n(Does nothing... yet! yet?"
                    

                on_initalize()

                with ui.HStack():
                    ui.Button("Init.", clicked_fn=on_initalize)
                    ui.Button("Drive", clicked_fn=on_drive)

    def on_shutdown(self):
        print("[ni.ki.test.ros] ni ki test ros shutdown")

# Creates the required sensors
def create_perspective_camera(stage: Usd.Stage, prim_path: str="/World/husky_3d_model/husky_cam") -> UsdGeom.Camera:
    camera = Camera(
        prim_path= prim_path_of_husky + "/husky_cam",
        position=np.array([-3.11, -1.87, 1.0]),
        frequency=20,
        resolution=(256, 256),
        orientation=rot_utils.euler_angles_to_quats(np.array([0, 0, 0]), degrees=True),
    )
    camera.initialize()
    approx_freq = 30

    
    # publish_camera_info(camera, approx_freq)
    publish_rgb(camera, approx_freq)
    publish_depth(camera, approx_freq)
    publish_camera_tf(camera)
    publish_pointcloud_from_depth(camera, approx_freq)

    return camera

def create_imu_sensor(stage, path):
    # The IMU is build into the LiDAR - refer to its datasheet
    imu_sensor = stage.GetPrimAtPath(path)
    if not imu_sensor.IsValid():
        success, _isaac_sensor_prim = omni.kit.commands.execute(
            "IsaacSensorCreateImuSensor",
            path="imu_sensor",
            parent=prim_path_of_husky,
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
            _imu_sensor_interface.get_sensor_reading(prim_path_of_husky + "/imu_sensor", use_latest_data = True, read_gravity = True)

def create_lidar_sensor():
    # LiDAR Specs - https://data.ouster.io/downloads/datasheets/datasheet-revd-v2p0-os1.pdf
    # 1. Create The Camera
    success, sensor = omni.kit.commands.execute(
        "IsaacSensorCreateRtxLidar",
        path="/lidar_sensor",
        parent=prim_path_of_husky,
        config=lidar_config,
        translation=(0, 50, 0),
        orientation=Gf.Quatd(0.70710677,0.70710677,0,0),
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

def publish_pointcloud_from_depth(camera: Camera, freq):
    # The following code will link the camera's render product and publish the data to the specified topic name.
    render_product = camera._render_product_path
    step_size = int(60/freq)
    topic_name = camera.name+"_pointcloud" # Set topic name to the camera's name
    queue_size = 1
    node_namespace = ""
    frame_id = camera.prim_path.split("/")[-1] # This matches what the TF tree is publishing.

    # Note, this pointcloud publisher will simply convert the Depth image to a pointcloud using the Camera intrinsics.
    # This pointcloud generation method does not support semantic labelled objects.
    rv = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(
        sd.SensorType.DistanceToImagePlane.name
    )

    writer = rep.writers.get(rv + "ROS2PublishPointCloud")
    writer.initialize(
        frameId=frame_id,
        nodeNamespace=node_namespace,
        queueSize=queue_size,
        topicName=topic_name
    )
    writer.attach([render_product])

    # Set step input of the Isaac Simulation Gate nodes upstream of ROS publishers to control their execution rate
    gate_path = omni.syntheticdata.SyntheticData._get_node_path(
        rv + "IsaacSimulationGate", render_product
    )
    og.Controller.attribute(gate_path + ".inputs:step").set(step_size)

    return

def publish_rgb(camera: Camera, freq):
    # The following code will link the camera's render product and publish the data to the specified topic name.
    render_product = camera._render_product_path
    step_size = int(60/freq)
    topic_name = camera.name+"_rgb"
    queue_size = 1
    node_namespace = ""
    frame_id = camera.prim_path.split("/")[-1] # This matches what the TF tree is publishing.

    rv = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(sd.SensorType.Rgb.name)
    writer = rep.writers.get(rv + "ROS2PublishImage")
    writer.initialize(
        frameId=frame_id,
        nodeNamespace=node_namespace,
        queueSize=queue_size,
        topicName=topic_name
    )
    writer.attach([render_product])

    # Set step input of the Isaac Simulation Gate nodes upstream of ROS publishers to control their execution rate
    gate_path = omni.syntheticdata.SyntheticData._get_node_path(
        rv + "IsaacSimulationGate", render_product
    )
    og.Controller.attribute(gate_path + ".inputs:step").set(step_size)

    return

def publish_camera_tf(camera: Camera):
    camera_prim = camera.prim_path

    if not is_prim_path_valid(camera_prim):
        raise ValueError(f"Camera path '{camera_prim}' is invalid.")

    try:
        # Generate the camera_frame_id. OmniActionGraph will use the last part of
        # the full camera prim path as the frame name, so we will extract it here
        # and use it for the pointcloud frame_id.
        camera_frame_id=camera_prim.split("/")[-1]

        # Generate an action graph associated with camera TF publishing.
        ros_camera_graph_path = "/CameraTFActionGraph"

        # If a camera graph is not found, create a new one.
        if not is_prim_path_valid(ros_camera_graph_path):
            (ros_camera_graph, _, _, _) = og.Controller.edit(
                {
                    "graph_path": ros_camera_graph_path,
                    "evaluator_name": "execution",
                    "pipeline_stage": og.GraphPipelineStage.GRAPH_PIPELINE_STAGE_SIMULATION,
                },
                {
                    og.Controller.Keys.CREATE_NODES: [
                        ("OnTick", "omni.graph.action.OnTick"),
                        ("IsaacClock", "omni.isaac.core_nodes.IsaacReadSimulationTime"),
                        ("RosPublisher", "omni.isaac.ros2_bridge.ROS2PublishClock"),
                    ],
                    og.Controller.Keys.CONNECT: [
                        ("OnTick.outputs:tick", "RosPublisher.inputs:execIn"),
                        ("IsaacClock.outputs:simulationTime", "RosPublisher.inputs:timeStamp"),
                    ]
                }
            )

        # Generate 2 nodes associated with each camera: TF from world to ROS camera convention, and world frame.
        og.Controller.edit(
            ros_camera_graph_path,
            {
                og.Controller.Keys.CREATE_NODES: [
                    ("PublishTF_"+camera_frame_id, "omni.isaac.ros2_bridge.ROS2PublishTransformTree"),
                    ("PublishRawTF_"+camera_frame_id+"_world", "omni.isaac.ros2_bridge.ROS2PublishRawTransformTree"),
                ],
                og.Controller.Keys.SET_VALUES: [
                    ("PublishTF_"+camera_frame_id+".inputs:topicName", "/tf"),
                    # Note if topic_name is changed to something else besides "/tf",
                    # it will not be captured by the ROS tf broadcaster.
                    ("PublishRawTF_"+camera_frame_id+"_world.inputs:topicName", "/tf"),
                    ("PublishRawTF_"+camera_frame_id+"_world.inputs:parentFrameId", camera_frame_id),
                    ("PublishRawTF_"+camera_frame_id+"_world.inputs:childFrameId", camera_frame_id+"_world"),
                    # Static transform from ROS camera convention to world (+Z up, +X forward) convention:
                    ("PublishRawTF_"+camera_frame_id+"_world.inputs:rotation", [0.5, -0.5, 0.5, 0.5]),
                ],
                og.Controller.Keys.CONNECT: [
                    (ros_camera_graph_path+"/OnTick.outputs:tick",
                        "PublishTF_"+camera_frame_id+".inputs:execIn"),
                    (ros_camera_graph_path+"/OnTick.outputs:tick",
                        "PublishRawTF_"+camera_frame_id+"_world.inputs:execIn"),
                    (ros_camera_graph_path+"/IsaacClock.outputs:simulationTime",
                        "PublishTF_"+camera_frame_id+".inputs:timeStamp"),
                    (ros_camera_graph_path+"/IsaacClock.outputs:simulationTime",
                        "PublishRawTF_"+camera_frame_id+"_world.inputs:timeStamp"),
                ],
            },
        )
    except Exception as e:
        print(e)

    # Add target prims for the USD pose. All other frames are static.
    set_target_prims(
        primPath=ros_camera_graph_path+"/PublishTF_"+camera_frame_id,
        inputName="inputs:targetPrims",
        targetPrimPaths=[camera_prim],
    )
    return

def publish_depth(camera: Camera, freq):
    # The following code will link the camera's render product and publish the data to the specified topic name.
    render_product = camera._render_product_path
    step_size = int(60/freq)
    topic_name = camera.name+"_depth"
    queue_size = 1
    node_namespace = ""
    frame_id = camera.prim_path.split("/")[-1] # This matches what the TF tree is publishing.

    rv = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(
                            sd.SensorType.DistanceToImagePlane.name
                        )
    writer = rep.writers.get(rv + "ROS2PublishImage")
    writer.initialize(
        frameId=frame_id,
        nodeNamespace=node_namespace,
        queueSize=queue_size,
        topicName=topic_name
    )
    writer.attach([render_product])

    # Set step input of the Isaac Simulation Gate nodes upstream of ROS publishers to control their execution rate
    gate_path = omni.syntheticdata.SyntheticData._get_node_path(
        rv + "IsaacSimulationGate", render_product
    )
    og.Controller.attribute(gate_path + ".inputs:step").set(step_size)

    return

def publish_camera_info(camera: Camera, freq):
    # The following code will link the camera's render product and publish the data to the specified topic name.
    render_product = camera._render_product_path
    step_size = int(60/freq)
    topic_name = camera.name+"_camera_info"
    queue_size = 1
    node_namespace = ""
    frame_id = camera.prim_path.split("/")[-1] # This matches what the TF tree is publishing.

    writer = rep.writers.get("ROS2PublishCameraInfo")
    camera_info = read_camera_info(render_product_path=render_product)
    writer.initialize(
        frameId=frame_id,
        nodeNamespace=node_namespace,
        queueSize=queue_size,
        topicName=topic_name,
        width=camera_info["width"],
        height=camera_info["height"],
        projectionType=camera_info["projectionType"],
        k=camera_info["k"].reshape([1, 9]),
        r=camera_info["r"].reshape([1, 9]),
        p=camera_info["p"].reshape([1, 12]),
        physicalDistortionModel=camera_info["physicalDistortionModel"],
        physicalDistortionCoefficients=camera_info["physicalDistortionCoefficients"],
    )
    writer.attach([render_product])

    gate_path = omni.syntheticdata.SyntheticData._get_node_path(
        "PostProcessDispatch" + "IsaacSimulationGate", render_product
    )

    # Set step input of the Isaac Simulation Gate nodes upstream of ROS publishers to control their execution rate
    og.Controller.attribute(gate_path + ".inputs:step").set(step_size)
    return

def update_scaling_orientation(prim, translation):
    global using_isaac_sim
    adj_height = 14.4
    # Upadates the position including rotation
    try:  # If you are using Isaac Sim an error message will appear
        prim.GetAttribute("xformOP:rotateXYZ").Set(Gf.Vec3f(90.0,0,0))

    except Exception as e:
        # Handles the error in quite a bad way - TODO
        print("The following error is expected if you are using Isaac Sim.")
        if hasattr(e, 'message'):
            print(e.mesage)
        else:
            print(e)

        using_isaac_sim = True  # Due to the error, its expected that the code runs inside of isaac sim

        # Executes Isaac Sim specific code
        prim.GetAttribute('xformOp:orient').Set(Gf.Quatf(0.70710677, 0.70710677, 0, 0))
        # Scales it down, since there is a conversion error in issac sim
        prim.GetAttribute("xformOp:scale").Set(Gf.Vec3f(0.01, 0.01, 0.01))

    finally:
        if using_isaac_sim:
            adj_height *= 0.01
        if translation[2] < adj_height:
            prim.GetAttribute("xformOp:translate").Set(Gf.Vec3f(translation[0], 
                                                            translation[1],
                                                            adj_height))
    return adj_height
