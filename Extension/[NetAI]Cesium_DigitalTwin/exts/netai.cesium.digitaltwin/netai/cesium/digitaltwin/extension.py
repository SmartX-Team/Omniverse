"""
Main Extension class for Cesium Digital Twin
"""

import asyncio
import json
import omni.ext
import omni.ui as ui
from typing import Dict, Any

from .core.object_tracker import ObjectTracker
from .core.selection_handler import SelectionHandler
from .websocket.client import WebSocketClient
from .websocket.connection_manager import ConnectionManager
from .websocket.message_handler import MessageHandler
from .utils.logger import logger
from .utils.config import Config


class CesiumDigitalTwinExtension(omni.ext.IExt):
    """NetAI Cesium Digital Twin Extension 메인 클래스"""
    
    def __init__(self):
        super().__init__()
        
        # 핵심 컴포넌트들
        self.config = None
        self.object_tracker = None
        self.selection_handler = None
        self.websocket_client = None
        self.connection_manager = None
        self.message_handler = None
        
        # UI 컴포넌트들
        self.window = None
        
        # 상태 관리
        self.is_initialized = False
        self.is_running = False
        
        logger.info("CesiumDigitalTwinExtension instance created")
        
    def on_startup(self, ext_id: str):
        """Extension 시작 시 호출"""
        logger.info(f"Starting Cesium Digital Twin Extension (ID: {ext_id})")
        
        try:
            # 설정 초기화
            self.config = Config()
            
            # 핵심 컴포넌트 초기화
            self._initialize_components()
            
            # 컴포넌트 간 연결 설정
            self._setup_component_connections()
            
            # UI 초기화
            self._initialize_ui()
            
            # 자동 연결 설정이 활성화된 경우 WebSocket 연결 시작
            if self.config.get_auto_connect():
                self._start_digital_twin()
                
            self.is_initialized = True
            logger.info("Cesium Digital Twin Extension started successfully")
            
        except Exception as e:
            logger.error(f"Error starting extension: {e}")
            self._cleanup_on_error()
            
    def on_shutdown(self):
        """Extension 종료 시 호출"""
        logger.info("Shutting down Cesium Digital Twin Extension")
        
        try:
            self._stop_digital_twin()
            self._cleanup_components()
            self._cleanup_ui()
            
            logger.info("Cesium Digital Twin Extension shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            
    def _initialize_components(self):
        """핵심 컴포넌트들 초기화"""
        try:
            # 연결 관리자 초기화
            self.connection_manager = ConnectionManager()
            logger.info("ConnectionManager initialized")
            
            # 메시지 핸들러 초기화
            self.message_handler = MessageHandler()
            logger.info("MessageHandler initialized")
            
            # 객체 추적기 초기화
            self.object_tracker = ObjectTracker()
            logger.info("ObjectTracker initialized")
            
            # 선택 핸들러 초기화
            self.selection_handler = SelectionHandler()
            logger.info("SelectionHandler initialized")
            
            # WebSocket 클라이언트 초기화 (새 모듈들과 연동)
            self.websocket_client = WebSocketClient()
            logger.info("WebSocketClient initialized")
            
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            raise
            
    def _setup_component_connections(self):
        """컴포넌트 간 연결 설정"""
        try:
            # ConnectionManager 콜백 설정
            self.connection_manager.add_state_change_callback(self._on_connection_state_change)
            
            # MessageHandler 핸들러 등록
            self.message_handler.register_handler("select_object", self._handle_select_object_message)
            self.message_handler.register_handler("ack", self._handle_ack_message)
            self.message_handler.register_handler("error", self._handle_error_message)
            self.message_handler.set_default_handler(self._handle_unknown_message)
            
            # ObjectTracker -> WebSocketClient: 좌표 업데이트 전송
            self.object_tracker.add_coordinate_callback(self._on_coordinate_update)
            self.object_tracker.add_error_callback(self._on_tracker_error)
            
            # WebSocketClient 콜백 설정 (MessageHandler 통해서 처리)
            self.websocket_client.add_message_callback(self._on_websocket_message)
            self.websocket_client.add_connection_callback(self._on_websocket_connection_change)
            self.websocket_client.add_error_callback(self._on_websocket_error)
            
            logger.info("Component connections established")
            
        except Exception as e:
            logger.error(f"Error setting up component connections: {e}")
            raise
            
    def _initialize_ui(self):
        """UI 초기화"""
        try:
            if self.config.get_show_window_on_startup():
                self._create_main_window()
                
        except Exception as e:
            logger.error(f"Error initializing UI: {e}")
            # UI 에러는 extension 전체를 중단시키지 않음
            
    def _create_main_window(self):
        """메인 UI 윈도우 생성"""
        try:
            width, height = self.config.get_window_size()
            
            self.window = ui.Window(
                "Cesium Digital Twin",
                width=width,
                height=height,
                dockPreference=ui.DockPreference.LEFT_BOTTOM
            )
            
            with self.window.frame:
                with ui.VStack(spacing=10):
                    # 제목
                    ui.Label("NetAI Cesium Digital Twin", style={"font_size": 18})
                    ui.Separator()
                    
                    # 연결 상태 표시
                    with ui.HStack():
                        ui.Label("Connection Status:", width=100)
                        self.status_label = ui.Label("Disconnected", style={"color": 0xFF0000FF})
                        
                    # 제어 버튼들
                    with ui.HStack():
                        self.start_button = ui.Button("Start", clicked_fn=self._on_start_clicked)
                        self.stop_button = ui.Button("Stop", clicked_fn=self._on_stop_clicked)
                        
                    ui.Separator()
                    
                    # 설정 섹션
                    ui.Label("Settings", style={"font_size": 14})
                    
                    with ui.HStack():
                        ui.Label("WebSocket URL:", width=100)
                        self.url_field = ui.StringField()
                        self.url_field.model.set_value(self.config.get_websocket_url())
                        
                    with ui.HStack():
                        ui.Label("Update Interval:", width=100)
                        self.interval_field = ui.FloatField()
                        self.interval_field.model.set_value(self.config.get_update_interval())
                        
                    ui.Button("Apply Settings", clicked_fn=self._on_apply_settings)
                    
                    ui.Separator()
                    
                    # 통계 정보
                    ui.Label("Statistics", style={"font_size": 14})
                    self.stats_label = ui.Label("No statistics available")
                    
            logger.info("Main window created")
            
        except Exception as e:
            logger.error(f"Error creating main window: {e}")
            
    def _start_digital_twin(self):
        """Digital Twin 시스템 시작"""
        if self.is_running:
            logger.warning("Digital Twin is already running")
            return
            
        try:
            # WebSocket 클라이언트 시작
            self.websocket_client.start()
            
            # 객체 추적 시작
            self.object_tracker.start_tracking()
            
            # 추적 루프 시작 (비동기)
            self._start_tracking_loop()
            
            self.is_running = True
            logger.info("Digital Twin system started")
            
            # UI 업데이트
            self._update_ui_state()
            
        except Exception as e:
            logger.error(f"Error starting Digital Twin: {e}")
            self._stop_digital_twin()
            
    def _stop_digital_twin(self):
        """Digital Twin 시스템 중지"""
        if not self.is_running:
            logger.warning("Digital Twin is not running")
            return
            
        try:
            # 객체 추적 중지
            if self.object_tracker:
                self.object_tracker.stop_tracking()
                
            # WebSocket 클라이언트 중지
            if self.websocket_client:
                self.websocket_client.stop()
                
            self.is_running = False
            logger.info("Digital Twin system stopped")
            
            # UI 업데이트
            self._update_ui_state()
            
        except Exception as e:
            logger.error(f"Error stopping Digital Twin: {e}")
            
    def _start_tracking_loop(self):
        """추적 루프 시작 (비동기)"""
        try:
            # 비동기 태스크로 추적 루프 실행
            import omni.kit.async_engine
            
            async def tracking_task():
                if self.object_tracker:
                    await self.object_tracker.tracking_loop()
                    
            omni.kit.async_engine.run_coroutine(tracking_task())
            
        except Exception as e:
            logger.error(f"Error starting tracking loop: {e}")
            
    # 콜백 함수들
    def _on_coordinate_update(self, prim_path: str, coordinates: Dict[str, Any]):
        """좌표 업데이트 콜백"""
        try:
            if self.websocket_client and self.websocket_client.connected:
                success = self.websocket_client.send_coordinate_update(prim_path, coordinates)
                if not success:
                    logger.warning(f"Failed to send coordinate update for {prim_path}")
                    
        except Exception as e:
            logger.error(f"Error in coordinate update callback: {e}")
            
    def _on_websocket_message(self, message: Dict[str, Any]):
        """WebSocket 메시지 수신 콜백 (MessageHandler로 전달)"""
        try:
            # MessageHandler를 통해 메시지 처리
            if self.message_handler:
                import asyncio
                # 비동기 처리를 위해 태스크 생성
                if hasattr(self, 'loop') and self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.message_handler.process_received_message(json.dumps(message)), 
                        self.loop
                    )
                else:
                    # 동기적으로 처리 (fallback)
                    self._handle_message_sync(message)
            else:
                # MessageHandler가 없으면 직접 처리
                self._handle_message_sync(message)
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            
    def _handle_message_sync(self, message: Dict[str, Any]):
        """동기적 메시지 처리 (fallback)"""
        message_type = message.get("type")
        
        if message_type == "select_object":
            prim_path = message.get("prim_path")
            action = message.get("action", "select")
            
            if prim_path and self.selection_handler:
                success = self.selection_handler.handle_web_selection_request(prim_path, action)
                if success:
                    logger.info(f"Handled web selection: {action} {prim_path}")
                else:
                    logger.warning(f"Failed to handle web selection: {action} {prim_path}")
        else:
            logger.debug(f"Unhandled message type: {message_type}")
            
    def _on_websocket_connection_change(self, connected: bool):
        """WebSocket 연결 상태 변경 콜백"""
        # ConnectionManager에 상태 전달
        if self.connection_manager:
            if connected:
                self.connection_manager.set_state(
                    self.connection_manager.ConnectionState.CONNECTED, 
                    "WebSocket connected"
                )
            else:
                self.connection_manager.set_state(
                    self.connection_manager.ConnectionState.DISCONNECTED, 
                    "WebSocket disconnected"
                )
        
        # 기존 처리
        self._on_connection_change(connected)
        
    def _on_connection_change(self, connected: bool):
        """연결 상태 변경 콜백"""
        status = "Connected" if connected else "Disconnected"
        logger.info(f"Connection status changed: {status}")
        
        # UI 업데이트
        self._update_ui_state()
        
    def _on_connection_state_change(self, old_state, new_state):
        """ConnectionManager 상태 변경 콜백"""
        logger.info(f"Connection state transition: {old_state.value} -> {new_state.value}")
        
        # 특정 상태 변경에 대한 처리
        if new_state == self.connection_manager.ConnectionState.REGISTERED:
            logger.info("Client successfully registered with server")
        elif new_state == self.connection_manager.ConnectionState.ERROR:
            logger.warning("Connection entered error state")
            
        # UI 업데이트
        self._update_ui_state()
        
    # 새로운 메시지 핸들러들
    async def _handle_select_object_message(self, message: Dict[str, Any]):
        """객체 선택 메시지 처리"""
        try:
            prim_path = message.get("prim_path")
            action = message.get("action", "select")
            
            if prim_path and self.selection_handler:
                success = self.selection_handler.handle_web_selection_request(prim_path, action)
                if success:
                    logger.info(f"Handled web selection: {action} {prim_path}")
                else:
                    logger.warning(f"Failed to handle web selection: {action} {prim_path}")
            else:
                logger.error("Invalid select_object message or SelectionHandler not available")
                
        except Exception as e:
            logger.error(f"Error handling select_object message: {e}")
            
    async def _handle_ack_message(self, message: Dict[str, Any]):
        """ACK 메시지 처리"""
        try:
            ack_message = message.get("message", "No message")
            logger.info(f"Server acknowledgment: {ack_message}")
            
            # 클라이언트 등록 ACK인 경우
            if "register" in ack_message.lower() and self.connection_manager:
                self.connection_manager.set_state(
                    self.connection_manager.ConnectionState.REGISTERED,
                    "Client registration confirmed"
                )
                
        except Exception as e:
            logger.error(f"Error handling ACK message: {e}")
            
    async def _handle_error_message(self, message: Dict[str, Any]):
        """에러 메시지 처리"""
        try:
            error_code = message.get("error_code", "UNKNOWN")
            error_message = message.get("error_message", "No error message")
            
            logger.error(f"Server error: {error_code} - {error_message}")
            
            # ConnectionManager에 에러 상태 전달
            if self.connection_manager:
                self.connection_manager.set_state(
                    self.connection_manager.ConnectionState.ERROR,
                    f"Server error: {error_code}"
                )
                
        except Exception as e:
            logger.error(f"Error handling error message: {e}")
            
    async def _handle_unknown_message(self, message: Dict[str, Any]):
        """알 수 없는 메시지 처리"""
        try:
            message_type = message.get("type", "unknown")
            logger.debug(f"Received unknown message type: {message_type}")
            
            # 디버그 모드에서만 전체 메시지 로그
            if self.config.get_debug_mode():
                logger.debug(f"Unknown message content: {message}")
                
        except Exception as e:
            logger.error(f"Error handling unknown message: {e}")
        
    def _on_tracker_error(self, source: str, error: Exception):
        """객체 추적 에러 콜백"""
        logger.error(f"Tracker error from {source}: {error}")
        
    def _on_websocket_error(self, source: str, error: Exception):
        """WebSocket 에러 콜백"""
        logger.error(f"WebSocket error from {source}: {error}")
        
        # ConnectionManager에 에러 상태 전달
        if self.connection_manager:
            self.connection_manager.set_state(
                self.connection_manager.ConnectionState.ERROR,
                f"WebSocket error: {source}"
            )
        
    # UI 이벤트 핸들러들
    def _on_start_clicked(self):
        """시작 버튼 클릭 핸들러"""
        self._start_digital_twin()
        
    def _on_stop_clicked(self):
        """중지 버튼 클릭 핸들러"""
        self._stop_digital_twin()
        
    def _on_apply_settings(self):
        """설정 적용 버튼 클릭 핸들러"""
        try:
            # URL 설정 적용
            new_url = self.url_field.model.get_value_as_string()
            if new_url and new_url != self.config.get_websocket_url():
                self.config.set_websocket_url(new_url)
                if self.websocket_client:
                    self.websocket_client.update_server_url(new_url)
                logger.info(f"WebSocket URL updated: {new_url}")
                
            # 업데이트 간격 설정 적용
            new_interval = self.interval_field.model.get_value_as_float()
            if new_interval > 0 and new_interval != self.config.get_update_interval():
                self.config.set_update_interval(new_interval)
                if self.object_tracker:
                    self.object_tracker.set_update_interval(new_interval)
                logger.info(f"Update interval updated: {new_interval}")
                
            logger.info("Settings applied successfully")
            
        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            
    def _update_ui_state(self):
        """UI 상태 업데이트"""
        if not self.window:
            return
            
        try:
            # 연결 상태 업데이트
            if hasattr(self, 'status_label'):
                if self.websocket_client and self.websocket_client.connected:
                    self.status_label.text = "Connected"
                    self.status_label.style = {"color": 0xFF00FF00}  # 녹색
                else:
                    self.status_label.text = "Disconnected"
                    self.status_label.style = {"color": 0xFF0000FF}  # 빨간색
                    
            # 버튼 상태 업데이트
            if hasattr(self, 'start_button') and hasattr(self, 'stop_button'):
                self.start_button.enabled = not self.is_running
                self.stop_button.enabled = self.is_running
                
            # 통계 정보 업데이트
            self._update_statistics_display()
            
        except Exception as e:
            logger.error(f"Error updating UI state: {e}")
            
    def _update_statistics_display(self):
        """통계 정보 표시 업데이트"""
        if not hasattr(self, 'stats_label'):
            return
            
        try:
            stats_text = "Statistics:\n"
            
            # WebSocket 통계
            if self.websocket_client:
                ws_stats = self.websocket_client.get_statistics()
                stats_text += f"• Messages Sent: {ws_stats.get('messages_sent', 0)}\n"
                stats_text += f"• Messages Received: {ws_stats.get('messages_received', 0)}\n"
                stats_text += f"• Connection Errors: {ws_stats.get('connection_errors', 0)}\n"
                
            # 연결 관리자 통계
            if self.connection_manager:
                conn_info = self.connection_manager.get_connection_info()
                stats_text += f"• Connection State: {conn_info.get('state', 'unknown')}\n"
                stats_text += f"• Retry Count: {conn_info.get('retry_count', 0)}\n"
                
                # 연결 품질 정보
                quality = conn_info.get('connection_quality', {})
                if quality.get('stability_score'):
                    stats_text += f"• Stability Score: {quality['stability_score']:.2f}\n"
                
            # 메시지 핸들러 통계
            if self.message_handler:
                msg_stats = self.message_handler.get_message_stats()
                stats_text += f"• Messages Processed: {msg_stats.get('total_processed', 0)}\n"
                stats_text += f"• Queue Size: {msg_stats.get('queue_stats', {}).get('normal', 0)}\n"
                
            # 객체 추적 통계
            if self.object_tracker:
                tracker_stats = self.object_tracker.get_statistics()
                stats_text += f"• Coordinate Updates: {tracker_stats.get('total_updates', 0)}\n"
                stats_text += f"• Success Rate: {tracker_stats.get('success_rate', 0):.1%}\n"
                stats_text += f"• Tracked Objects: {tracker_stats.get('tracked_objects_count', 0)}\n"
                
            self.stats_label.text = stats_text
            
        except Exception as e:
            logger.error(f"Error updating statistics display: {e}")
            
    def _cleanup_components(self):
        """컴포넌트 정리"""
        try:
            if self.object_tracker:
                self.object_tracker.cleanup()
                self.object_tracker = None
                
            if self.selection_handler:
                self.selection_handler.cleanup()
                self.selection_handler = None
                
            if self.websocket_client:
                self.websocket_client.cleanup()
                self.websocket_client = None
                
            if self.message_handler:
                self.message_handler.cleanup()
                self.message_handler = None
                
            if self.connection_manager:
                self.connection_manager.cleanup()
                self.connection_manager = None
                
            logger.info("Components cleaned up")
            
        except Exception as e:
            logger.error(f"Error cleaning up components: {e}")
            
    def _cleanup_ui(self):
        """UI 정리"""
        try:
            if self.window:
                self.window.destroy()
                self.window = None
                
            logger.info("UI cleaned up")
            
        except Exception as e:
            logger.error(f"Error cleaning up UI: {e}")
            
    def _cleanup_on_error(self):
        """에러 발생 시 정리 작업"""
        try:
            self._stop_digital_twin()
            self._cleanup_components()
            self._cleanup_ui()
            self.is_initialized = False
            
        except Exception as e:
            logger.error(f"Error during error cleanup: {e}")
            
    # 공개 API 메서드들
    def get_status(self) -> Dict[str, Any]:
        """Extension 상태 정보 가져오기"""
        status = {
            "initialized": self.is_initialized,
            "running": self.is_running,
            "components": {
                "object_tracker": self.object_tracker is not None,
                "selection_handler": self.selection_handler is not None,
                "websocket_client": self.websocket_client is not None,
                "connection_manager": self.connection_manager is not None,
                "message_handler": self.message_handler is not None
            }
        }
        
        # 각 컴포넌트의 상세 상태
        if self.websocket_client:
            status["websocket"] = self.websocket_client.get_connection_status()
            
        if self.connection_manager:
            status["connection"] = self.connection_manager.get_connection_info()
            
        if self.message_handler:
            status["messages"] = self.message_handler.get_message_stats()
            
        if self.object_tracker:
            status["tracker"] = self.object_tracker.get_statistics()
            
        return status
        
    def add_tracked_object(self, prim_path: str):
        """추적 객체 추가"""
        if self.object_tracker:
            current_objects = self.config.get_tracked_objects()
            if prim_path not in current_objects:
                current_objects.append(prim_path)
                self.config.set_tracked_objects(current_objects)  # 설정도 업데이트
                self.object_tracker.set_tracked_objects(current_objects)
                logger.info(f"Added tracked object: {prim_path}")
            else:
                logger.warning(f"Object already tracked: {prim_path}")
        else:
            logger.error("ObjectTracker not available")
            
    def remove_tracked_object(self, prim_path: str):
        """추적 객체 제거"""
        if self.object_tracker:
            current_objects = self.config.get_tracked_objects()
            if prim_path in current_objects:
                current_objects.remove(prim_path)
                self.config.set_tracked_objects(current_objects)  # 설정도 업데이트
                self.object_tracker.set_tracked_objects(current_objects)
                logger.info(f"Removed tracked object: {prim_path}")
            else:
                logger.warning(f"Object not in tracked list: {prim_path}")
        else:
            logger.error("ObjectTracker not available")
            
    def send_test_message(self, message_type: str = "test"):
        """테스트 메시지 전송"""
        if self.websocket_client and self.websocket_client.connected:
            test_message = {
                "type": message_type,
                "timestamp": __import__('time').time(),
                "source": "omniverse_extension",
                "test_data": "Hello from Omniverse!"
            }
            
            success = self.websocket_client.send_status_update("test", test_message)
            if success:
                logger.info("Test message sent successfully")
            else:
                logger.error("Failed to send test message")
        else:
            logger.error("WebSocket not connected")


# Extension 전역 인스턴스
_extension_instance = None


def get_extension_instance() -> CesiumDigitalTwinExtension:
    """Extension 인스턴스 가져오기"""
    global _extension_instance
    return _extension_instance


# Omniverse Extension Entry Point
def on_startup(ext_id: str):
    """Extension 시작점"""
    global _extension_instance
    _extension_instance = CesiumDigitalTwinExtension()
    _extension_instance.on_startup(ext_id)


def on_shutdown():
    """Extension 종료점"""
    global _extension_instance
    if _extension_instance:
        _extension_instance.on_shutdown()
        _extension_instance = None