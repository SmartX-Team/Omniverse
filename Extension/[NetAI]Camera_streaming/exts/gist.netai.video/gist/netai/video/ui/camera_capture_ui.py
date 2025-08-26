"""UI components for Camera Capture Extension

1.1.0 버전 기준으로 UI 구조는 분리시킴 -Inyong Song
"""

import omni.ui as ui
import weakref
import functools
from typing import Dict, Callable, Optional
import asyncio

class CameraCaptureUI:
    """Manages the UI for Camera Capture Extension"""
    
    def __init__(self, 
                 default_camera_path: str,
                 default_output_dir: str,
                 callbacks: Dict[str, Callable]):
        """
        Initialize UI manager
        
        Args:
            default_camera_path: Default camera path
            default_output_dir: Default output directory  
            callbacks: Dictionary of callback functions from main extension
        """
        self._window = None
        self._callbacks = callbacks
        self._camera_ui_container = None
        self._camera_ui_items = {}  # Store UI references for each camera
        
        # Models for input fields
        self._camera_path_model = ui.SimpleStringModel(default_camera_path)
        self._output_dir_model = ui.SimpleStringModel(default_output_dir)
        
        self._build_window()
    
    def _build_window(self):
        """Build the main UI window"""
        self._window = ui.Window("Camera Capture Controller", width=800, height=600)
        
        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                self._build_header()
                self._build_input_section()
                ui.Line()
                self._build_camera_list_section()
                ui.Line()
                self._build_global_controls()
    
    def _build_header(self):
        """Build header section"""
        ui.Label("Off-screen Camera Capture System", 
                style={"font_size": 16, "font_weight": "bold"})
        ui.Line()
    
    def _build_input_section(self):
        """Build input section for adding cameras"""
        with ui.VStack(spacing=5):
            # Camera path input
            with ui.HStack(height=30, spacing=5):
                ui.Label("Camera Path:", width=100)
                ui.StringField(model=self._camera_path_model, width=ui.Percent(70))
            
            # Output directory input
            with ui.HStack(height=30, spacing=5):
                ui.Label("Output Dir:", width=100)
                ui.StringField(model=self._output_dir_model, width=ui.Percent(70))
            
            # Add button
            ui.Button("Add Camera", 
                     clicked_fn=self._on_add_camera_clicked,
                     height=30,
                     style={"background_color": 0xFF4A90E2})
    
    def _build_camera_list_section(self):
        """Build camera list section"""
        ui.Label("Managed Cameras:", style={"font_size": 14})
        with ui.ScrollingFrame(
            height=ui.Pixel(400),
            horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
            vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON
        ):
            self._camera_ui_container = ui.VStack(spacing=8)
    
    def _build_global_controls(self):
        """Build global control buttons"""
        with ui.HStack(spacing=5):
            ui.Button("Stop All Captures", 
                     clicked_fn=self._callbacks.get("stop_all"),
                     style={"background_color": 0xFFE74C3C})
            ui.Button("Clear All", 
                     clicked_fn=self._callbacks.get("clear_all"),
                     style={"background_color": 0xFF95A5A6})
    
    def _on_add_camera_clicked(self):
        """Handle add camera button click"""
        camera_path = self._camera_path_model.get_value_as_string().strip()
        output_dir = self._output_dir_model.get_value_as_string().strip()
        
        if self._callbacks.get("add_camera"):
            self._callbacks["add_camera"](camera_path, output_dir)
    
    def add_camera_ui(self, camera_id: int, camera_path: str, output_dir: str) -> dict:
        """
        Add UI for a specific camera
        
        Returns:
            Dictionary containing UI models and references
        """
        if not self._camera_ui_container:
            print("[ERROR] Camera UI container not initialized.")
            return None
        
        # Create models for UI inputs
        ui_models = {
            "interval_model": ui.SimpleFloatModel(1.0),
            "frame_count_model": ui.SimpleIntModel(5),
            "resolution_x_model": ui.SimpleIntModel(1280),
            "resolution_y_model": ui.SimpleIntModel(720)
        }
        
        ui_refs = {}
        
        with self._camera_ui_container:
            frame_title = f"Camera {camera_id}: {camera_path}"
            collapsable_frame = ui.CollapsableFrame(frame_title, collapsed=False)
            ui_refs["frame"] = collapsable_frame
            
            with collapsable_frame:
                with ui.VStack(spacing=5, height=0):
                    # Status display
                    ui_refs["status_label"] = ui.Label("Status: Ready", word_wrap=True)
                    ui_refs["progress_label"] = ui.Label("", word_wrap=True)
                    
                    # Output directory display
                    with ui.HStack(height=25, spacing=5):
                        ui.Label("Output:", width=80)
                        ui.Label(output_dir, style={"color": 0xFF888888})
                    
                    # Resolution input
                    with ui.HStack(height=25, spacing=5):
                        ui.Label("Resolution:", width=80)
                        ui.IntField(model=ui_models["resolution_x_model"], width=60)
                        ui.Label("x", width=20)
                        ui.IntField(model=ui_models["resolution_y_model"], width=60)
                    
                    # Capture settings
                    with ui.HStack(height=25, spacing=5):
                        ui.Label("Interval (s):", width=80)
                        ui.FloatField(model=ui_models["interval_model"], width=60)
                        ui.Label("Frames:", width=60)
                        ui.IntField(model=ui_models["frame_count_model"], width=60)
                    
                    ui.Line(height=2)
                    
                    # Control buttons
                    self._build_camera_controls(camera_path, camera_id)
        
        self._camera_ui_items[camera_path] = {**ui_models, **ui_refs}
        return self._camera_ui_items[camera_path]
    
    def _build_camera_controls(self, camera_path: str, camera_id: int):
        """Build control buttons for a camera"""
        with ui.HStack(spacing=5):
            ui.Button("Capture Once", 
                     clicked_fn=functools.partial(
                         self._callbacks.get("capture_once"), camera_path, camera_id
                     ),
                     tooltip=f"Capture single frame from camera {camera_id}")
            ui.Button("Start Periodic", 
                     clicked_fn=functools.partial(
                         self._callbacks.get("capture_periodic"), camera_path, camera_id
                     ),
                     tooltip=f"Start periodic capture",
                     style={"background_color": 0xFF27AE60})
        
        with ui.HStack(spacing=5):
            ui.Button("Stop Capture", 
                     clicked_fn=functools.partial(
                         self._callbacks.get("stop_capture"), camera_path, camera_id
                     ),
                     tooltip="Stop ongoing capture",
                     style={"background_color": 0xFFE67E22})
            ui.Button("Remove", 
                     clicked_fn=functools.partial(
                         self._callbacks.get("remove_camera"), camera_path, camera_id
                     ),
                     tooltip="Remove camera from management",
                     style={"color": 0xFFFF6666})
    
    def remove_camera_ui(self, camera_path: str):
        """Remove camera UI by hiding first, then destroying"""
        if camera_path not in self._camera_ui_items:
            print(f"[Warning] Camera UI not found for path: {camera_path}")
            return
        
        ui_item = self._camera_ui_items[camera_path]
        frame = ui_item.get("frame")
        
        if frame:
            frame.visible = False
        
        # deferred destroy를 위한 태스크 생성
        async def cleanup():
            await asyncio.sleep(0.1)  # 100ms 대기
            if frame:
                try:
                    frame.destroy()
                except:
                    pass
        
        # 딕셔너리에서는 즉시 제거
        del self._camera_ui_items[camera_path]
        print(f"[Info] Camera removed: {camera_path}")
        
        # 정리는 백그라운드에서
        asyncio.ensure_future(cleanup())
    
    def update_status(self, camera_path: str, status: str):
        """Update status label for a camera"""
        if camera_path in self._camera_ui_items:
            label = self._camera_ui_items[camera_path].get("status_label")
            if label:
                label.text = status
    
    def update_progress(self, camera_path: str, progress: str):
        """Update progress label for a camera"""
        if camera_path in self._camera_ui_items:
            label = self._camera_ui_items[camera_path].get("progress_label")
            if label:
                label.text = progress
    
    def get_camera_path(self) -> str:
        """Get current camera path from input field"""
        return self._camera_path_model.get_value_as_string().strip()
    
    def get_output_dir(self) -> str:
        """Get current output directory from input field"""
        return self._output_dir_model.get_value_as_string().strip()
    
    def destroy(self):
        """Clean up UI"""
        if self._window:
            self._window.destroy()
        self._window = None
        self._camera_ui_container = None
        self._camera_ui_items.clear()