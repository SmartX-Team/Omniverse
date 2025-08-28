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
    
    def add_camera(self, camera_path: str, output_or_config: str, ui_refs: dict, capture_mode: str = "LOCAL") -> int:
        """
        Add a camera to management
        
        Returns:
            Camera ID
        """
        camera_id = self._next_camera_id
        self._next_camera_id += 1

        # Parse configuration based on capture mode
        if capture_mode == "LOCAL":
            output_dir = output_or_config
            kafka_config = None
        elif capture_mode == "KAFKA":
            output_dir = None  # Not used for Kafka mode
            # Parse Kafka configuration
            if "|" in output_or_config:
                broker, topic = output_or_config.split("|", 1)
            else:
                broker = output_or_config
                topic = f"camera_{camera_id}"
            kafka_config = {
                "broker": broker,
                "topic": topic
            }
        else:
            # Default to LOCAL
            output_dir = output_or_config
            kafka_config = None
            capture_mode = "LOCAL"



        camera_info = {
            "path": camera_path,
            "camera_id": camera_id,
            "capture_mode": capture_mode,
            "output_dir": output_dir,
            "kafka_config": kafka_config,
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
        capture_mode = camera_info.get("capture_mode", "LOCAL")
        
        # Writer 정리 - flush 대기 추가
        if capture_mode == "LOCAL" and camera_info.get("writer"):
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
                # WriterRegistry에서도 제거 시도
                try:
                    if hasattr(rep.WriterRegistry, '_writers'):
                        for key in list(rep.WriterRegistry._writers.keys()):
                            if rep.WriterRegistry._writers[key] == writer:
                                del rep.WriterRegistry._writers[key]
                except:
                    pass
                
                camera_info["writer"] = None
                del writer

                print(f"[Info] Writer detached for camera {camera_id}")
            except Exception as e:
                print(f"[Warning] Failed to clean up writer: {e}")
        
        # Render product 정리
        if camera_info.get("render_product"):
            try:
                rp = camera_info["render_product"]

                # Annotator 연결 해제
                try:
                    import omni.syntheticdata as sd
                    sd._sensor_helpers.remove_sensor(str(rp))
                except:
                    pass


                camera_info["render_product"] = None
                del rp
                print(f"[Info] Render product cleaned for camera {camera_id}")
            except Exception as e:
                print(f"[Warning] Failed to clean up render product: {e}")
        
        # Active writers 리스트에서도 제거
        if capture_mode == "LOCAL" and hasattr(self, '_active_writers'):
            self._active_writers = [w for w in self._active_writers 
                                if w.get('camera_id') != camera_id]
    
    def _create_render_product(self, camera_path: str, camera_id: int, resolution: tuple):
        """Create render product and writer for off-screen capture"""
        try:
            self._cleanup_writer_by_id(camera_id)
            
            # 현재 카메라 정보 가져오기
            camera_info = self.cameras.get(camera_path)
            if not camera_info:
                print(f"[ERROR] Camera info not found for {camera_path}")
                return None, None
                
            capture_mode = camera_info.get("capture_mode", "LOCAL")
            print(f"[Info] Creating render product for camera {camera_id} in {capture_mode} mode")
            
            rp = rep.create.render_product(
                camera_path, 
                resolution=resolution
            )
            
            # LOCAL 모드에서만 BasicWriter 생성
            if capture_mode == "LOCAL":
                if not camera_info.get("output_dir"):
                    print(f"[ERROR] No output_dir specified for LOCAL mode camera {camera_id}")
                    return rp, None
                    
                # Writer 생성
                writer = rep.WriterRegistry.get("BasicWriter")
                
                # 각 카메라별 고유 출력 디렉토리
                camera_name = camera_path.split('/')[-1]
                output_subdir = os.path.join(
                    camera_info["output_dir"],
                    f"camera_{camera_id}_{camera_name}"
                )
                os.makedirs(output_subdir, exist_ok=True)
                
                # Writer 초기화
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
                
                print(f"[Info] Created render product with BasicWriter for LOCAL camera {camera_id}")
                return rp, writer
                
            elif capture_mode == "KAFKA":
                # Kafka 모드에서는 writer 없이 render product만 생성
                kafka_config = camera_info.get("kafka_config", {})
                print(f"[Info] Created render product for KAFKA camera {camera_id}")
                print(f"  - Broker: {kafka_config.get('broker')}")
                print(f"  - Topic: {kafka_config.get('topic')}")
                return rp, None
            else:
                print(f"[ERROR] Unknown capture mode: {capture_mode}")
                return rp, None
            
        except Exception as e:
            print(f"[ERROR] Failed to create render product for camera {camera_id}: {e}")
            import traceback
            traceback.print_exc()
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
        Capture a single frame from camera with metadata
        
        Args:
            pause_sim: True for single capture (stops sim), False for periodic (no stop)
        """
        camera_info = self.cameras.get(camera_path)
        if not camera_info:
            return False

        camera_id = camera_info["camera_id"]
        capture_mode = camera_info.get("capture_mode", "LOCAL")
        
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
            if not rp:  # render product는 필수, writer는 LOCAL 모드에서만 필요
                return False
            
            camera_info["render_product"] = rp
            camera_info["writer"] = writer  # KAFKA 모드에서는 None일 수 있음
            camera_info["last_resolution"] = resolution
        
        try:
            # KAFKA 모드에서 이미지 데이터 추출 및 전송
            if capture_mode == "KAFKA":
                # 먼저 프레임 캡처
                await rep.orchestrator.step_async(pause_timeline=pause_sim)
                
                # 이미지 데이터 추출
                import omni.syntheticdata as sd
                import numpy as np
                from PIL import Image
                import io
                
                try:
                    # render product에서 RGB 데이터 가져오기
                    rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb", device="cpu")
                    rgb_annotator.attach([camera_info["render_product"]])
                    
                    # 데이터 대기
                    await rep.orchestrator.step_async(pause_timeline=False)
                    
                    # RGB 데이터 가져오기
                    rgb_data = rgb_annotator.get_data()
                    
                    if rgb_data is not None and len(rgb_data) > 0:
                        # RGB 데이터 처리
                        if isinstance(rgb_data, dict):
                            image_data = rgb_data.get("data", rgb_data.get("rgb", None))
                        else:
                            image_data = rgb_data
                        
                        if image_data is not None:
                            # NumPy array로 변환
                            if not isinstance(image_data, np.ndarray):
                                image_data = np.array(image_data)
                            
                            # RGBA to RGB 변환 (4채널인 경우)
                            if len(image_data.shape) == 3 and image_data.shape[2] == 4:
                                image_data = image_data[:, :, :3]
                            
                            # uint8로 변환
                            if image_data.dtype != np.uint8:
                                image_data = (image_data * 255).astype(np.uint8)
                            
                            # PIL Image로 변환
                            image = Image.fromarray(image_data)
                            
                            # JPEG로 압축
                            buffer = io.BytesIO()
                            image.save(buffer, format='JPEG', quality=85)
                            image_bytes = buffer.getvalue()
                            
                            # 카메라 메타데이터 추출
                            camera_metadata = self.get_camera_metadata(camera_path, resolution)
                            
                            # Kafka로 전송
                            kafka_config = camera_info.get("kafka_config", {})
                            broker = kafka_config.get("broker", "localhost:9092")
                            topic = kafka_config.get("topic", f"camera_{camera_id}")
                            
                            # Kafka handler 초기화 (필요시)
                            if not hasattr(self, 'kafka_handlers'):
                                self.kafka_handlers = {}
                            
                            if camera_id not in self.kafka_handlers:
                                from ..utils.kafka_handler import KafkaHandler
                                handler = KafkaHandler()
                                success, msg = await handler.connect(broker)
                                if success:
                                    self.kafka_handlers[camera_id] = handler
                                    print(f"[Info] Connected to Kafka broker: {broker}")
                                else:
                                    print(f"[Error] Failed to connect to Kafka: {msg}")
                                    if camera_info.get("status_label"):
                                        camera_info["status_label"].text = f"Kafka connection failed: {msg}"
                                    return False
                            
                            handler = self.kafka_handlers.get(camera_id)
                            if handler:
                                # 메타데이터와 함께 이미지 전송
                                import base64
                                
                                message = {
                                    # Frame identification
                                    "frame_id": f"frame_{int(datetime.now().timestamp() * 1000)}",
                                    "camera_id": camera_id,
                                    "camera_name": f"cam{camera_id}",
                                    "camera_path": camera_path,
                                    "timestamp": datetime.now().isoformat(),
                                    "timestamp_ms": int(datetime.now().timestamp() * 1000),
                                    
                                    # Camera calibration
                                    "intrinsics": {
                                        "K": camera_metadata["K"],  # 3x3 matrix
                                        "distortion": camera_metadata["distortion"],  # [0,0,0,0,0]
                                        "image_size": camera_metadata["image_size"],  # [width, height]
                                        "focal_length": camera_metadata["focal_length"],
                                        "sensor_size": camera_metadata["sensor_size"]
                                    },
                                    
                                    # Camera pose
                                    "extrinsics": {
                                        "R": camera_metadata["R"],  # 3x3 rotation matrix
                                        "t": camera_metadata["t"],  # 3x1 translation vector
                                        "T_world_cam": camera_metadata["T_world_cam"]  # Full 4x4 transform
                                    },
                                    
                                    # Image data
                                    "image": {
                                        "format": "jpeg",
                                        "quality": 85,
                                        "size": len(image_bytes),
                                        "width": resolution[0],
                                        "height": resolution[1],
                                        "data": base64.b64encode(image_bytes).decode('utf-8')
                                    }
                                }
                                
                                # KafkaHandler의 send_message 사용 (value_serializer가 처리)
                                try:
                                    success = await handler.send_message(
                                        topic=topic,
                                        message=message,
                                        key=f"cam{camera_id}"
                                    )
                                    if success:
                                        print(f"[Info] Sent frame with metadata to topic '{topic}' - Camera {camera_id} (size: {len(image_bytes)} bytes)")
                                    else:
                                        print(f"[Error] Failed to send frame to Kafka topic '{topic}'")
                                except Exception as e:
                                    print(f"[Error] Failed to send to Kafka: {e}")
                            
                            # annotator 정리
                            rgb_annotator.detach()
                        else:
                            print(f"[Warning] No valid image data received for camera {camera_id}")
                    else:
                        print(f"[Warning] No RGB data available for camera {camera_id}")
                        
                except Exception as e:
                    print(f"[Error] Kafka streaming failed for camera {camera_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    
            else:  # LOCAL mode
                # 기존 방식대로 BasicWriter가 파일로 저장
                await rep.orchestrator.step_async(pause_timeline=pause_sim)

                # 메타데이터 추출 및 저장 추가
                if camera_info.get("output_dir"):
                    camera_metadata = self.get_camera_metadata(camera_path, resolution)
                    
                    # 메타데이터 JSON 파일 저장
                    import json
                    camera_name = camera_path.split('/')[-1]
                    output_subdir = os.path.join(
                        camera_info["output_dir"],
                        f"camera_{camera_id}_{camera_name}"
                    )
                    
                    # 프레임별 메타데이터 파일
                    frame_num = camera_info["frame_counter"]
                    metadata_file = os.path.join(
                        output_subdir, 
                        f"frame_{frame_num:06d}_metadata.json"
                    )
                    
                    metadata_with_frame = {
                        "frame_number": frame_num,
                        "timestamp": datetime.now().isoformat(),
                        **camera_metadata
                    }
                    
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata_with_frame, f, indent=2)
            
            # 공통 처리
            camera_info["frame_counter"] += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            if camera_info.get("progress_label"):
                camera_info["progress_label"].text = f"Captured frame {camera_info['frame_counter']} at {timestamp}"
            
            mode_str = f" ({capture_mode} mode)" if capture_mode == "KAFKA" else ""
            print(f"[Debug] Frame {camera_info['frame_counter']} captured at {timestamp}{mode_str}")
            
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
        capture_mode = camera_info.get("capture_mode", "LOCAL")


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
        if capture_mode == "LOCAL" and camera_info.get("writer"):
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
        
        # Active writers 리스트에서 제거 (LOCAL 모드만)
        if capture_mode == "LOCAL" and hasattr(self, '_active_writers'):
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
        time.sleep(0.2)

        for camera_path in list(self.cameras.keys()):
            camera_info = self.cameras[camera_path]
            self._cleanup_render_product(camera_info)

        # 추적된 모든 writer 정리
        for item in self._active_writers[:]:
            try:
                item['writer'].detach()
            except:
                pass
        self._active_writers.clear()
        
        # 4. Kafka handlers 정리
        if hasattr(self, 'kafka_handlers'):
            for handler in self.kafka_handlers.values():
                try:
                    asyncio.create_task(handler.disconnect())
                except:
                    pass
            self.kafka_handlers.clear()
        
        self.cameras.clear()
        
        # 강제 가비지 컬렉션
        import gc
        gc.collect()

        # Kafka handlers 정리
        if hasattr(self, 'kafka_handlers'):
            for handler in self.kafka_handlers.values():
                asyncio.create_task(handler.disconnect())
            self.kafka_handlers.clear()        

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


    def get_camera_metadata(self, camera_path: str, resolution: tuple) -> dict:
            """
            Extract camera intrinsic and extrinsic parameters from USD
            """
            import numpy as np
            from pxr import UsdGeom, Gf
            
            camera_prim = self.stage.GetPrimAtPath(camera_path)
            if not camera_prim:
                return None
            
            camera = UsdGeom.Camera(camera_prim)
            
            # Get intrinsic parameters (기본값 처리 포함)
            focal_length = camera.GetFocalLengthAttr().Get()
            h_aperture = camera.GetHorizontalApertureAttr().Get()
            v_aperture = camera.GetVerticalApertureAttr().Get()
            
            # USD 기본값 사용 (없으면)
            if not focal_length:
                focal_length = 18.14756
            if not h_aperture:
                h_aperture = 20.955
            if not v_aperture:
                v_aperture = 15.2908
            
            width, height = resolution
            
            # Calculate intrinsic matrix K
            fx = focal_length * width / h_aperture
            fy = focal_length * height / v_aperture
            cx = width / 2.0
            cy = height / 2.0
            
            K = np.array([
                [fx, 0,  cx],
                [0,  fy, cy],
                [0,  0,  1]
            ])
            
            # Get extrinsic parameters (world transform)
            xform = UsdGeom.Xformable(camera_prim)
            world_transform = xform.ComputeLocalToWorldTransform(0)
            
            # Convert to 4x4 matrix
            T_world_cam = np.array(world_transform).reshape(4, 4)
            
            # Extract rotation (R) and translation (t)
            R = T_world_cam[:3, :3]
            t = T_world_cam[:3, 3]
            
            # Camera looks down -Z in USD, convert to OpenCV convention (Z forward)
            flip = np.array([
                [1, 0, 0],
                [0, -1, 0],
                [0, 0, -1]
            ])
            R = R @ flip
            
            return {
                "camera_path": camera_path,
                "K": K.tolist(),  # 3x3 intrinsic matrix
                "distortion": [0, 0, 0, 0, 0],  # No distortion in USD
                "R": R.tolist(),  # 3x3 rotation matrix
                "t": t.tolist(),  # 3x1 translation vector
                "T_world_cam": T_world_cam.tolist(),  # Full 4x4 transform
                "image_size": [width, height],
                "focal_length": focal_length,
                "sensor_size": [h_aperture, v_aperture]
            }

    def export_rig_config(self, output_path: str = "rig.json"):
        """
        Export all camera configurations to a rig file
        """
        import json
        
        rig_data = {
            "timestamp": datetime.now().isoformat(),
            "frame_id": "world",
            "cameras": []
        }
        
        for camera_path in self.cameras.keys():
            metadata = self.get_camera_metadata(camera_path)
            if metadata:
                # Add camera index/name
                camera_info = self.cameras[camera_path]
                metadata["camera_id"] = camera_info["camera_id"]
                metadata["camera_name"] = f"cam{camera_info['camera_id']}"
                rig_data["cameras"].append(metadata)
        
        with open(output_path, 'w') as f:
            json.dump(rig_data, f, indent=2)
        
        print(f"[Info] Exported camera rig to {output_path}")
        return rig_data