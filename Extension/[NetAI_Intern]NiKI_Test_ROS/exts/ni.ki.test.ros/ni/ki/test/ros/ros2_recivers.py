# Creates graph based node systems in Isaac Sim for the purpose of listening to ROS2 Topics
# and moving husky in accordance with those.
# It's important to note that *ONLY ONE* of the two should be active and *NOT BOTH* at once!
# The options are: Joystick or Tank Controll

# Used to create a graph node
import omni.graph.core as og

def create_tank_controll_listener(prim_path_of_husky):
    keys = og.Controller.Keys
    (graph_handle, list_of_nodes, _, _) = og.Controller.edit(
        {"graph_path": "/ackermann_drive_reciver", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("tick", "omni.graph.action.OnPlaybackTick"),
                ("ack_sub", "omni.isaac.ros2_bridge.ROS2SubscribeAckermannDrive"),
                ("array", "omni.graph.nodes.ConstructArray"),
                ("array_add1", "omni.graph.nodes.ArrayInsertValue"),
                ("array_add2", "omni.graph.nodes.ArrayInsertValue"),
                ("array_add3", "omni.graph.nodes.ArrayInsertValue"),
                ("controller", "omni.isaac.core_nodes.IsaacArticulationController")
            ],
            keys.SET_VALUES: [
                ("array.inputs:arraySize", 1),
                ("controller.inputs:targetPrim", prim_path_of_husky),
                ("controller.inputs:jointNames", [
                    "back_right_wheel_joint",
                    "back_left_wheel_joint",
                    "front_right_wheel_joint",
                    "front_left_wheel_joint",
                                                    ]),
                ("controller.inputs:robotPath", "/World/Ni_KI_Husky/base_link"),
                ("controller.inputs:usePath", True),
            ],
            keys.CONNECT: [
                ("tick.outputs:tick", "ack_sub.inputs:execIn"),
                ("tick.outputs:tick", "controller.inputs:execIn"),
                ("array.outputs:array", "array_add1.inputs:array"),
                ("ack_sub.outputs:speed", "array.inputs:input0"),
                ("ack_sub.outputs:speed", "array_add2.inputs:value"),
                ("ack_sub.outputs:jerk", "array_add1.inputs:value"),
                ("ack_sub.outputs:jerk", "array_add3.inputs:value"),
                ("array_add1.outputs:array", "array_add2.inputs:array"),
                ("array_add2.outputs:array", "array_add3.inputs:array"),
                ("array_add3.outputs:array","controller.inputs:velocityCommand")
            ],
        },
    )

def create_joystick_listener(prim_path_of_husky):
    keys = og.Controller.Keys
    (graph_handle, list_of_nodes, _, _) = og.Controller.edit(
        {"graph_path": "/ackermann_drive_reciver", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("tick", "omni.graph.action.OnPlaybackTick"),
                ("odom","omni.isaac.core_nodes.IsaacComputeOdometry"),
                ("ack_sub", "omni.isaac.ros2_bridge.ROS2SubscribeAckermannDrive"),
                ("ack_dri", "omni.isaac.wheeled_robots.AckermannSteering"),
                ("array", "omni.graph.nodes.ConstructArray"),
                ("array_res", "omni.graph.nodes.ArrayResize"),
                ("array_fill", "omni.graph.nodes.ArrayFill"),
                ("controller", "omni.isaac.core_nodes.IsaacArticulationController")
            ],
            keys.SET_VALUES: [
                ("array.inputs:arraySize", 4),
                ("array_res.inputs:newSize", 4),
                ("odom.inputs:chassisPrim", prim_path_of_husky),
                ("controller.inputs:targetPrim", prim_path_of_husky),
                ("controller.inputs:jointNames", [
                    "back_right_wheel_joint",
                    "back_left_wheel_joint",
                    "front_right_wheel_joint",
                    "front_left_wheel_joint",
                                                    ]),
                ("ack_dri.inputs:turningWheelRadius", 0.5),
                ("ack_dri.inputs:maxWheelVelocity", 250),
                ("controller.inputs:robotPath", "/World/Ni_KI_Husky/base_link"),
                ("controller.inputs:usePath", True),
            ],
            keys.CONNECT: [
                ("tick.outputs:tick", "odom.inputs:execIn"),
                ("tick.outputs:tick", "ack_sub.inputs:execIn"),
                ("tick.outputs:tick", "ack_dri.inputs:execIn"),
                ("tick.outputs:deltaSeconds", "ack_dri.inputs:DT"),
                ("tick.outputs:tick", "controller.inputs:execIn"),
                ("odom.outputs:linearVelocity", "ack_dri.inputs:currentLinearVelocity"),
                ("ack_sub.outputs:acceleration", "ack_dri.inputs:acceleration"),
                ("ack_dri.outputs:wheelRotationVelocity", "array.inputs:input0"),
                ("ack_dri.outputs:wheelRotationVelocity", "array_fill.inputs:fillValue"),
                ("array.outputs:array", "array_res.inputs:array"),
                ("array_res.outputs:array", "array_fill.inputs:array"),
                ("array_fill.outputs:array", "controller.inputs:velocityCommand")
                # ("ack_dri.outputs:wheelRotationVelocity", "array.inputs:input2"),
                # ("ack_dri.outputs:wheelRotationVelocity", "array.inputs:input3")
            ],
        },
    )
