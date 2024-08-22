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
# =======================================================================================

# Links:
# (1) https://ewww.gist.ac.kr/en/main.html
# (2) https://clearpathrobotics.com/husky-unmanned-ground-vehicle-robot/
# (3) https://docs.omniverse.nvidia.com/isaacsim/latest/overview.html
# (4) https://docs.ros.org/en/humble/index.html

# Imports
# Used for working with the USD File Format
from pxr import Gf

# Basic Imports from Omniverse (Most of them are installed with Omniverse KIT)
import omni.ext
import omni.kit.commands
import omni.ui as ui
from omni.usd import get_context

# Actuall Sensor import
from omni.isaac.sensor import _sensor
from .isaac_sensor import *

# Listeners for ROS2 Topics
# And movement of Husky in Isaac Sim
from .ros2_recivers import *

# Additional Helper functions from Isaac Sim (for convenience purposes only)
from .slice_of_life_adjustments import *
import warnings 

# Please change the specification of Husky to be as precise as possible.
# TODO: Use the robot.yaml file from clearpath to automaticly do it.

# The prim path of Husky in Isaac Sim
# The prim_path is viewable by selecting the entire robot and looking into the inspector.
# TODO: Make it selectable in the Sim, which prim you want to choose.
prim_path_of_husky = "/World/Ni_KI_Husky"

# Additionaly please select the footprint of the model so the height can be correctly be adjusted.
prim_path_of_footprint = prim_path_of_husky + "/base_footprint"

# Furtermore we need the next two paths for attaching the sensors to the robot
prim_path_of_front_bumper = prim_path_of_husky + "/front_bumper_link"  # Front Bumper
prim_path_of_lidar = prim_path_of_husky + "/lidar_link"  # LiDAR

# Please refer to the actual robot to double check if the correct lidar is being selected.
# The following link refers to the possible configurations:
# https://docs.omniverse.nvidia.com/isaacsim/latest/features/sensors_simulation/isaac_sim_sensors_rtx_based_lidar.html#lidar-config-files
lidar_config = "OS1_32ch10hz2048res"

# The following variables should not be changed!
# The center of mass of husky is used as origin. And since the robot still needs to drive with its tires and not 
# with its chassy, the height gets adjusted based on the difference between origin and husky's footprint
height_of_husky_adjusted = False

# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.
class NiKiTestRosExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def on_startup(self, ext_id):
        print("[ni.ki.test.ros] ni ki test ros startup")
        print_info()  # Creates Info Box
        # print_fox()  # Creates a picture of a cute fox >.<

        self._window = ui.Window("Test ROS (Ni-KI)", width=500, height=180)
        with self._window.frame:
            with ui.VStack():
                label = ui.Label("")
                label.text = "Extension not initalised."

                def on_initalize():
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
                    
                    update_scaling_orientation(prim, stage, self.translate)

                    label.text += "| Position: Valid "
                    
                    # Husky RGB Cam
                    husky_cam_path = prim_path_of_front_bumper + "/husky_rgb_cam"
                    husky_depth_cam_path = prim_path_of_front_bumper + "/husky_depth_cam"
                    self.husky_cam_prim = stage.GetPrimAtPath(husky_cam_path)
                    if not self.husky_cam_prim.IsValid():
                        self.husky_cam = create_rgb_camera(stage=stage, prim_path=husky_cam_path)
                        self.husky_cam_prim = stage.GetPrimAtPath(husky_cam_path)
                        self.husky_cam_depth = create_depth_camera(stage=stage, prim_path=husky_depth_cam_path)

                    label.text += " | Husky Cam: Valid"
                    
                    # LiDAR
                    lidar_sensor_path = prim_path_of_lidar + "/lidar_sensor"
                    self.lidar_sensor = stage.GetPrimAtPath(lidar_sensor_path)
                    lidar_created = True
                    if not self.lidar_sensor.IsValid():
                        lidar_created = create_lidar_sensor(prim_path_of_lidar, lidar_config)
                        self.lidar_sensor = stage.GetPrimAtPath(lidar_sensor_path)
                    
                    if not lidar_created:
                        label.text += " | LiDAR: Failed"
                    else:
                        label.text += " | LiDAR: Valid"

                        # Creates the IMU only if the LiDAR worked.
                        create_imu_sensor(stage, prim_path_of_lidar)
                        
                        # In the case of husky the IMU is part of the LiDAR sensor
                        # Get the data of the IMU
                        _imu_sensor_interface = _sensor.acquire_imu_sensor_interface()
                        data = _imu_sensor_interface.get_sensor_reading(prim_path_of_lidar + "/imu_sensor", use_latest_data = True, read_gravity = True)
                        print("Data is valid: ", data.is_valid)

                        label.text += " | IMU: Valid"

                    
                    # Delets the root of all evil - the root joint, if it exists
                    # It should not, since it's mainly used for static robots
                    # If its still there KILL it on sight, since it causes MANY issues.
                    path_to_root_joint = prim_path_of_husky + "/root_joint"
                    root_of_all_evil = stage.GetPrimAtPath(path_to_root_joint)
                    if root_of_all_evil.IsValid() and stage.RemovePrim(path_to_root_joint):  # It's the root of all evil
                        warnings.warn("Root Joint was removed! This might cause issues in the future! - NI.KI.Test.ROS")
                        print("The hero (this program) killed the demon (root_joint)! Rejoice!")  # Flavor text >.<
                    elif root_of_all_evil.IsValid():  # It is there, but it coulnd't be removed :-(
                        warnings.warn("Please delet (husky)/root_joint on your own accord so that the robot can move.")
                        print("Oh nooo! The hero (this program) is unable to defeat the root of all evil (root_joint)!")
                    else:
                        print("You are blessed! The hero (this program) could not find its arch enemy (root_joint)!")



                    label.text += "\n\nInit finished."
                    return True
            
                
                def on_cosmo():
                    # This function contains a heavy missues of jerk (3rd derivative of position) as a second velocity!
                    on_cease()

                    label.text = "Let's go! >.<\n\nPlease also run an instance of the Tank Controll script."
                    create_tank_controll_listener(prim_path_of_husky)
                    print_instructions_for_tank_controll()
                    

                def on_pilot():
                    label.text = "LET'S GO HUSKY!"
                    
                    # Gets the required prim of the husky
                    stage = get_context().get_stage()

                    # Needs to remove the driver before forcefully applying speed
                    try:
                        stage.RemovePrim("/ackermann_drive_reciver")
                    except:
                        pass

                    bl_wheel = stage.GetPrimAtPath(prim_path_of_husky + "/base_link/back_left_wheel_joint")
                    bl_wheel.GetAttribute("drive:angular:physics:stiffness").Set(0)
                    bl_wheel.GetAttribute("drive:angular:physics:targetVelocity").Set(1000)

                    br_wheel = stage.GetPrimAtPath(prim_path_of_husky + "/base_link/back_right_wheel_joint")
                    br_wheel.GetAttribute("drive:angular:physics:stiffness").Set(0)
                    br_wheel.GetAttribute("drive:angular:physics:targetVelocity").Set(1000)

                    fl_wheel = stage.GetPrimAtPath(prim_path_of_husky + "/base_link/front_left_wheel_joint")
                    fl_wheel.GetAttribute("drive:angular:physics:stiffness").Set(0)
                    fl_wheel.GetAttribute("drive:angular:physics:targetVelocity").Set(1000)

                    fr_wheel = stage.GetPrimAtPath(prim_path_of_husky + "/base_link/front_right_wheel_joint")
                    fr_wheel.GetAttribute("drive:angular:physics:stiffness").Set(0)
                    fr_wheel.GetAttribute("drive:angular:physics:targetVelocity").Set(1000)

                    self.wheels = [bl_wheel, br_wheel, fl_wheel, fr_wheel]

                def on_cease():
                    # Gets the required prim of the husky
                    stage = get_context().get_stage()

                    on_pilot()  # Used to reset the speed - Seems weird, but trust me on this
                    
                    label.text = "Shutdown of Movement system initated."

                    # This is extermly hardcoded pls do something about it ㅜㅜ
                    # TODO: Save the world from this hardcode ****
                    bl_wheel = stage.GetPrimAtPath(prim_path_of_husky + "/base_link/back_left_wheel_joint")
                    bl_wheel.GetAttribute("drive:angular:physics:stiffness").Set(0)
                    bl_wheel.GetAttribute("drive:angular:physics:targetVelocity").Set(0)

                    br_wheel = stage.GetPrimAtPath(prim_path_of_husky + "/base_link/back_right_wheel_joint")
                    br_wheel.GetAttribute("drive:angular:physics:stiffness").Set(0)
                    br_wheel.GetAttribute("drive:angular:physics:targetVelocity").Set(0)

                    fl_wheel = stage.GetPrimAtPath(prim_path_of_husky + "/base_link/front_left_wheel_joint")
                    fl_wheel.GetAttribute("drive:angular:physics:stiffness").Set(0)
                    fl_wheel.GetAttribute("drive:angular:physics:targetVelocity").Set(0)

                    fr_wheel = stage.GetPrimAtPath(prim_path_of_husky + "/base_link/front_right_wheel_joint")
                    fr_wheel.GetAttribute("drive:angular:physics:stiffness").Set(0)
                    fr_wheel.GetAttribute("drive:angular:physics:targetVelocity").Set(0)

                on_initalize()
                with ui.VStack():
                    with ui.HStack():
                        ui.Button("Init.", clicked_fn=on_initalize, tooltip="Sets up the robot.")
                        ui.Button("Cease", clicked_fn=on_cease, tooltip="Stops the energy.")
                    with ui.HStack():
                        ui.Button("Cosmo", clicked_fn=on_cosmo, 
                                  tooltip="Enables yout to drive via tankcontrol. - COntrolled Simulated MOtion")
                        ui.Button("Pilot", clicked_fn=on_pilot, 
                                  tooltip="Runs an auto-pilot that drives husky in a straight line.")

    def on_shutdown(self):
        print("[ni.ki.test.ros] ni ki test ros shutdown")

def update_scaling_orientation(prim, stage, translation):
    adj_height = -stage.GetPrimAtPath(prim_path_of_husky + "/base_footprint").GetAttribute("xformOp:translate").Get()[2]
    
    # Upadates the position including rotation
    prim.GetAttribute('xformOp:orient').Set(Gf.Quatd(0, 0, 0, 0))
    prim.GetAttribute("xformOp:translate").Set(Gf.Vec3f(translation[0], translation[1], adj_height))
    return adj_height
