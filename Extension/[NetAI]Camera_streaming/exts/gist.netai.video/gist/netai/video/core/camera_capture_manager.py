# camera_capture_manager.py
"""Business logic for camera capture operations


1.1.0 에서 기존 메인 Extension은 분리되어 탄생함; 어차피 리팩토링은 클로드 4.1이 해줌 -Inyong Song

"""

import os
import asyncio
from datetime import datetime
from typing import Dict, Optional, Tuple
import omni.replicator.core as rep

class CameraCaptureManager:
    """Manages camera capture operations"""
    
    def __init__(self, stage):
        """
        Initialize capture manager
        
        Args:
            stage: USD stage reference
        """
        self.stage = stage
        self.cameras = {}  # Store camera information
        self._next_camera_id = 0
        self._active_writers = []
        
        # Initialize replicator orchestrator ; 1.2.0 때 새로 생성한 함수 
        self._force_cleanup_all()

        # Orchestrator 재초기화 ; 1.2.0 때 새로 생성한 함수 
        self._reinitialize_orchestrator()
    
    def validate_camera(self, camera_path: str) -> Tuple[bool, str]:
        """
        Validate if camera exists and is valid
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not camera_path:
            return False, "Camera path cannot be empty."
        
        if not camera_path.startswith("/"):
            return False, f"Invalid path format: '{camera_path}'."
        
        if camera_path in self.cameras:
            return False, f"Camera '{camera_path}' is already managed."
        
        if not self.stage:
            return False, "USD Stage is not available."
        
        try:
            camera_prim = self.stage.GetPrimAtPath(camera_path)
            if not camera_prim or not camera_prim.IsValid():
                return False, f"Camera prim not found at path: '{camera_path}'."
            if camera_prim.GetTypeName() != "Camera":
                return False, f"Prim at '{camera_path}' is not a Camera."
        except Exception as e:
            return False, f"Error validating camera path '{camera_path}': {e}"
        
        return True, ""
    
    def add_camera(self, camera_path: str, output_dir: str, ui_refs: dict) -> int:
        """
        Add a camera to management
        
        Returns:
            Camera ID
        """
        camera_id = self._next_camera_id
        self._next_camera_id += 1
        
        camera_info = {
            "path": camera_path,
            "camera_id": camera_id,
            "output_dir": output_dir,
            "render_product": None,
            "writer": None,
            "last_resolution": None,
            "capture_task": None,
            "frame_counter": 0,
            "stop_requested": False,
            **ui_refs  # Include UI models and references
        }
        
        self.cameras[camera_path] = camera_info
        print(f"[Info] Camera added - ID: {camera_id}, Path: {camera_path}")
        return camera_id
    
    def remove_camera(self, camera_path: str):
        """Remove camera from management"""
        if camera_path not in self.cameras:
            return
        
        camera_info = self.cameras[camera_path]
        
        # Stop any ongoing capture
        if camera_info.get("capture_task"):
            camera_info["stop_requested"] = True
        
        # Clean up render product and writer
        self._cleanup_render_product(camera_info)
        
        del self.cameras[camera_path]
        print(f"[Info] Camera removed. Remaining: {len(self.cameras)} cameras")
    
    def _cleanup_render_product(self, camera_info: dict):
        """Clean up render product"""
        # Writer 정리
        if camera_info.get("writer"):
            try:
                # detach는 필요 없을 수 있음
                camera_info["writer"] = None
            except Exception as e:
                print(f"[Warning] Failed to clean up writer: {e}")
        
        # Render product 정리
        if camera_info.get("render_product"):
            try:
                camera_info["render_product"] = None
            except Exception as e:
                print(f"[Warning] Failed to clean up render product: {e}")
    
    def _create_render_product(self, camera_path: str, camera_id: int, resolution: tuple):
        """Create render product and writer for off-screen capture"""
        try:
            self._cleanup_writer_by_id(camera_id)

            rp = rep.create.render_product(
                camera_path, 
                resolution=resolution
            )
            
            # Writer 생성
            writer = rep.WriterRegistry.get("BasicWriter")
            
            # 각 카메라별 고유 출력 디렉토리
            camera_name = camera_path.split('/')[-1]
            output_subdir = os.path.join(
                self.cameras[camera_path]["output_dir"],
                f"camera_{camera_id}_{camera_name}"
            )
            os.makedirs(output_subdir, exist_ok=True)
            
            # Writer 초기화 - 고유 이름 없이
            writer.initialize(
                output_dir=output_subdir,
                rgb=True,
                colorize_instance_segmentation=False,
                colorize_semantic_segmentation=False
            )
            writer.attach([rp])

            self._active_writers.append({
                'camera_id': camera_id,
                'writer': writer,
                'render_product': rp
            })

            print(f"[Info] Created render product for camera {camera_id}")
            return rp, writer
            
        except Exception as e:
            print(f"[ERROR] Failed to create render product for camera {camera_id}: {e}")
            import traceback
            traceback.print_exc()  # 전체 에러 스택 출력
            return None, None

    def _cleanup_writer_by_id(self, camera_id: int):
        """Clean up specific writer by camera ID"""
        for item in self._active_writers[:]:
            if item['camera_id'] == camera_id:
                try:
                    item['writer'].detach()
                    self._active_writers.remove(item)
                    print(f"[Info] Cleaned up writer for camera {camera_id}")
                except:
                    pass

    async def capture_single_frame(self, camera_path: str) -> bool:
        """
        Capture a single frame from camera
        
        Returns:
            Success status
        """
        camera_info = self.cameras.get(camera_path)
        if not camera_info:
            return False
        
        camera_id = camera_info["camera_id"]
        print(f"[Debug] Capturing from camera {camera_id}: {camera_path}")
        
        # Get resolution from UI models
        resolution = (
            camera_info["resolution_x_model"].as_int,
            camera_info["resolution_y_model"].as_int
        )
        
        # Check if render product exists or resolution changed
        if not camera_info["render_product"] or camera_info.get("last_resolution") != resolution:
            # Clean up old render product if resolution changed
            if camera_info["render_product"] and camera_info.get("last_resolution") != resolution:
                print(f"[Info] Resolution changed for camera {camera_info['camera_id']}, recreating render product")
                self._cleanup_render_product(camera_info)
            
            # Create new render product and writer
            rp, writer = self._create_render_product(
                camera_path, 
                camera_info["camera_id"], 
                resolution
            )
            if not rp or not writer:
                return False
            
            camera_info["render_product"] = rp
            camera_info["writer"] = writer
            camera_info["last_resolution"] = resolution
        
        try:
            # Capture frame using existing writer
            await rep.orchestrator.step_async()
            
            camera_info["frame_counter"] += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Update progress through UI reference
            if camera_info.get("progress_label"):
                camera_info["progress_label"].text = f"Captured frame {camera_info['frame_counter']} at {timestamp}"
            
            return True
        except Exception as e:
            print(f"[ERROR] Capture failed for camera {camera_info['camera_id']}: {e}")
            if camera_info.get("status_label"):
                camera_info["status_label"].text = f"Error: {str(e)}"
            return False
    
    async def capture_periodic_task(self, camera_path: str):
        """Execute periodic capture task"""
        camera_info = self.cameras.get(camera_path)
        if not camera_info:
            return
        
        interval = camera_info["interval_model"].as_float
        total_frames = camera_info["frame_count_model"].as_int
        
        if camera_info.get("status_label"):
            camera_info["status_label"].text = f"Capturing: 0/{total_frames}"
        
        for i in range(total_frames):
            if camera_info.get("stop_requested"):
                break
            
            await self.capture_single_frame(camera_path)
            
            if camera_info.get("status_label"):
                camera_info["status_label"].text = f"Capturing: {i+1}/{total_frames}"
            
            if i < total_frames - 1:
                await asyncio.sleep(interval)
        
        # Update final status
        if camera_info.get("status_label"):
            if not camera_info.get("stop_requested"):
                camera_info["status_label"].text = f"Complete: {camera_info['frame_counter']} frames captured"
            else:
                camera_info["status_label"].text = f"Stopped: {camera_info['frame_counter']} frames captured"
        
        camera_info["capture_task"] = None
        camera_info["stop_requested"] = False
    
    def start_periodic_capture(self, camera_path: str):
        """Start periodic capture for a camera"""
        camera_info = self.cameras.get(camera_path)
        if not camera_info:
            return
        
        if camera_info["capture_task"]:
            print(f"[Warning] Capture already in progress for camera {camera_info['camera_id']}")
            return
        
        camera_info["stop_requested"] = False
        camera_info["capture_task"] = asyncio.ensure_future(
            self.capture_periodic_task(camera_path)
        )
    
    def stop_capture(self, camera_path: str):
        """Stop ongoing capture for a camera"""
        camera_info = self.cameras.get(camera_path)
        if not camera_info:
            return
        
        if camera_info["capture_task"]:
            camera_info["stop_requested"] = True
            if camera_info.get("status_label"):
                camera_info["status_label"].text = "Stopping..."
        elif camera_info.get("status_label"):
            camera_info["status_label"].text = "No active capture"
    
    def stop_all_captures(self):
        """Stop all ongoing captures"""
        for camera_path, camera_info in self.cameras.items():
            if camera_info.get("capture_task"):
                camera_info["stop_requested"] = True
                if camera_info.get("status_label"):
                    camera_info["status_label"].text = "Stopped"
    
    def cleanup(self):
        """Cleanup all resources"""
        self.stop_all_captures()
        
        # 추적된 모든 writer 정리
        for item in self._active_writers[:]:
            try:
                item['writer'].detach()
            except:
                pass
        self._active_writers.clear()
        
        # 카메라별 정리
        for camera_info in self.cameras.values():
            self._cleanup_render_product(camera_info)
        
        self.cameras.clear()
        
        # 강제 가비지 컬렉션
        import gc
        gc.collect()

    def _force_cleanup_all(self):
        """Force cleanup all replicator components"""
        try:
            # 모든 비동기 태스크 취소
            for task in asyncio.all_tasks():
                if hasattr(task, '_coro') and 'capture' in str(task._coro):
                    task.cancel()
                    
            # Syntheticdata 센서 정리
            try:
                import omni.syntheticdata as sd
                if hasattr(sd, '_sensor_helpers'):
                    sd._sensor_helpers.clear_all_sensors()
            except:
                pass
            
            # 메모리 강제 정리
            import gc
            gc.collect()
            
        except Exception as e:
            print(f"[Warning] Force cleanup error: {e}")


    def _reinitialize_orchestrator(self):
        """Reinitialize orchestrator safely"""
        try:
            # 기존 orchestrator 정지
            if rep.orchestrator.get_is_started():
                rep.orchestrator.stop()
                asyncio.sleep(0.2)
            
            # 새로 시작
            rep.orchestrator.run()
            print("[Info] Orchestrator reinitialized")
        except Exception as e:
            print(f"[Warning] Orchestrator reinit error: {e}")