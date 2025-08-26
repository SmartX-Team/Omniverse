# camera_capture_extension.py
"""Main extension that coordinates UI and business logic"""

import omni.ext
import asyncio
from omni.usd import get_context
from .ui.camera_capture_ui import CameraCaptureUI
from .core.camera_capture_manager import CameraCaptureManager
from .core.camera_validator import CameraValidator

# Default Configuration
DEFAULT_CAMERA_PATH = "/World/Camera"
DEFAULT_OUTPUT_DIR = "/home/netai/Documents/traffic_captures"

class CameraCaptureExtension(omni.ext.IExt):
    """
    Omniverse Extension for managing multiple camera captures
    without changing viewport using render products.
    """
    
    def on_startup(self, ext_id: str):
        """Called upon extension startup"""
        print(f"[{ext_id}] CameraCaptureExtension startup")
        
        # Initialize manager
        self.stage = get_context().get_stage()
        self.capture_manager = CameraCaptureManager(self.stage)
        
        # Setup callbacks for UI
        callbacks = {
            "add_camera": self._on_add_camera,
            "capture_once": self._on_capture_once,
            "capture_periodic": self._on_capture_periodic,
            "stop_capture": self._on_stop_capture,
            "remove_camera": self._on_remove_camera,
            "stop_all": self._on_stop_all,
            "clear_all": self._on_clear_all
        }
        
        # Initialize UI
        self.ui = CameraCaptureUI(
            DEFAULT_CAMERA_PATH,
            DEFAULT_OUTPUT_DIR,
            callbacks
        )
    
    def _on_add_camera(self, camera_path: str, output_dir: str):
        """Handle add camera request"""
        # Validate camera
        is_valid, error_msg = CameraValidator.validate_camera(
            self.stage, 
            camera_path, 
            self.capture_manager.cameras
        )
        if not is_valid:
            print(f"[Warning] {error_msg}")
            return
        
        print(f"[Info] Adding camera: {camera_path}")
        
        # Get camera ID for UI
        temp_id = self.capture_manager._next_camera_id
        
        # Create UI elements
        ui_refs = self.ui.add_camera_ui(temp_id, camera_path, output_dir)
        
        if ui_refs:
            # Add camera to manager with UI references
            self.capture_manager.add_camera(camera_path, output_dir, ui_refs)
    
    def _on_capture_once(self, camera_path: str, camera_id: int):
        """Handle single capture request"""
        camera_info = self.capture_manager.cameras.get(camera_path)
        if not camera_info:
            return
        
        self.ui.update_status(camera_path, "Capturing...")
        
        task = asyncio.ensure_future(
            self.capture_manager.capture_single_frame(camera_path)
        )
        
        def on_complete(future):
            if future.result():
                self.ui.update_status(camera_path, "Single frame captured")
            else:
                self.ui.update_status(camera_path, "Capture failed")
        
        task.add_done_callback(on_complete)
    
    def _on_capture_periodic(self, camera_path: str, camera_id: int):
        """Handle periodic capture request"""
        self.capture_manager.start_periodic_capture(camera_path)
    
    def _on_stop_capture(self, camera_path: str, camera_id: int):
        """Handle stop capture request"""
        self.capture_manager.stop_capture(camera_path)
    
    def _on_remove_camera(self, camera_path: str, camera_id: int):
        """Handle remove camera request"""
        print(f"[Info] Removing camera: {camera_path}")
        self.capture_manager.remove_camera(camera_path)
        self.ui.remove_camera_ui(camera_path)
    
    def _on_stop_all(self):
        """Handle stop all captures request"""
        self.capture_manager.stop_all_captures()
    
    def _on_clear_all(self):
        """Handle clear all cameras request"""
        for camera_path in list(self.capture_manager.cameras.keys()):
            self._on_remove_camera(camera_path, 0)
    
    def on_shutdown(self):
        """Called upon extension shutdown"""
        print("[CameraCaptureExtension] Shutdown")
        
        # Cleanup manager
        self.capture_manager.cleanup()
        
        # Cleanup UI
        self.ui.destroy()
        
        self.stage = None
        print("[CameraCaptureExtension] Shutdown complete")