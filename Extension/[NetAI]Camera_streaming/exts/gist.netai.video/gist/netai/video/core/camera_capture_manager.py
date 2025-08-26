# camera_capture_manager.py
"""Business logic for camera capture operations


1.1.0 에서 기존 메인 Extension은 분리되어 탄생함; 어차피 리팩토링은 클로드 4.1이 해줌 -Inyong Song

"""

import os
import asyncio
from datetime import datetime
from typing import Dict, Optional, Tuple
import omni.replicator.core as rep
import time

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
        camera_id = camera_info.get("camera_id")
        
        # Stop any ongoing capture
        if camera_info.get("capture_task"):
            camera_info["stop_requested"] = True
            if camera_info["capture_task"]:
                camera_info["capture_task"].cancel()
                camera_info["capture_task"] = None
        
        # Clean up render product and writer
        self._cleanup_render_product(camera_info)
        
        del self.cameras[camera_path]
        # 가비지 컬렉션 강제 실행
        import gc
        gc.collect()        
        print(f"[Info] Camera removed. Remaining: {len(self.cameras)} cameras")
    
    def _cleanup_render_product(self, camera_info: dict):
        """Clean up render product"""
        camera_id = camera_info.get("camera_id")
        
        # Writer 정리 - flush 대기 추가
        if camera_info.get("writer"):
            try:
                writer = camera_info["writer"]
                
                # 모든 프레임이 기록될 때까지 대기
                max_wait = 30  # 최대 3초 대기
                while max_wait > 0:
                    pending = rep.orchestrator.get_sim_times_to_write()
                    if not pending:
                        break
                    time.sleep(0.1)
                    max_wait -= 1
                
                writer.detach()
                camera_info["writer"] = None
                print(f"[Info] Writer detached for camera {camera_id}")
            except Exception as e:
                print(f"[Warning] Failed to clean up writer: {e}")
        
        # Render product 정리
        if camera_info.get("render_product"):
            try:
                rp = camera_info["render_product"]
                del rp
                camera_info["render_product"] = None
                print(f"[Info] Render product cleaned for camera {camera_id}")
            except Exception as e:
                print(f"[Warning] Failed to clean up render product: {e}")
        
        # Active writers 리스트에서도 제거
        if hasattr(self, '_active_writers'):
            self._active_writers = [w for w in self._active_writers 
                                if w.get('camera_id') != camera_id]
    
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

    async def capture_single_frame(self, camera_path: str, pause_sim: bool = True) -> bool:
        """
        Capture a single frame from camera
        
        Args:
            use_orchestrator: True for single capture (stops sim), False for periodic (no stop)
        """
        camera_info = self.cameras.get(camera_path)
        if not camera_info:
            return False

        camera_id = camera_info["camera_id"]
        
        # Get resolution from UI models
        resolution = (
            camera_info["resolution_x_model"].as_int,
            camera_info["resolution_y_model"].as_int
        )
        
        # Check if render product exists or resolution changed
        if not camera_info["render_product"] or camera_info.get("last_resolution") != resolution:
            if camera_info["render_product"] and camera_info.get("last_resolution") != resolution:
                print(f"[Info] Resolution changed for camera {camera_id}, recreating render product")
                self._cleanup_render_product(camera_info)
            
            rp, writer = self._create_render_product(camera_path, camera_id, resolution)
            if not rp or not writer:
                return False
            
            camera_info["render_product"] = rp
            camera_info["writer"] = writer
            camera_info["last_resolution"] = resolution
        
        try:
            # pause_timeline 파라미터로 시뮬레이션 중단 여부 제어
            await rep.orchestrator.step_async(pause_timeline=pause_sim)
            
            camera_info["frame_counter"] += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            if camera_info.get("progress_label"):
                camera_info["progress_label"].text = f"Captured frame {camera_info['frame_counter']} at {timestamp}"
            
            print(f"[Debug] Frame {camera_info['frame_counter']} captured at {timestamp}")
            
            return True
        except Exception as e:
            print(f"[ERROR] Capture failed for camera {camera_id}: {e}")
            if camera_info.get("status_label"):
                camera_info["status_label"].text = f"Error: {str(e)}"
            return False
    
    async def capture_periodic_task(self, camera_path: str):
        """Execute periodic capture task with proper timing"""
        camera_info = self.cameras.get(camera_path)
        if not camera_info:
            return
        
        interval = camera_info["interval_model"].as_float
        total_frames = camera_info["frame_count_model"].as_int
        
        print(f"[Info] Starting periodic capture: {total_frames} frames with {interval}s interval")
        
        if camera_info.get("status_label"):
            camera_info["status_label"].text = f"Capturing: 0/{total_frames}"
        
        frames_captured = 0
        
        for i in range(total_frames):
            if camera_info.get("stop_requested"):
                print(f"[Info] Capture stopped by user at frame {i}/{total_frames}")
                break
            
            # pause_sim=False로 시뮬레이션 안 멈추고 캡처
            success = await self.capture_single_frame(camera_path, pause_sim=False)
            
            if success:
                frames_captured += 1
                if camera_info.get("status_label"):
                    camera_info["status_label"].text = f"Capturing: {frames_captured}/{total_frames}"
            
            # stop 체크를 interval 대기 중에도
            if i < total_frames - 1:
                # interval을 작은 단위로 나눠서 체크
                interval_steps = int(interval * 10)  # 100ms 단위로 체크
                for _ in range(interval_steps):
                    if camera_info.get("stop_requested"):
                        break
                    await asyncio.sleep(0.1)
        
        # 태스크 종료 처리
        if not camera_info.get("stop_requested"):
            # 정상 완료
            if camera_info.get("status_label"):
                camera_info["status_label"].text = f"Complete: {frames_captured} frames captured"
        # stop_requested인 경우는 stop_capture에서 이미 처리
        
        camera_info["capture_task"] = None
        
        print(f"[Info] Periodic capture ended: {frames_captured} frames")
    
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
        
        camera_id = camera_info.get("camera_id")

        # 진행 중인 태스크가 없으면 바로 리턴
        if not camera_info.get("capture_task"):
            if camera_info.get("status_label"):
                camera_info["status_label"].text = "No active capture"
            return
        
        print(f"[Info] Stopping capture for camera {camera_id}")
        
        # 1. stop 플래그 설정
        camera_info["stop_requested"] = True
        
        # 2. 상태 업데이트
        if camera_info.get("status_label"):
            camera_info["status_label"].text = "Stopping..."
        
        # 3. 태스크 취소
        try:
            if camera_info["capture_task"]:
                camera_info["capture_task"].cancel()
        except:
            pass
        finally:
            camera_info["capture_task"] = None
        
        # 4. Writer와 Render Product 정리 칵
        print(f"[Info] Cleaning up resources for camera {camera_id}")
        
        # Writer flush 및 정리
        if camera_info.get("writer"):
            try:
                writer = camera_info["writer"]
                
                # 펜딩 프레임 대기
                import time
                max_wait = 20  # 2초 대기
                while max_wait > 0:
                    pending = rep.orchestrator.get_sim_times_to_write()
                    if not pending:
                        break
                    time.sleep(0.1)
                    max_wait -= 1
                
                writer.detach()
                camera_info["writer"] = None
                print(f"[Info] Writer stopped and detached for camera {camera_id}")
            except Exception as e:
                print(f"[Warning] Error stopping writer: {e}")
        
        # Render product 정리
        if camera_info.get("render_product"):
            try:
                rp = camera_info["render_product"]
                del rp
                camera_info["render_product"] = None
                print(f"[Info] Render product removed for camera {camera_id}")
            except Exception as e:
                print(f"[Warning] Error removing render product: {e}")
        
        # Active writers 리스트에서 제거
        if hasattr(self, '_active_writers'):
            self._active_writers = [w for w in self._active_writers 
                                if w.get('camera_id') != camera_id]
        
        # 상태 업데이트
        if camera_info.get("status_label"):
            camera_info["status_label"].text = "Stopped - Ready"
        
        # stop_requested 플래그 리셋
        camera_info["stop_requested"] = False
        
        print(f"[Info] Capture stopped for camera {camera_id}. Writer/RP cleaned.")
    
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