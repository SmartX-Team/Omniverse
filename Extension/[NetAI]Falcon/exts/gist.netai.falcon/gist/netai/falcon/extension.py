import omni.ext
import omni.ui as ui
from omni.usd import get_context, StageEventType
from pxr import Usd, UsdGeom, Sdf, Gf

import asyncio
import json
from aiokafka import AIOKafkaConsumer
import logging
import weakref
import threading
from typing import Optional, List, Dict, Any

# --- Configuration ---
KAFKA_BROKER = '10.79.1.1:9094'
KAFKA_TOPIC = 'inference_results'
KAFKA_GROUP_ID = 'omniverse_falcon_human_visualizer_group'

# 사용할 사람 Prim 경로 목록
PERSON_PRIM_PATHS = [
    "/World/human/human_01",
    "/World/human/human_02",
    "/World/human/human_03"
]
MAX_PERSONS_TO_DISPLAY = len(PERSON_PRIM_PATHS)

PERSON_PRIM_FIXED_Y_HEIGHT = 90.0
PERSON_PRIM_SCALE = 100.0

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class FalconHumanVisualizerExtension(omni.ext.IExt):
    def on_startup(self, ext_id: str):
        logger.info(f"FalconHumanVisualizerExtension startup. Ext ID: {ext_id}")
        
        # 초기화 시 모든 속성을 None으로 설정
        self._ext_id: Optional[str] = ext_id
        self._consumer_task: Optional[asyncio.Task] = None
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._person_prim_objects: List[Dict[str, Any]] = []
        self._stage_event_sub = None
        self._window: Optional[ui.Window] = None
        self._status_label: Optional[ui.Label] = None
        self._is_shutting_down: bool = False
        self._shutdown_event = threading.Event()
        
        # WeakSet으로 생성된 task들 추적
        self._background_tasks: weakref.WeakSet = weakref.WeakSet()

        try:
            # Stage 이벤트 구독
            usd_context = get_context()
            if usd_context:
                self._stage_event_sub = usd_context.get_stage_event_stream().create_subscription_to_pop(
                    self._on_stage_event, name="FalconHumanVisualizer Stage Event"
                )
            else:
                logger.error("Failed to get USD context during startup")

            # UI 창 생성
            self._create_ui()

            # Stage 초기화
            self._initialize_stage()
            
            logger.info("FalconHumanVisualizerExtension startup complete.")
        except Exception as e:
            logger.error(f"Error during startup: {e}", exc_info=True)
            # 시작 실패 시 정리
            self._cleanup_resources(force=True)

    def _create_ui(self):
        """UI 창을 생성합니다."""
        try:
            # 기존 창이 있다면 제거
            if hasattr(self, '_window') and self._window:
                try:
                    self._window.destroy()
                except:
                    pass
                self._window = None

            label_height = 30
            vstack_spacing = 30
            button_row_height = 100
            content_actual_height = label_height + vstack_spacing + button_row_height
            window_vertical_padding = 40
            new_window_height = content_actual_height + window_vertical_padding

            self._window = ui.Window("Falcon Human Visualizer", width=600, height=new_window_height)
            
            with self._window.frame:
                with ui.VStack(spacing=vstack_spacing): 
                    self._status_label = ui.Label(
                        "Status: Initializing...",
                        alignment=ui.Alignment.CENTER,
                        word_wrap=True,
                        height=label_height,
                        style={"font_size": 12}
                    )
                    
                    with ui.HStack(spacing=10, height=button_row_height):
                        self.start_button = ui.Button(
                            "Start Consuming",
                            clicked_fn=self._on_start_clicked,
                            width=0
                        )
                        self.stop_button = ui.Button(
                            "Stop Consuming",
                            clicked_fn=self._on_stop_clicked,
                            width=0
                        )
        except Exception as e:
            logger.error(f"Error creating UI: {e}", exc_info=True)

    def _initialize_stage(self):
        """Stage를 초기화하고 Prim들을 설정합니다."""
        if self._is_shutting_down:
            return
            
        try:
            # Stage 가져오기
            stage = get_context().get_stage()
            if stage:
                logger.info("Stage found during startup. Initializing person prims.")
                task = asyncio.ensure_future(self._initialize_person_prims())
                self._background_tasks.add(task)
            else:
                logger.info("Stage not loaded yet. Waiting for stage event.")
                if self._status_label:
                    self._status_label.text = "Status: Waiting for stage..."
        except Exception as e:
            logger.error(f"Error during stage initialization: {e}", exc_info=True)
            if self._status_label:
                self._status_label.text = f"Status: Error - {str(e)}"

    def _on_stage_event(self, event):
        """Stage 이벤트를 처리합니다."""
        if self._is_shutting_down:
            return
            
        try:
            if event.type == StageEventType.OPENED or \
               (event.type == StageEventType.ASSETS_LOADED and not self._person_prim_objects):
                logger.info(f"Stage event: {event.type}. Initializing person prims.")
                task = asyncio.ensure_future(self._initialize_person_prims())
                self._background_tasks.add(task)
                        
            elif event.type == StageEventType.CLOSED:
                logger.info("Stage closed. Clearing person prims info.")
                self._person_prim_objects.clear()
                if self._status_label:
                    self._status_label.text = "Status: Stage closed"
                    
        except Exception as e:
            logger.error(f"Error in stage event handler: {e}", exc_info=True)

    async def _initialize_person_prims(self):
        """미리 정의된 Person Prim들을 초기화합니다."""
        if self._is_shutting_down:
            return
            
        stage = get_context().get_stage()
        if not stage:
            logger.error("Stage not available for prim initialization.")
            if self._status_label:
                self._status_label.text = "Status: Error - Stage not found"
            return

        logger.info(f"Attempting to find and initialize {MAX_PERSONS_TO_DISPLAY} predefined person prims...")
        self._person_prim_objects = []
        
        try:
            for prim_path_str in PERSON_PRIM_PATHS:
                if self._is_shutting_down:
                    return
                    
                prim = stage.GetPrimAtPath(prim_path_str)
                if prim and prim.IsValid():
                    logger.info(f"Found existing prim at {prim_path_str}")
                    try:
                        # Prim을 초기에는 보이지 않도록 설정
                        imageable = UsdGeom.Imageable(prim)
                        if imageable:
                            imageable.MakeInvisible()
                            self._person_prim_objects.append({
                                "prim": prim, 
                                "path": prim_path_str, 
                                "is_currently_visible": False
                            })
                        else:
                            logger.warning(f"Prim at {prim_path_str} is not imageable")
                    except Exception as e:
                        logger.error(f"Error setting up prim {prim_path_str}: {e}")
                else:
                    logger.warning(f"Predefined prim NOT FOUND at path: {prim_path_str}")

            if self._person_prim_objects:
                logger.info(f"Initialized {len(self._person_prim_objects)} of {MAX_PERSONS_TO_DISPLAY} person prims.")
                if self._status_label and not self._is_shutting_down:
                    self._status_label.text = f"Status: Ready ({len(self._person_prim_objects)} prims)"
            else:
                logger.error("Could not find any of the predefined person prims.")
                if self._status_label and not self._is_shutting_down:
                    self._status_label.text = "Status: Error - No person prims found"
                    
        except Exception as e:
            logger.error(f"Error during prim initialization: {e}", exc_info=True)
            if self._status_label and not self._is_shutting_down:
                self._status_label.text = f"Status: Error - {str(e)}"

    def _on_start_clicked(self):
        """Start 버튼 클릭 이벤트를 처리합니다."""
        if self._is_shutting_down:
            return
            
        try:
            if not self._consumer_task or self._consumer_task.done():
                # Stage 상태 확인
                stage = get_context().get_stage()
                if not stage:
                    logger.error("Cannot start consumer: Stage not available.")
                    if self._status_label:
                        self._status_label.text = "Status: Error - Stage not ready"
                    return

                if not self._person_prim_objects:
                    logger.warning("Person prims not initialized. Attempting to initialize now.")
                    task = asyncio.ensure_future(self._initialize_person_prims())
                    self._background_tasks.add(task)

                logger.info("Starting Kafka consumer task.")
                self._consumer_task = asyncio.ensure_future(self._consume_kafka_messages())
                self._background_tasks.add(self._consumer_task)
            else:
                logger.info("Consumer task is already running.")
                if self._status_label:
                    self._status_label.text = "Status: Consumer already running"
                    
        except Exception as e:
            logger.error(f"Error in start button handler: {e}", exc_info=True)
            if self._status_label:
                self._status_label.text = f"Status: Error - {str(e)}"

    def _on_stop_clicked(self):
        """Stop 버튼 클릭 이벤트를 처리합니다."""
        logger.info("Stop consuming button clicked.")
        task = asyncio.ensure_future(self._stop_kafka_consumer())
        self._background_tasks.add(task)

    async def _consume_kafka_messages(self):
        """Kafka 메시지를 소비합니다."""
        if self._is_shutting_down or not self._person_prim_objects:
            logger.error("Cannot start consumer: shutting down or prims not ready.")
            return

        # Prim 유효성 재검사
        valid_prims = []
        for p_info in self._person_prim_objects:
            if p_info["prim"] and p_info["prim"].IsValid():
                valid_prims.append(p_info)
            else:
                logger.warning(f"Invalid prim found: {p_info.get('path', 'Unknown')}")

        if not valid_prims:
            logger.error("No valid person prims available. Cannot start consumer.")
            if self._status_label and not self._is_shutting_down:
                self._status_label.text = "Status: Error - No valid prims"
            return

        self._person_prim_objects = valid_prims

        logger.info(f"Initializing AIOKafkaConsumer for topic '{KAFKA_TOPIC}' at {KAFKA_BROKER}")
        
        consumer = None
        try:
            consumer = AIOKafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BROKER,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="latest",
                loop=asyncio.get_event_loop(),
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                session_timeout_ms=10000,  # 더 짧게 설정
                heartbeat_interval_ms=3000,  # 더 짧게 설정
                request_timeout_ms=5000  # 타임아웃 추가
            )
            
            # Consumer 참조 저장
            self._consumer = consumer
            
            await consumer.start()
            logger.info("AIOKafkaConsumer started successfully.")
            if self._status_label and not self._is_shutting_down:
                self._status_label.text = f"Status: Consuming from {KAFKA_TOPIC}"

            # 모든 Prim을 초기에 보이지 않도록 설정
            for p_info in self._person_prim_objects:
                if self._is_shutting_down:
                    break
                if p_info["prim"] and p_info["prim"].IsValid():
                    try:
                        UsdGeom.Imageable(p_info["prim"]).MakeInvisible()
                        p_info["is_currently_visible"] = False
                    except Exception as e:
                        logger.error(f"Error making prim invisible: {e}")

            # 메시지 소비 루프
            async for msg in consumer:
                if self._is_shutting_down:
                    logger.info("Shutting down, breaking message loop")
                    break
                    
                try:
                    # 취소 확인
                    if self._consumer_task and self._consumer_task.cancelled():
                        logger.info("Consumer task was cancelled, breaking message loop")
                        break
                        
                    message_data = json.loads(msg.value.decode('utf-8'))
                    task = asyncio.create_task(self._process_falcon_message(message_data))
                    self._background_tasks.add(task)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON message: {e}")
                except Exception as e:
                    logger.error(f"Error processing Kafka message: {e}", exc_info=True)
        
        except asyncio.CancelledError:
            logger.info("Kafka consuming task was cancelled.")
            raise  # 취소 예외는 다시 발생시켜야 함
        except Exception as e:
            logger.error(f"AIOKafkaConsumer error: {e}", exc_info=True)
            if self._status_label and not self._is_shutting_down:
                self._status_label.text = f"Status: Error - {str(e)}"
        finally:
            # Consumer 정리
            await self._cleanup_consumer(consumer)
            
            logger.info("Kafka consumer cleanup completed.")
            if hasattr(self, '_status_label') and self._status_label and not self._is_shutting_down:
                self._status_label.text = "Status: Consumer stopped"

    async def _cleanup_consumer(self, consumer):
        """Consumer 정리를 안전하게 수행합니다."""
        if consumer:
            logger.info("Stopping AIOKafkaConsumer in cleanup.")
            try:
                await asyncio.wait_for(consumer.stop(), timeout=3.0)
                logger.info("AIOKafkaConsumer stopped successfully.")
            except asyncio.TimeoutError:
                logger.warning("Consumer stop timed out in cleanup")
            except Exception as e:
                logger.error(f"Error stopping consumer in cleanup: {e}")
            finally:
                consumer = None
                
        # 참조 정리
        self._consumer = None
        if hasattr(self, '_consumer_task'):
            self._consumer_task = None

    async def _process_falcon_message(self, data: dict):
        """Falcon 메시지를 처리하여 Prim 위치를 업데이트합니다."""
        if self._is_shutting_down:
            return
            
        # Stage 가져오기
        stage = get_context().get_stage()
        if not stage:
            logger.warning("Stage not available during message processing.")
            return
            
        if not self._person_prim_objects:
            logger.warning("Person prim objects not initialized. Skipping message processing.")
            return

        try:
            person_locations = data.get("person_locations_estimated", [])
            num_persons_in_message = len(person_locations)

            UWB_ANCHOR_X = 5.4  # UWB 좌표계에서 Omniverse Z=0에 해당하는 X 값
            UWB_ANCHOR_Y = 7.29 # UWB 좌표계에서 Omniverse X=0에 해당하는 Y 값
            
            for i in range(min(MAX_PERSONS_TO_DISPLAY, len(self._person_prim_objects))):
                if self._is_shutting_down:
                    break
                    
                prim_info = self._person_prim_objects[i]
                prim = prim_info.get("prim")

                if not (prim and prim.IsValid()):
                    continue

                if i < num_persons_in_message:
                    person_data = person_locations[i]
                    
                    est_x_falcon = person_data.get("estimated_world_x")
                    est_y_falcon = person_data.get("estimated_world_y")

                    if est_x_falcon is None or est_y_falcon is None:
                        # 데이터가 없으면 숨김
                        if prim_info.get("is_currently_visible", False):
                            try:
                                UsdGeom.Imageable(prim).MakeInvisible()
                                prim_info["is_currently_visible"] = False
                            except Exception as e:
                                logger.error(f"Error hiding prim {prim.GetPath()}: {e}")
                        continue

                    # UWB RTLS 서버 원점이 0,0 이 아니기에 오프셋 기준으로 변환해줘야함
                    relative_uwb_x = est_x_falcon - UWB_ANCHOR_X
                    relative_uwb_y = est_y_falcon + UWB_ANCHOR_Y                 
                    # 좌표 변환
                    ov_x = relative_uwb_y * PERSON_PRIM_SCALE
                    ov_y = PERSON_PRIM_FIXED_Y_HEIGHT
                    ov_z = relative_uwb_x * PERSON_PRIM_SCALE
                    
                    try:
                        # Prim 위치 업데이트
                        xform_api = UsdGeom.XformCommonAPI(prim)
                        if xform_api:
                            xform_api.SetTranslate(Gf.Vec3d(ov_x, ov_y, ov_z))
                        
                        # Prim 보이기
                        imageable = UsdGeom.Imageable(prim)
                        if imageable:
                            if not prim_info.get("is_currently_visible", False):
                                logger.info(f"Making prim {prim.GetPath()} visible")
                            imageable.MakeVisible()
                            prim_info["is_currently_visible"] = True

                    except Exception as e:
                        logger.error(f"Error updating prim {prim.GetPath()}: {e}")
                
                else:
                    # 메시지에 해당 인덱스의 사람 데이터가 없으면 숨김
                    if prim_info.get("is_currently_visible", False):
                        try:
                            UsdGeom.Imageable(prim).MakeInvisible()
                            prim_info["is_currently_visible"] = False
                        except Exception as e:
                            logger.error(f"Error hiding prim {prim.GetPath()}: {e}")
                            
        except Exception as e:
            logger.error(f"Error in message processing: {e}", exc_info=True)

    async def _stop_kafka_consumer(self):
        """Kafka consumer를 중지합니다."""
        logger.info("Stopping Kafka consumer.")
        
        try:
            # 1. Consumer task 취소
            if self._consumer_task and not self._consumer_task.done():
                logger.info("Cancelling consumer task...")
                self._consumer_task.cancel()
                
                # Task 완료 대기 (타임아웃 설정)
                try:
                    await asyncio.wait_for(self._consumer_task, timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("Consumer task cancellation timed out")
                except asyncio.CancelledError:
                    logger.info("Consumer task cancelled successfully.")
                except Exception as e:
                    logger.error(f"Error waiting for consumer task cancellation: {e}")

            # 2. Consumer 정리
            await self._cleanup_consumer(self._consumer)

            # 3. 모든 Prim 숨기기
            await self._hide_all_prims()

            logger.info("Kafka consumer stopped successfully.")
            if hasattr(self, '_status_label') and self._status_label and not self._is_shutting_down:
                self._status_label.text = "Status: Consumer stopped"
                
        except Exception as e:
            logger.error(f"Error in stop consumer: {e}", exc_info=True)
            if hasattr(self, '_status_label') and self._status_label and not self._is_shutting_down:
                self._status_label.text = f"Status: Error stopping - {str(e)}"

    async def _hide_all_prims(self):
        """모든 Prim을 숨깁니다."""
        try:
            for p_info in self._person_prim_objects:
                if p_info.get("prim") and p_info["prim"].IsValid():
                    try:
                        UsdGeom.Imageable(p_info["prim"]).MakeInvisible()
                        p_info["is_currently_visible"] = False
                    except Exception as e:
                        logger.error(f"Error hiding prim on stop: {e}")
        except Exception as e:
            logger.error(f"Error hiding prims: {e}")

    def _cleanup_resources(self, force: bool = False):
        """모든 리소스를 정리합니다."""
        logger.info(f"Cleaning up resources (force={force})...")
        
        try:
            # 1. 종료 플래그 설정
            self._is_shutting_down = True
            self._shutdown_event.set()
            
            # 2. Consumer 강제 정리
            if self._consumer:
                try:
                    # Consumer 내부 상태 강제 정리
                    if hasattr(self._consumer, '_closed'):
                        self._consumer._closed = True
                    if hasattr(self._consumer, '_coordinator'):
                        self._consumer._coordinator = None
                except Exception as e:
                    logger.debug(f"Error during consumer force cleanup: {e}")
                finally:
                    self._consumer = None

            # 3. Task 강제 취소
            if self._consumer_task and not self._consumer_task.done():
                self._consumer_task.cancel()
                self._consumer_task = None

            # 4. 백그라운드 태스크들 취소
            try:
                for task in list(self._background_tasks):
                    if not task.done():
                        task.cancel()
            except Exception as e:
                logger.debug(f"Error cancelling background tasks: {e}")

            # 5. Stage 이벤트 구독 해제
            if self._stage_event_sub:
                try:
                    self._stage_event_sub.unsubscribe()
                    logger.info("Stage event subscription unsubscribed")
                except Exception as e:
                    logger.error(f"Error unsubscribing stage event: {e}")
                finally:
                    self._stage_event_sub = None
            
            # 6. UI 창 정리
            if self._window:
                try:
                    self._window.destroy()
                    logger.info("UI window destroyed")
                except Exception as e:
                    logger.error(f"Error destroying window: {e}")
                finally:
                    self._window = None
                    self._status_label = None
            
            # 7. 데이터 정리
            self._person_prim_objects.clear()
            
            logger.info("Resource cleanup completed.")
            
        except Exception as e:
            logger.error(f"Error during resource cleanup: {e}", exc_info=True)

    def on_shutdown(self):
        """Extension 종료 시 정리 작업을 수행합니다.""" 
        logger.info(f"FalconHumanVisualizerExtension shutdown started. Ext ID: {self._ext_id}")
        
        try:
            # 즉시 강제 정리 수행
            self._cleanup_resources(force=True)
            
            # 짧은 대기로 비동기 작업 완료 확인
            max_wait_time = 2.0  # 최대 2초 대기
            wait_interval = 0.1
            waited_time = 0.0
            
            while waited_time < max_wait_time:
                if self._shutdown_event.is_set():
                    # 모든 비동기 작업이 완료되었는지 확인
                    all_done = True
                    try:
                        for task in list(self._background_tasks):
                            if not task.done():
                                all_done = False
                                break
                    except:
                        pass
                    
                    if all_done:
                        break
                
                import time
                time.sleep(wait_interval)
                waited_time += wait_interval
            
            if waited_time >= max_wait_time:
                logger.warning("Shutdown timeout reached, forcing completion")
            
            logger.info("FalconHumanVisualizerExtension shutdown complete.")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            # 최종 정리
            self._consumer = None
            self._consumer_task = None
            self._stage_event_sub = None
            self._window = None
            self._status_label = None
            self._person_prim_objects.clear()