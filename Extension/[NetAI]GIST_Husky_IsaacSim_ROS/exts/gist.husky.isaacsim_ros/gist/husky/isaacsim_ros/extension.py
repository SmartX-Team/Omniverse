# extension.py (Multi-Robot UI - Strong Label Ref)

import omni.ext
import omni.ui as ui
from omni.usd import get_context
import omni.usd
import importlib
import weakref
import functools

# --- Constants and Configuration ---
DEFAULT_ROBOT_PATH = "/World/Ni_KI_Husky"

class NetAIRosExtension(omni.ext.IExt):
    """
    Omniverse Extension UI for managing multiple simulated Husky robots
    with individual Domain ID configuration for ROS2 communication.
    """
    def on_startup(self, ext_id: str):
        """Called upon extension startup."""
        print(f"[{ext_id}] NetAIRosExtension startup")

        # --- Load necessary modules ---
        self.actions = importlib.import_module(".actions", package=__package__)
        self.utils = importlib.import_module(".utils", package=__package__)

        self.utils.print_info()

        # --- Initialize members ---
        self._window = None
        self.stage = get_context().get_stage()
        self.managed_robots = {}
        self._robot_path_model = ui.SimpleStringModel(DEFAULT_ROBOT_PATH)
        self._robot_ui_container = None
        self._next_robot_id = 0  # 자동 증가 robot_id

        if not self.stage:
            print("[ERROR] Failed to get USD Stage.")

        print(f"[DEBUG] Extension Instance ID: {id(self)}")

        # --- Build the UI Window ---
        self._window = ui.Window("Multi-Robot ROS2 Domain Controller", width=750, height=500)

        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                # --- Header ---
                ui.Label("Multi-Robot ROS2 Domain Configuration", 
                        style={"font_size": 16, "font_weight": "bold"})
                ui.Line()
                
                # --- Input Section ---
                with ui.HStack(height=30, spacing=5):
                    ui.Label("Robot Path:", width=100)
                    ui.StringField(model=self._robot_path_model, width=ui.Percent(70))
                    ui.Button("Add Robot", 
                             clicked_fn=self._on_add_robot_clicked, 
                             width=ui.Percent(20))

                ui.Line()

                # --- Robot List Area ---
                ui.Label("Managed Robots:", style={"font_size": 14})
                with ui.ScrollingFrame(
                    height=ui.Pixel(350),
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON
                ):
                    self._robot_ui_container = ui.VStack(spacing=8)

                ui.Line()

    def _on_add_robot_clicked(self):
        """Callback when 'Add Robot' button is clicked."""
        robot_path = self._robot_path_model.get_value_as_string().strip()
        
        # Validation
        if not robot_path:
            print("[Warning] Robot path cannot be empty.")
            return

        if not robot_path.startswith("/"):
            print(f"[Warning] Invalid path format: '{robot_path}'.")
            return

        if robot_path in self.managed_robots:
            print(f"[Warning] Robot '{robot_path}' is already managed.")
            return

        # Check if prim exists
        if not self.stage:
            print("[ERROR] USD Stage is not available.")
            return
            
        try:
            robot_prim = self.stage.GetPrimAtPath(robot_path)
            if not robot_prim or not robot_prim.IsValid():
                print(f"[Warning] Prim not found at path: '{robot_path}'.")
                return
        except Exception as e:
            print(f"[ERROR] Error validating path '{robot_path}': {e}")
            return

        print(f"[Info] Adding robot: {robot_path}")
        self._add_robot_ui(robot_path)

    def _add_robot_ui(self, robot_path: str):
        """Creates UI section for a specific robot with Domain ID input."""
        if not self._robot_ui_container:
            print("[ERROR] Robot UI container not initialized.")
            return

        # Assign unique robot_id
        robot_id = self._next_robot_id
        self._next_robot_id += 1
        
        # Create domain_id model (default to robot_id)
        domain_id_model = ui.SimpleIntModel(robot_id)
        
        collapsable_frame = None
        robot_label = None
        domain_field = None

        with self._robot_ui_container:
            frame_title = f"Robot {robot_id}: {robot_path}"
            collapsable_frame = ui.CollapsableFrame(frame_title, collapsed=False)
            
            with collapsable_frame:
                with ui.VStack(spacing=5, height=0):
                    # Status display
                    robot_label = ui.Label("Status: Ready", word_wrap=True)
                    
                    # Domain ID input field
                    with ui.HStack(height=25, spacing=5):
                        ui.Label("Domain ID:", width=80)
                        domain_field = ui.IntField(model=domain_id_model, width=60)
                        ui.Label(f"(Default: {robot_id})", style={"color": 0xFF888888})
                    
                    ui.Line(height=2)
                    
                    # Control buttons
                    lidar_config = "OS1_REV6_32ch10hz2048res"
                    
                    # Pre-create callbacks with robot_id
                    on_init_callback = functools.partial(
                        self._on_init_clicked, robot_path, robot_id
                    )
                    on_create_graph_callback = functools.partial(
                        self._on_create_graph_clicked, robot_path, robot_id
                    )
                    on_delete_graph_callback = functools.partial(
                        self._on_delete_graph_clicked, robot_path, robot_id
                    )
                    on_remove_callback = functools.partial(
                        self._on_remove_clicked, robot_path, robot_id
                    )
                    
                    # Buttons
                    with ui.HStack(spacing=5):
                        ui.Button("Initialize", 
                                 clicked_fn=on_init_callback,
                                 tooltip=f"Initialize sensors for robot {robot_id}")
                        ui.Button("Create Graph", 
                                 clicked_fn=on_create_graph_callback,
                                 tooltip=f"Create ROS2 control graph with Domain ID")
                    
                    with ui.HStack(spacing=5):
                        ui.Button("Delete Graph", 
                                 clicked_fn=on_delete_graph_callback,
                                 tooltip="Delete ROS2 control graph")
                        ui.Button("Remove", 
                                 clicked_fn=on_remove_callback,
                                 tooltip="Remove robot from management",
                                 style={"color": 0xFFFF6666})

        # Store robot information
        if collapsable_frame and robot_label:
            robot_info = {
                "path": robot_path,
                "robot_id": robot_id,
                "label": robot_label,
                "frame_ref": weakref.ref(collapsable_frame),
                "domain_id_model": domain_id_model,
                "graph_created": False,
                "initialized": False
            }
            
            self.managed_robots[robot_path] = robot_info
            print(f"[Info] Robot added - ID: {robot_id}, Path: {robot_path}")
            print(f"[Info] Total robots: {len(self.managed_robots)}")

    def _get_robot_label_widget(self, robot_path: str):
        """Get label widget for a robot."""
        if robot_path in self.managed_robots:
            return self.managed_robots[robot_path].get("label")
        return None

    def _get_robot_info(self, robot_path: str):
        """Get complete robot info."""
        return self.managed_robots.get(robot_path)

    # --- Callback Methods ---
    def _on_init_clicked(self, robot_path: str, robot_id: int):
        """Initialize sensors for the robot."""
        label_widget = self._get_robot_label_widget(robot_path)
        if label_widget:
            label_widget.text = "Initializing..."
            lidar_config = "OS1_REV6_32ch10hz2048res"
            
            # Call existing initialize function with robot_id
            success = self.actions.initialize_husky(
                self.stage, 
                label_widget, 
                robot_path,
                f"{robot_path}/front_bumper_link", 
                f"{robot_path}/lidar_link", 
                lidar_config,
                robot_id  # Pass robot_id
            )
            
            if success:
                robot_info = self._get_robot_info(robot_path)
                if robot_info:
                    robot_info["initialized"] = True
                label_widget.text = "Initialized"
            else:
                label_widget.text = "Init Failed"

    def _on_create_graph_clicked(self, robot_path: str, robot_id: int):
        """Create ROS2 control graph with Domain ID."""
        robot_info = self._get_robot_info(robot_path)
        if not robot_info:
            print(f"[ERROR] Robot info not found for {robot_path}")
            return
        
        if not robot_info.get("initialized"):
            print(f"[Warning] Initialize robot first: {robot_path}")
            return
        
        label_widget = robot_info["label"]
        domain_id = robot_info["domain_id_model"].as_int
        
        if label_widget:
            label_widget.text = f"Creating Graph (Domain: {domain_id})..."
            
            # Call new function to create graph with domain_id
            success = self.actions.create_ros2_control_graph(
                self.stage,
                label_widget,
                robot_path,
                robot_id,
                domain_id
            )
            
            if success:
                robot_info["graph_created"] = True
                label_widget.text = f"Graph Active (Domain: {domain_id})"
            else:
                label_widget.text = "Graph Creation Failed"

    def _on_delete_graph_clicked(self, robot_path: str, robot_id: int):
        """Delete ROS2 control graph."""
        robot_info = self._get_robot_info(robot_path)
        if not robot_info:
            return
        
        label_widget = robot_info["label"]
        
        if label_widget:
            success = self.actions.delete_ros2_control_graph(
                self.stage,
                label_widget,
                robot_path,
                robot_id
            )
            
            if success:
                robot_info["graph_created"] = False
                label_widget.text = "Graph Deleted"

    def _on_remove_clicked(self, robot_path: str, robot_id: int):
        """Remove robot from management."""
        self._remove_robot_ui(robot_path)

    def _remove_robot_ui(self, robot_path: str):
        """Remove robot UI and cleanup."""
        print(f"[Info] Removing robot: {robot_path}")
        
        if robot_path not in self.managed_robots:
            print(f"[Warning] Robot path '{robot_path}' not found.")
            return
        
        robot_info = self.managed_robots[robot_path]
        robot_id = robot_info["robot_id"]  # robot_info에서 직접 가져오기
        
        # Delete graph if exists
        if robot_info.get("graph_created"):
            try:
                success = self.actions.delete_ros2_control_graph(
                    self.stage,
                    None,
                    robot_path,
                    robot_id
                )
                if success:
                    print(f"[Info] Graph deleted for robot {robot_id}")
            except Exception as e:
                print(f"[Error] Failed to delete graph: {e}")
        # Then destroy UI
        frame_ref = robot_info.get("frame_ref")
        if frame_ref:
            frame = frame_ref()
            if frame:
                try:
                    # frame이 아직 유효한지 확인
                    if frame.visible is not None:  # frame이 살아있는지 체크
                        frame.visible = False  # 먼저 숨기기
                        frame.destroy()  # 그 다음 삭제
                        print(f"[Info] UI frame destroyed for {robot_path}")
                    else:
                        print(f"[Warning] Frame already invalid for {robot_path}")
                except Exception as e:
                    print(f"[Error] Failed to destroy frame: {e}")
                    # 강제로 시도
                    try:
                        frame.destroy()
                    except:
                        pass
            else:
                print(f"[Warning] Frame reference lost for {robot_path}")
        else:
            print(f"[Warning] No frame reference for {robot_path}")
        
        
        print(f"[Info] Robot removed. Remaining: {len(self.managed_robots)} robots")

    def on_shutdown(self):
        """Called upon extension shutdown."""
        print("[NetAIRosExtension] NetAI RoS2 Robot Simulation shutdown")
        
        # Cleanup all robots
        for robot_path in list(self.managed_robots.keys()):
            self._remove_robot_ui(robot_path)
        
        self.managed_robots.clear()
        
        if self._window:
            self._window.destroy()
        self._window = None
        self.stage = None
        print("[DEBUG] Shutdown complete.")