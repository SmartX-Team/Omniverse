"""
WebSocket client for Digital Twin communication
"""

import asyncio
import json
import time
import threading
from typing import Dict, Any, Callable, Optional, List
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI

from ..utils.logger import logger
from ..utils.config import Config


class WebSocketClient:
    """Digital Twin WebSocket 클라이언트"""
    
    def __init__(self):
        self.config = Config()
        self.server_url = self.config.get_websocket_url()
        
        # 연결 상태
        self.websocket = None
        self.connected = False
        self.running = False
        self.registered = False
        
        # 스레드 관리
        self.thread = None
        self.loop = None
        
        # 재연결 설정
        self.max_retries = 5
        self.retry_delay = 5
        self.current_retry = 0
        
        # 콜백 함수들
        self.message_callbacks: List[Callable] = []
        self.connection_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        
        # 통계 정보
        self.stats = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "connection_errors": 0,
            "last_connected": None,
            "last_disconnected": None
        }
        
        logger.info(f"WebSocketClient initialized for {self.server_url}")
        
    def add_message_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """메시지 수신 콜백 추가"""
        self.message_callbacks.append(callback)
        logger.debug(f"Message callback added. Total: {len(self.message_callbacks)}")
        
    def add_connection_callback(self, callback: Callable[[bool], None]):
        """연결 상태 변경 콜백 추가"""
        self.connection_callbacks.append(callback)
        logger.debug(f"Connection callback added. Total: {len(self.connection_callbacks)}")
        
    def add_error_callback(self, callback: Callable[[str, Exception], None]):
        """에러 콜백 추가"""
        self.error_callbacks.append(callback)
        logger.debug(f"Error callback added. Total: {len(self.error_callbacks)}")
        
    def start(self):
        """WebSocket 클라이언트 시작"""
        if self.running:
            logger.warning("WebSocket client is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()
        logger.info("WebSocket client started in background thread")
        
    def stop(self):
        """WebSocket 클라이언트 중지"""
        if not self.running:
            logger.warning("WebSocket client is not running")
            return
            
        self.running = False
        self.connected = False
        self.registered = False
        
        # WebSocket 연결 종료
        if self.loop and self.websocket:
            future = asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
            try:
                future.result(timeout=2.0)
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
                
        logger.info("WebSocket client stopped")
        
    def _run_async_loop(self):
        """별도 스레드에서 비동기 이벤트 루프 실행"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._connect_and_run())
        except Exception as e:
            logger.error(f"Async loop error: {e}")
            self._notify_error("async_loop", e)
        finally:
            self.loop.close()
            self.loop = None
            
    async def _connect_and_run(self):
        """서버에 연결하고 메인 루프 실행"""
        while self.running:
            try:
                self.stats["connection_attempts"] += 1
                logger.info(f"Connecting to {self.server_url}... (Attempt {self.current_retry + 1})")
                
                async with websockets.connect(self.server_url) as websocket:
                    self.websocket = websocket
                    self.connected = True
                    self.current_retry = 0
                    self.stats["successful_connections"] += 1
                    self.stats["last_connected"] = time.time()
                    
                    logger.info("Connected to WebSocket server")
                    self._notify_connection_change(True)
                    
                    # 클라이언트 등록
                    await self._register_client()
                    
                    # 메시지 수신 루프
                    await self._message_receiver()
                    
            except ConnectionClosed:
                logger.info("WebSocket connection closed")
                self._handle_disconnection()
                
            except InvalidURI:
                logger.error(f"Invalid WebSocket URL: {self.server_url}")
                self.stats["connection_errors"] += 1
                self._notify_error("invalid_uri", Exception(f"Invalid URL: {self.server_url}"))
                break
                
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.stats["connection_errors"] += 1
                self._notify_error("connection", e)
                self._handle_disconnection()
                
            # 재연결 로직
            if self.running and self.current_retry < self.max_retries:
                self.current_retry += 1
                logger.info(f"Retrying in {self.retry_delay} seconds... ({self.current_retry}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay)
            elif self.running:
                logger.error("Max retries reached. Stopping client.")
                self.running = False
                
    def _handle_disconnection(self):
        """연결 해제 처리"""
        if self.connected:
            self.connected = False
            self.registered = False
            self.stats["last_disconnected"] = time.time()
            self._notify_connection_change(False)
            
    async def _register_client(self):
        """Omniverse Extension으로 클라이언트 등록"""
        register_message = {
            "type": "client_register",
            "client_type": "omniverse_extension"
        }
        
        success = await self._send_message(register_message)
        if success:
            self.registered = True
            logger.info("Client registration sent successfully")
        else:
            logger.error("Failed to send client registration")
            
    async def _message_receiver(self):
        """서버로부터 메시지 수신 처리"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    self.stats["messages_received"] += 1
                    
                    if self.config.get_log_websocket_messages():
                        logger.websocket_debug("Received message", data)
                        
                    await self._handle_received_message(data)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {message}")
                    self._notify_error("json_decode", e)
                    
                except Exception as e:
                    logger.error(f"Error processing received message: {e}")
                    self._notify_error("message_processing", e)
                    
        except ConnectionClosed:
            logger.info("Message receiver: Connection closed")
        except Exception as e:
            logger.error(f"Message receiver error: {e}")
            self._notify_error("message_receiver", e)
            
    async def _handle_received_message(self, data: Dict[str, Any]):
        """수신된 메시지 처리"""
        message_type = data.get("type")
        
        if message_type == "ack":
            logger.info(f"Server acknowledgment: {data.get('message', 'No message')}")
            
        elif message_type == "error":
            error_code = data.get("error_code", "UNKNOWN")
            error_message = data.get("error_message", "No error message")
            logger.error(f"Server error: {error_code} - {error_message}")
            self._notify_error("server_error", Exception(f"{error_code}: {error_message}"))
            
        else:
            # 다른 메시지들은 콜백으로 전달
            self._notify_message_received(data)
            
    async def _send_message(self, message: Dict[str, Any]) -> bool:
        """메시지 전송"""
        if not self.connected or not self.websocket:
            logger.warning("Cannot send message: not connected")
            return False
            
        try:
            message_json = json.dumps(message)
            await self.websocket.send(message_json)
            self.stats["messages_sent"] += 1
            
            if self.config.get_log_websocket_messages():
                logger.websocket_debug("Sent message", message)
                
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._notify_error("send_message", e)
            return False
            
    def send_coordinate_update(self, prim_path: str, coordinates: Dict[str, Any]) -> bool:
        """좌표 업데이트 메시지 전송 (동기 인터페이스)"""
        if not self.loop or not self.running:
            return False
            
        message = {
            "type": "coordinate_update",
            "prim_path": prim_path,
            "latitude": coordinates["latitude"],
            "longitude": coordinates["longitude"],
            "height": coordinates["height"],
            "metadata": coordinates["metadata"]
        }
        
        # 비동기 함수를 동기적으로 호출
        future = asyncio.run_coroutine_threadsafe(self._send_message(message), self.loop)
        try:
            return future.result(timeout=1.0)
        except Exception as e:
            logger.error(f"Error sending coordinate update: {e}")
            return False
            
    def send_status_update(self, status: str, details: Dict[str, Any] = None) -> bool:
        """상태 업데이트 메시지 전송"""
        if not self.loop or not self.running:
            return False
            
        message = {
            "type": "status_update",
            "status": status,
            "timestamp": time.time()
        }
        
        if details:
            message["details"] = details
            
        future = asyncio.run_coroutine_threadsafe(self._send_message(message), self.loop)
        try:
            return future.result(timeout=1.0)
        except Exception as e:
            logger.error(f"Error sending status update: {e}")
            return False
            
    def _notify_message_received(self, message: Dict[str, Any]):
        """메시지 수신 콜백 호출"""
        for callback in self.message_callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")
                
    def _notify_connection_change(self, connected: bool):
        """연결 상태 변경 콜백 호출"""
        for callback in self.connection_callbacks:
            try:
                callback(connected)
            except Exception as e:
                logger.error(f"Error in connection callback: {e}")
                
    def _notify_error(self, source: str, error: Exception):
        """에러 콜백 호출"""
        for callback in self.error_callbacks:
            try:
                callback(source, error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
                
    def get_connection_status(self) -> Dict[str, Any]:
        """연결 상태 정보 가져오기"""
        return {
            "connected": self.connected,
            "registered": self.registered,
            "running": self.running,
            "server_url": self.server_url,
            "current_retry": self.current_retry,
            "max_retries": self.max_retries
        }
        
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 가져오기"""
        stats = self.stats.copy()
        
        if stats["last_connected"] and stats["last_disconnected"]:
            if stats["last_connected"] > stats["last_disconnected"]:
                stats["current_session_duration"] = time.time() - stats["last_connected"]
            else:
                stats["current_session_duration"] = 0.0
        elif stats["last_connected"]:
            stats["current_session_duration"] = time.time() - stats["last_connected"]
        else:
            stats["current_session_duration"] = 0.0
            
        return stats
        
    def update_server_url(self, url: str):
        """서버 URL 업데이트"""
        if url != self.server_url:
            self.server_url = url
            self.config.set_websocket_url(url)
            logger.info(f"Server URL updated to: {url}")
            
            # 연결 중이면 재연결
            if self.connected:
                logger.info("Reconnecting with new URL...")
                self.stop()
                self.start()
                
    def cleanup(self):
        """정리 작업"""
        self.stop()
        self.message_callbacks.clear()
        self.connection_callbacks.clear()
        self.error_callbacks.clear()
        logger.info("WebSocketClient cleaned up")