# ui/camera_capture_ui.py
import omni.ui as ui
import asyncio
from typing import Dict, Callable, Optional
from .panels.local_storage_panel import LocalStoragePanel
from .panels.base_panel import CameraPanelBase

class CameraCaptureUI:
    """Manages the UI for Camera Capture Extension with panel abstraction"""
    
    def __init__(self, 
                 default_camera_path: str,
                 default_output_dir: str,
                 callbacks: Dict[str, Callable]):
        self._window = None
        self._callbacks = callbacks
        self._camera_ui_container = None
        self._camera_panels = {}  # Store panel objects
        
        # Models for input fields
        self._camera_path_model = ui.SimpleStringModel(default_camera_path)
        self._output_dir_model = ui.SimpleStringModel(default_output_dir)
        
        # Default capture mode
        self._default_capture_mode = "LOCAL"
        
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
    
    def add_camera_panel(self, camera_id: int, camera_path: str, output_dir: str, 
                        capture_mode: str = "LOCAL") -> Optional[Dict]:
        """Add a camera panel based on capture mode"""
        if not self._camera_ui_container:
            print("[ERROR] Camera UI container not initialized.")
            return None
        
        # Create appropriate panel based on mode
        panel = None
        if capture_mode == "LOCAL":
            panel = LocalStoragePanel(camera_id, camera_path, self._camera_ui_container, self._callbacks)
        # elif capture_mode == "KAFKA":
        #     panel = KafkaStreamingPanel(camera_id, camera_path, self._camera_ui_container, self._callbacks)
        else:
            print(f"[ERROR] Unknown capture mode: {capture_mode}")
            return None
        
        # Build panel UI
        ui_refs = panel.build_panel(output_dir=output_dir)
        
        # Store panel object
        self._camera_panels[camera_path] = panel
        
        return ui_refs
    
    def remove_camera_panel(self, camera_path: str):
        """Remove camera panel with proper cleanup"""
        if camera_path not in self._camera_panels:
            print(f"[Warning] Camera panel not found for path: {camera_path}")
            return
        
        panel = self._camera_panels[camera_path]
        
        # Hide immediately
        panel.hide()
        
        # Deferred destroy
        async def cleanup():
            await asyncio.sleep(0.1)
            if not panel.is_destroyed():
                panel.destroy()
        
        # Remove from dictionary
        del self._camera_panels[camera_path]
        print(f"[Info] Camera panel removed: {camera_path}")
        
        # Schedule cleanup
        asyncio.ensure_future(cleanup())
    
    def update_status(self, camera_path: str, status: str):
        """Update status for a camera panel"""
        if camera_path in self._camera_panels:
            self._camera_panels[camera_path].update_status(status)
    
    def update_progress(self, camera_path: str, progress: str):
        """Update progress for a camera panel"""
        if camera_path in self._camera_panels:
            self._camera_panels[camera_path].update_progress(progress)
    
    def get_panel(self, camera_path: str) -> Optional[CameraPanelBase]:
        """Get panel object for a camera"""
        return self._camera_panels.get(camera_path)
    
    def destroy(self):
        """Clean up UI"""
        # Destroy all panels
        for panel in self._camera_panels.values():
            if not panel.is_destroyed():
                panel.destroy()
        
        if self._window:
            self._window.destroy()
        
        self._window = None
        self._camera_ui_container = None
        self._camera_panels.clear()