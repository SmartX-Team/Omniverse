# camera_capture_extension.py
"""Main extension that coordinates UI and business logic
"""

import omni.ext
import asyncio
import gc
import time
from omni.usd import get_context
from .ui.camera_capture_ui import CameraCaptureUI
from .core.camera_capture_manager import CameraCaptureManager
from .core.camera_validator import CameraValidator
import omni.replicator.core as rep

from .utils.preset_loader import PresetLoader

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

        self._cleanup_existing_replicator_resources()
        
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
            "clear_all": self._on_clear_all,
            "load_preset": self._on_load_preset,
            "save_preset": self._on_save_preset

        }
        
        # Initialize UI
        self.ui = CameraCaptureUI(
            DEFAULT_CAMERA_PATH,
            DEFAULT_OUTPUT_DIR,
            callbacks
        )
    
    def _on_add_camera(self, camera_path: str, output_or_config: str, capture_mode: str = "LOCAL"):
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
        
        print(f"[Info] Adding camera: {camera_path} with mode: {capture_mode}")
        
        # Get camera ID for UI
        temp_id = self.capture_manager._next_camera_id
        
        # Create UI elements
        ui_refs = self.ui.add_camera_panel(temp_id, camera_path, output_or_config, capture_mode)
        
        if ui_refs:
            # Add camera to manager with UI references
            self.capture_manager.add_camera(camera_path, output_or_config, ui_refs, capture_mode)
    
    def _on_capture_once(self, camera_path: str, camera_id: int):
        """Handle single capture request"""
        camera_info = self.capture_manager.cameras.get(camera_path)
        if not camera_info:
            return
        
        self.ui.update_status(camera_path, "Capturing...")
        
        task = asyncio.ensure_future(
            self.capture_manager.capture_single_frame(camera_path, pause_sim=True)
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
        import time
        time.sleep(0.1)
        
        # UI 패널 제거
        self.ui.remove_camera_panel(camera_path)
        
        print(f"[Info] Camera {camera_id} removal complete")
    
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
        
        # 모든 캡처 정지
        self.capture_manager.stop_all_captures()
        
        # 각 카메라별 리소스 확실히 정리
        for camera_path in list(self.capture_manager.cameras.keys()):
            camera_info = self.capture_manager.cameras[camera_path]
            
            # Writer detach
            if camera_info.get("writer"):
                try:
                    camera_info["writer"].detach()
                    camera_info["writer"] = None
                except:
                    pass
            
            # Render product 정리
            if camera_info.get("render_product"):
                camera_info["render_product"] = None
        
        # Orchestrator 정지
        try:
            if rep.orchestrator.get_is_started():
                rep.orchestrator.stop()
                print("[Info] Orchestrator stopped")
        except Exception as e:
            print(f"[Warning] Error stopping orchestrator: {e}")
        
        # Manager 정리
        self.capture_manager.cleanup()
        
        # UI 정리
        self.ui.destroy()
        
        self.stage = None
        print("[CameraCaptureExtension] Shutdown complete")

    def _cleanup_existing_replicator_resources(self):
        """Clean up any existing replicator resources from previous sessions"""

        try:
            print("[Info] Starting aggressive Replicator cleanup...")
            
            # 1. 모든 실행 중인 비동기 태스크 취소
            for task in asyncio.all_tasks():
                if 'capture' in str(task).lower():
                    task.cancel()

            try:
                print("[Info] Cleaning up existing Replicator resources...")
                
                # Orchestrator 정지
                if rep.orchestrator.get_is_started():
                    rep.orchestrator.stop()
                    print("[Info] Stopped existing orchestrator")
            except:
                pass
            # 모든 writer 정리 시도
            try:
                # WriterRegistry의 모든 writer 정리
                writers_cleared = 0
                for writer_name in ['BasicWriter', 'RtxWriter', 'KittiWriter']:
                    try:
                        writer = rep.WriterRegistry.get(writer_name)
                        if writer:
                            writer.detach()
                            writers_cleared += 1
                    except:
                        pass
                
                # Registry 자체 초기화 시도
                rep.WriterRegistry.clear()
                print(f"[Info] Cleared {writers_cleared} writer types")
            except AttributeError:
                pass

            try:
                # 모든 render product 찾아서 정리
                import omni.syntheticdata as sd
                sd._sensor_helpers.clear_all_sensors()
            except:
                pass

            gc.collect()
            time.sleep(0.1)
            # Orchestrator 재시작
            rep.orchestrator.run()
            print("[Info] Replicator resources cleaned and reinitialized")
            
        except Exception as e:
            print(f"[Warning] Error during replicator cleanup: {e}")



    def _on_load_preset(self, preset_path: str):
        """Load cameras from preset file"""
        preset_data = PresetLoader.load_preset(preset_path)

        print(f"[Info] Loading preset from: {preset_path}")

        if not preset_data:
            return
        
        # Clear existing cameras first (optional)
        # self._on_clear_all()
        
        # Add each camera from preset
        cameras_added = 0
        cameras_failed = 0
        
        for camera_config in preset_data.get('cameras', []):
            camera_path = camera_config.get('camera_path')
            capture_mode = camera_config.get('capture_mode', 'LOCAL')

            # Prepare config based on mode
            if capture_mode == 'LOCAL':
                output_or_config = camera_config.get('output_dir', '/home/netai/Documents/traffic_captures')
            elif capture_mode == 'KAFKA':
                broker = camera_config.get('kafka_broker', 'localhost:9092')
                topic = camera_config.get('kafka_topic', '')
                output_or_config = f"{broker}|{topic}" if topic else broker
            else:
                output_or_config = camera_config.get('output_dir', '/home/netai/Documents/traffic_captures')
            
            print(f"[Info] Processing camera from preset: {camera_path} (mode: {capture_mode})")
            
            # Validate camera
            is_valid, error_msg = CameraValidator.validate_camera(
                self.stage, 
                camera_path, 
                self.capture_manager.cameras
            )
            
            if is_valid:
                # Get camera ID
                temp_id = self.capture_manager._next_camera_id
                
                # Create panel with capture mode
                ui_refs = self.ui.add_camera_panel(
                    temp_id, 
                    camera_path, 
                    output_or_config, 
                    capture_mode=capture_mode
                )
                
                if ui_refs:
                    self.capture_manager.add_camera(camera_path, output_or_config, ui_refs, capture_mode)
                    
                    # Apply preset settings to UI models if provided
                    if 'resolution' in camera_config and len(camera_config['resolution']) == 2:
                        ui_refs["resolution_x_model"].set_value(camera_config['resolution'][0])
                        ui_refs["resolution_y_model"].set_value(camera_config['resolution'][1])
                        print(f"  - Set resolution: {camera_config['resolution']}")
                    
                    if 'interval' in camera_config:
                        ui_refs["interval_model"].set_value(float(camera_config['interval']))
                        print(f"  - Set interval: {camera_config['interval']}s")
                    
                    if 'frame_count' in camera_config:
                        ui_refs["frame_count_model"].set_value(int(camera_config['frame_count']))
                        print(f"  - Set frame count: {camera_config['frame_count']}")
                    
                    cameras_added += 1
                    print(f"[Info] Successfully added camera: {camera_path}")
            else:
                print(f"[Warning] Failed to add camera '{camera_path}': {error_msg}")
                cameras_failed += 1
    
        print(f"[Info] Preset loaded: {cameras_added} cameras added, {cameras_failed} failed")

    def _on_save_preset(self, preset_path: str):
        """Save current cameras to preset file"""
        cameras = []
        for camera_path, camera_info in self.capture_manager.cameras.items():
            # Get panel to determine capture mode
            panel = self.ui.get_panel(camera_path)
            capture_mode = camera_info.get("capture_mode", "LOCAL")
            if panel:
                capture_mode = panel.get_capture_mode()
            
            camera_entry = {
                "camera_path": camera_path,
                "capture_mode": capture_mode,
                "resolution": [
                    camera_info["resolution_x_model"].as_int,
                    camera_info["resolution_y_model"].as_int
                ],
                "interval": camera_info["interval_model"].as_float,
                "frame_count": camera_info["frame_count_model"].as_int
            }
            
            # Add mode-specific configuration
            if capture_mode == "LOCAL":
                camera_entry["output_dir"] = camera_info.get("output_dir", "")
            elif capture_mode == "KAFKA":
                kafka_config = camera_info.get("kafka_config", {})
                camera_entry["kafka_broker"] = kafka_config.get("broker", "localhost:9092")
                camera_entry["kafka_topic"] = kafka_config.get("topic", "")
            
            cameras.append(camera_entry)
        
        if PresetLoader.save_preset(cameras, preset_path):
            print(f"[Info] Saved {len(cameras)} cameras to preset")