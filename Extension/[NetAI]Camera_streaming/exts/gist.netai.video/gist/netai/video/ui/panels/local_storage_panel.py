# ui/panels/local_storage_panel.py
import omni.ui as ui
import functools
from typing import Dict, Any, Callable
from .base_panel import CameraPanelBase

class LocalStoragePanel(CameraPanelBase):
    """Panel for local storage capture mode"""
    
    def __init__(self, camera_id: int, camera_path: str, container: ui.Widget, callbacks: Dict[str, Callable]):
        super().__init__(camera_id, camera_path, container)
        self.callbacks = callbacks
        self.output_dir = ""
    
    def build_panel(self, output_dir: str = "/home/netai/Documents/traffic_captures", resolution: list = None, interval: float = None, 
                frame_count: int = None, **kwargs) -> Dict[str, Any]:
        """Build local storage panel UI"""
        self.output_dir = output_dir
        
        # Create UI models
        self._ui_models = {
            "interval_model": ui.SimpleFloatModel(interval if interval else 1.0),
            "frame_count_model": ui.SimpleIntModel(frame_count if frame_count else 5),
            "resolution_x_model": ui.SimpleIntModel(resolution[0] if resolution else 1280),
            "resolution_y_model": ui.SimpleIntModel(resolution[1] if resolution and len(resolution) > 1 else 720)
        }
        
        # Build UI
        with self.container:
            frame_title = f"Camera {self.camera_id}: {self.camera_path}"
            self._frame = ui.CollapsableFrame(frame_title, collapsed=False)
            self._ui_refs["frame"] = self._frame
            
            with self._frame:
                with ui.VStack(spacing=5, height=0):
                    self._build_status_section()
                    self._build_settings_section()
                    ui.Line(height=2)
                    self._build_control_buttons()
        
        # Return combined references
        return self.get_all_refs()
    
    def _build_status_section(self):
        """Build status display section"""
        self._ui_refs["status_label"] = ui.Label("Status: Ready", word_wrap=True)
        self._ui_refs["progress_label"] = ui.Label("", word_wrap=True)
        
        # Output directory display
        with ui.HStack(height=25, spacing=5):
            ui.Label("Output:", width=80)
            ui.Label(self.output_dir, style={"color": 0xFF888888})
    
    def _build_settings_section(self):
        """Build capture settings section"""
        # Resolution input
        with ui.HStack(height=25, spacing=5):
            ui.Label("Resolution:", width=80)
            ui.IntField(model=self._ui_models["resolution_x_model"], width=60)
            ui.Label("x", width=20)
            ui.IntField(model=self._ui_models["resolution_y_model"], width=60)
        
        # Capture settings
        with ui.HStack(height=25, spacing=5):
            ui.Label("Interval (s):", width=80)
            ui.FloatField(model=self._ui_models["interval_model"], width=60)
            ui.Label("Frames:", width=60)
            ui.IntField(model=self._ui_models["frame_count_model"], width=60)
    
    def _build_control_buttons(self):
        """Build control buttons"""
        with ui.HStack(spacing=5):
            ui.Button("Capture Once", 
                     clicked_fn=functools.partial(
                         self.callbacks.get("capture_once"), 
                         self.camera_path, self.camera_id
                     ),
                     tooltip=f"Capture single frame from camera {self.camera_id}")
            ui.Button("Start Periodic", 
                     clicked_fn=functools.partial(
                         self.callbacks.get("capture_periodic"), 
                         self.camera_path, self.camera_id
                     ),
                     tooltip=f"Start periodic capture",
                     style={"background_color": 0xFF27AE60})
        
        with ui.HStack(spacing=5):
            ui.Button("Stop Capture", 
                     clicked_fn=functools.partial(
                         self.callbacks.get("stop_capture"), 
                         self.camera_path, self.camera_id
                     ),
                     tooltip="Stop ongoing capture",
                     style={"background_color": 0xFFE67E22})
            ui.Button("Remove", 
                     clicked_fn=functools.partial(
                         self.callbacks.get("remove_camera"), 
                         self.camera_path, self.camera_id
                     ),
                     tooltip="Remove camera from management",
                     style={"color": 0xFFFF6666})
    
    def get_capture_mode(self) -> str:
        """Return capture mode type"""
        return "LOCAL"
    
    def get_output_dir(self) -> str:
        """Get output directory"""
        return self.output_dir