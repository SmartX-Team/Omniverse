# Creates graph based node systems in Isaac Sim for the purpose of listening to ROS2 Topics
# and moving husky in accordance with those.
# It's important to note that *ONLY ONE* of the two should be active and *NOT BOTH* at once!
# The options are: Joystick or Tank Controll

# Used to create a graph node
import omni.graph.core as og
from omni.usd import get_context # Need get_context for the check

# --- Function to check and create Tank Control Listener ---
def create_tank_controll_listener(prim_path_of_husky):
    graph_path = "/ackermann_drive_reciver" # Graph prim path
    stage = get_context().get_stage()
    if stage is None:
         print("Error: Could not get USD stage context.")
         return

    # Check if graph already exists
    if stage.GetPrimAtPath(graph_path).IsValid():
        print(f"OmniGraph '{graph_path}' already exists.")
        return # Exit if graph exists

    # Create the graph
    print(f"Creating OmniGraph '{graph_path}' for Tank Control and TF...")
    keys = og.Controller.Keys
    try:
        og.Controller.edit(
            {"graph_path": graph_path, "evaluator_name": "execution"},
            {
                keys.CREATE_NODES: [
                    # Core nodes
                    ("tick", "omni.graph.action.OnPlaybackTick"),
                    ("controller", "omni.isaac.core_nodes.IsaacArticulationController"),

                    # ROS 2 Nodes
                    # Verify this node type name is exactly correct for your IS version
                    ("ack_sub", "isaacsim.ros2.bridge.ROS2SubscribeAckermannDrive"),

                    # --- TF Publishing Setup ---
                    # Node for Static Transforms (/tf_static)
                    ("tf_static_pub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
                    # Node for Dynamic Transforms (/tf)
                    ("tf_dynamic_pub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
                    # -------------------------

                    # Nodes for processing Ackermann -> Velocity Array (Tank Control Hack)
                    ("array", "omni.graph.nodes.ConstructArray"),
                    ("array_add1", "omni.graph.nodes.ArrayInsertValue"),
                    ("array_add2", "omni.graph.nodes.ArrayInsertValue"),
                    ("array_add3", "omni.graph.nodes.ArrayInsertValue"),
                ],
                keys.SET_VALUES: [
                    # Ackermann Subscriber settings
                    ("ack_sub.inputs:topicName", "/ackermann_cmd"),

                    # Static TF Publisher settings
                    ("tf_static_pub.inputs:targetPrims", [prim_path_of_husky]), # Target the robot prim
                    # Alternatively, use primPath="/World" to publish everything below /World
                    # ("tf_static_pub.inputs:primPath", "/World"),
                    ("tf_static_pub.inputs:topicName", "/tf_static"), # Publish to /tf_static
                    ("tf_static_pub.inputs:useTfStatic", True), # Publish only static transforms

                    # Dynamic TF Publisher settings
                    ("tf_dynamic_pub.inputs:targetPrims", [prim_path_of_husky]), # Target the robot prim
                    # Alternatively, use primPath="/World"
                    # ("tf_dynamic_pub.inputs:primPath", "/World"),
                    ("tf_dynamic_pub.inputs:topicName", "/tf"), # Publish to /tf
                    ("tf_dynamic_pub.inputs:useTfStatic", False), # Publish dynamic transforms

                    # Articulation Controller settings
                    ("array.inputs:arraySize", 1), # Initial size for array logic below
                    ("controller.inputs:targetPrim", prim_path_of_husky), # Control the Husky prim
                    ("controller.inputs:jointNames", [ # List joints to control
                        "back_right_wheel_joint", "back_left_wheel_joint",
                        "front_right_wheel_joint", "front_left_wheel_joint"
                     ]),
                ],
                keys.CONNECT: [
                    # Connect Playback Tick to nodes that need continuous execution
                    ("tick.outputs:tick", "ack_sub.inputs:execIn"),
                    ("tick.outputs:tick", "controller.inputs:execIn"),
                    # Connect tick ONLY to the DYNAMIC TF publisher
                    ("tick.outputs:tick", "tf_dynamic_pub.inputs:execIn"),
                    # Static TF publisher usually works without execIn after creation

                    # Logic for converting Ackermann (speed/jerk hack) to wheel velocities
                    ("array.outputs:array", "array_add1.inputs:array"),
                    # Verify these output attribute names based on the actual node
                    ("ack_sub.outputs:speed", "array.inputs:input0"),
                    ("ack_sub.outputs:speed", "array_add2.inputs:value"), # Left speed -> index 2
                    ("ack_sub.outputs:jerk", "array_add1.inputs:value"),  # Right speed (from jerk) -> index 1
                    ("ack_sub.outputs:jerk", "array_add3.inputs:value"),  # Right speed (from jerk) -> index 3
                    # Resulting array order might need adjustment based on jointNames order:
                    # Check if order should be [BR, BL, FR, FL] or something else.
                    # Current connections result in [Speed, Jerk, Speed, Jerk] fed to controller
                    ("array_add1.outputs:array", "array_add2.inputs:array"),
                    ("array_add2.outputs:array", "array_add3.inputs:array"),
                    ("array_add3.outputs:array","controller.inputs:velocityCommand")
                ],
            },
        )
        print(f"Successfully created OmniGraph '{graph_path}' with TF publishers.")
    except Exception as e:
        error_msg = f"Error during OmniGraph creation for '{graph_path}': {e}"
        warnings.warn(error_msg) # Use warning instead of print for visibility in console
        # Optionally re-raise e if the caller needs to handle it
        # raise e

# --- Function to check and create Joystick Listener ---
# Apply the SAME logic: check if graph exists first
def create_joystick_listener(prim_path_of_husky):
    graph_path = "/ackermann_drive_reciver" # Using the same graph path! This will conflict.
    # *** IMPORTANT: You cannot have both listeners trying to create/use the SAME graph path. ***
    # *** You need different graph_path values (e.g., "/joystick_listener_graph") ***
    # *** OR modify the extension logic to only call ONE of these functions. ***
    # *** Assuming for now you only intend to use create_tank_controll_listener ***
    # *** If you need both, the paths MUST be different. ***

    stage = get_context().get_stage()
    if stage is None:
         print("Error: Could not get USD stage context.")
         return

    # Check if graph prim already exists
    if stage.GetPrimAtPath(graph_path).IsValid():
        print(f"Graph already exists at {graph_path}. Cannot create joystick listener here.")
        # Decide how to handle this - maybe delete existing graph first? Or use different path?
        # Returning for now to avoid overwriting tank controller graph.
        return # <<<<< EXIT EARLY

    # Graph does not exist, proceed with creation
    print(f"Creating OmniGraph at {graph_path} for Joystick Control...")
    keys = og.Controller.Keys
    try:
        (graph_handle, list_of_nodes, _, _) = og.Controller.edit(
             {"graph_path": graph_path, "evaluator_name": "execution"},
             { # Graph definition...
                 keys.CREATE_NODES: [
                    ("tick", "omni.graph.action.OnPlaybackTick"),
                    ("odom","omni.isaac.core_nodes.IsaacComputeOdometry"),
                    # --- Use the CORRECT Node Type Name found previously ---
                    ("ack_sub", "isaacsim.ros2.bridge.ROS2SubscribeAckermannDrive"),
                    # ---------------------------------------------------------
                    ("ack_dri", "omni.isaac.wheeled_robots.AckermannSteering"),
                    ("array", "omni.graph.nodes.ConstructArray"),
                    ("array_res", "omni.graph.nodes.ArrayResize"),
                    ("array_fill", "omni.graph.nodes.ArrayFill"),
                    ("controller", "omni.isaac.core_nodes.IsaacArticulationController")
                ],
                # ... rest of SET_VALUES, CONNECT ...
                # Remember to verify input/output names for ack_sub node
             }
        )
        print(f"Successfully created graph at {graph_path}")
    except Exception as e:
        print(f"Error during initial graph creation for {graph_path}: {e}")
