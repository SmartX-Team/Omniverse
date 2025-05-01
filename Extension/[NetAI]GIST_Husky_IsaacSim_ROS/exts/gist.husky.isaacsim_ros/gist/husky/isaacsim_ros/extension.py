# extension.py (Multi-Robot UI - Strong Label Ref)

import omni.ext
import omni.ui as ui
from omni.usd import get_context
import omni.usd
import importlib # Using importlib based on previous troubleshooting
# weakref is no longer needed for the label, but keep it for the frame
import weakref
import functools # Import functools

# --- Constants and Configuration ---
DEFAULT_ROBOT_PATH = "/World/Ni_KI_Husky"

class NiKiTestRosExtension(omni.ext.IExt):
    """
    Omniverse Extension UI for managing and controlling multiple simulated Husky robots
    in Isaac Sim, integrating with ROS2 Humble. Uses strong reference for labels.
    """
    def on_startup(self, ext_id: str):
        """Called upon extension startup."""
        print(f"[{ext_id}] NiKiTestRosExtension startup")

        # --- Load necessary modules ---
        self.actions = importlib.import_module(".actions", package=__package__)
        self.utils = importlib.import_module(".utils", package=__package__)

        self.utils.print_info()

        # --- Initialize members ---
        self._window = None
        self.stage = get_context().get_stage()
        # Dictionary to store managed robots: {robot_path: {"frame_ref": weakref, "label": ui.Label, ...}}
        self.managed_robots = {}
        self._robot_path_model = ui.SimpleStringModel(DEFAULT_ROBOT_PATH)
        self._robot_ui_container = None # This will be the VStack inside ScrollingFrame

        if not self.stage:
            print("[ERROR] Failed to get USD Stage.")
            # return # Uncomment to stop if stage is crucial early on

        print(f"[DEBUG] Extension Instance ID: {id(self)}")

        # --- Build the UI Window ---
        self._window = ui.Window("Multi-Robot ROS Controller", width=700, height=400)

        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                # --- Input Section ---
                with ui.HStack(height=30, spacing=5):
                    ui.Label("Robot Base Path:", width=ui.Percent(25))
                    ui.StringField(model=self._robot_path_model, width=ui.Percent(55))
                    ui.Button("Add Robot", clicked_fn=self._on_add_robot_clicked, width=ui.Percent(20))

                # --- Separator ---
                ui.Line()

                # --- Robot List Area ---
                with ui.ScrollingFrame(
                    height=ui.Pixel(250), # Fixed height
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON
                ):
                    # This VStack holds the CollapsableFrame for each robot directly
                    self._robot_ui_container = ui.VStack(spacing=8)

                # --- Separator ---
                ui.Line()


    def _on_add_robot_clicked(self):
        """Callback when the 'Add Robot' button is clicked."""
        robot_path = self._robot_path_model.get_value_as_string().strip()
        if not robot_path:
            print("[Warning] Robot path cannot be empty.")
            return

        if not robot_path.startswith("/"):
             print(f"[Warning] Invalid path format: '{robot_path}'. Path should start with '/'.")
             return

        if robot_path in self.managed_robots:
            print(f"[Warning] Robot path '{robot_path}' is already managed.")
            return

        if not self.stage:
             print("[ERROR] Cannot validate path: USD Stage is not available.")
             return
        try:
            robot_prim = self.stage.GetPrimAtPath(robot_path)
            if not robot_prim or not robot_prim.IsValid():
                print(f"[Warning] Prim not found or invalid at path: '{robot_path}'. Cannot add robot.")
                return
        except Exception as e:
            print(f"[ERROR] Error validating path '{robot_path}': {e}. Check path syntax.")
            return

        print(f"[Info] Adding UI for robot: {robot_path}")
        self._add_robot_ui(robot_path)


    def _add_robot_ui(self, robot_path: str):
        """Creates and adds the UI section for a specific robot."""
        if not self._robot_ui_container:
            print("[ERROR] Robot UI container not initialized.")
            return

        # --- Create UI elements directly under the container ---
        collapsable_frame = None
        robot_label = None

        with self._robot_ui_container:
            collapsable_frame = ui.CollapsableFrame(robot_path, collapsed=False)
            with collapsable_frame:
                with ui.VStack(spacing=5, height=0):
                    robot_label = ui.Label("Status: Ready", word_wrap=True)
                    # --- Store STRONG reference to label, weak ref to frame ---
                    robot_info = {
                        "path": robot_path,
                        "label": robot_label, # <<< Store the label object directly
                        "frame_ref": weakref.ref(collapsable_frame), # Keep weakref for frame
                    }
                    # --- End reference storage change ---

                    lidar_config = "OS1_REV6_32ch10hz2048res"

                    # --- Pre-create callback functions using functools.partial ---
                    on_init_callback = functools.partial(self._on_init_clicked, robot_path)
                    on_cease_callback = functools.partial(self._on_cease_clicked, robot_path)
                    on_cosmo_callback = functools.partial(self._on_cosmo_clicked, robot_path)
                    on_pilot_callback = functools.partial(self._on_pilot_clicked, robot_path)
                    on_remove_callback = functools.partial(self._on_remove_clicked, robot_path)
                    # --- End Pre-creation ---

                    # --- Assign pre-created callbacks to buttons ---
                    with ui.HStack(spacing=5):
                        ui.Button("Init", clicked_fn=on_init_callback,
                                  tooltip=f"Initialize sensors for {robot_path}")
                        ui.Button("Cease", clicked_fn=on_cease_callback,
                                  tooltip=f"Stop movement for {robot_path}")
                    with ui.HStack(spacing=5):
                        ui.Button("Cosmo", clicked_fn=on_cosmo_callback,
                                  tooltip=f"Enable ROS2 control for {robot_path}")
                        ui.Button("Pilot", clicked_fn=on_pilot_callback,
                                  tooltip=f"Simple forward movement for {robot_path}")

                    ui.Button("Remove", clicked_fn=on_remove_callback,
                              tooltip=f"Remove {robot_path}")
                    # --- End Assignment ---

        # Check if UI elements were created before storing
        if collapsable_frame and robot_label:
            # Store the callbacks in robot_info as well
            robot_info["callbacks"] = {
                "init": on_init_callback,
                "cease": on_cease_callback,
                "cosmo": on_cosmo_callback,
                "pilot": on_pilot_callback,
                "remove": on_remove_callback,
            }
            self.managed_robots[robot_path] = robot_info
            print(f"[Info] Robot '{robot_path}' added to management. Total: {len(self.managed_robots)}")
        else:
             print(f"[ERROR] Failed to create UI elements (CollapsableFrame/Label) for {robot_path}")

    # --- Callback Methods for Robot Buttons ---
    def _get_robot_label_widget(self, robot_path: str) -> ui.Label | None:
        """Helper to get the actual label widget using the stored strong reference."""
        if robot_path in self.managed_robots:
            robot_info = self.managed_robots[robot_path]
            # --- Get label directly from the dictionary ---
            label_widget = robot_info.get("label")
            if label_widget:
                # Optional: Check if the widget is still valid in the UI tree (though less likely to fail now)
                # if label_widget.visible: # Or another property check
                return label_widget
                # else:
                #     print(f"[Warning] Label widget for {robot_path} found but might be hidden or invalid.")
            else:
                 print(f"[Warning] No label widget stored for {robot_path}.")
            # --- End direct retrieval ---
        else:
            print(f"[Warning] Robot path '{robot_path}' not found in managed list.")
        return None

    # --- Other callback methods (_on_init_clicked, etc.) remain the same ---
    # They will now receive a valid label_widget from _get_robot_label_widget
    def _on_init_clicked(self, robot_path: str):
        """Callback for the 'Init' button."""
        label_widget = self._get_robot_label_widget(robot_path)
        if label_widget:
            lidar_config = "OS1_REV6_32ch10hz2048res"
            self.actions.initialize_husky(self.stage, label_widget, robot_path,
                                        f"{robot_path}/front_bumper_link", f"{robot_path}/lidar_link", lidar_config)
        else:
            print(f"[ERROR] Cannot execute Init for {robot_path}, label widget not found or invalid.")

    def _on_cease_clicked(self, robot_path: str):
        """Callback for the 'Cease' button."""
        label_widget = self._get_robot_label_widget(robot_path)
        if label_widget:
            self.actions.cease_movement(self.stage, label_widget, robot_path)
        else:
            print(f"[ERROR] Cannot execute Cease for {robot_path}, label widget not found or invalid.")

    def _on_cosmo_clicked(self, robot_path: str):
        """Callback for the 'Cosmo' button."""
        label_widget = self._get_robot_label_widget(robot_path)
        if label_widget:
            self.actions.start_cosmo_mode(self.stage, label_widget, robot_path)
        else:
            print(f"[ERROR] Cannot execute Cosmo for {robot_path}, label widget not found or invalid.")

    def _on_pilot_clicked(self, robot_path: str):
        """Callback for the 'Pilot' button."""
        label_widget = self._get_robot_label_widget(robot_path)
        if label_widget:
            self.actions.pilot_forward(self.stage, label_widget, robot_path)
        else:
            print(f"[ERROR] Cannot execute Pilot for {robot_path}, label widget not found or invalid.")

    def _on_remove_clicked(self, robot_path: str):
        """Callback for the 'Remove' button."""
        self._remove_robot_ui(robot_path)

    # --- End Callback Methods ---


    def _remove_robot_ui(self, robot_path: str):
        """Removes the UI section for a specific robot and cleans up."""
        print(f"[Info] Attempting to remove robot UI for: {robot_path}")
        if robot_path in self.managed_robots:
            robot_info = self.managed_robots.pop(robot_path)
            # Remove the CollapsableFrame widget using its weak reference
            frame_ref = robot_info.get("frame_ref")
            if frame_ref:
                frame = frame_ref()
                if frame:
                    frame.destroy()
                    print(f"[Info] Robot UI (CollapsableFrame) for '{robot_path}' removed successfully.")
                else:
                    print(f"[Warning] CollapsableFrame for '{robot_path}' already destroyed or invalid weakref during removal.")
            else:
                 print(f"[Warning] No frame reference found for '{robot_path}' during removal.")

            # The strong reference to the label in robot_info is now gone
            # The label widget itself will be destroyed when its parent frame is destroyed

            print(f"[Info] Robots remaining: {list(self.managed_robots.keys())}")
        else:
            print(f"[Warning] Robot path '{robot_path}' not found in management list for removal.")


    def on_shutdown(self):
        """Called upon extension shutdown."""
        print("[ni.ki.test.ros] NiKiTestRosExtension shutdown")
        # Clean up managed robot data and UI elements
        for robot_path in list(self.managed_robots.keys()):
            self._remove_robot_ui(robot_path)
        self.managed_robots.clear()

        if self._window:
            self._window.destroy()
        self._window = None
        self.stage = None
        self._robot_path_model = None
        self._robot_ui_container = None
        print("[DEBUG] Shutdown complete.")

