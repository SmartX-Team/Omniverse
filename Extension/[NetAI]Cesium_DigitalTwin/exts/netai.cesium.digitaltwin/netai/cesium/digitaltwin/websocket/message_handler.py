"""
WebSocket message handling module
"""

import json
import time
from typing import Dict, Any, Callable, List, Optional
from enum import Enum

from ..utils.logger import logger
from ..utils.config import Config


class MessageType(Enum):
    """메시지 타입 열거형"""
    # 클라이언트 -> 서버
    CLIENT_REGISTER = "client_register"
    COORDINATE_UPDATE = "coordinate_update"
    STATUS_UPDATE = "status_update"
    PING = "ping"
    PONG = "pong"
    
    # 서버 -> 클라이언트
    ACK = "ack"
    SELECT_OBJECT = "select_object"
    ERROR = "error"
    SERVER_PING = "server_ping"
    SERVER_PONG = "server_pong"
    
    # 양방향
    HEARTBEAT = "heartbeat"
    CUSTOM = "custom"


class MessagePriority(Enum):
    """메시지 우선순위"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageHandler:
    """WebSocket 메시지 처리 클래스"""
    
    def __init__(self):
        self.config = Config()
        
        # 메시지 처리 콜백
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.default_handler: Optional[Callable] = None
        
        # 메시지 검증 규칙
        self.validation_rules = {
            MessageType.CLIENT_REGISTER.value: self._validate_client_register,
            MessageType.COORDINATE_UPDATE.value: self._validate_coordinate_update,
            MessageType.STATUS_UPDATE.value: self._validate_status_update,
            MessageType.SELECT_OBJECT.value: self._validate_select_object,
        }
        
        # 메시지 통계
        self.message_stats = {
            "total_processed": 0,
            "total_sent": 0,
            "by_type": {},
            "validation_errors": 0,
            "processing_errors": 0,
            "last_processed": None
        }
        
        # 메시지 큐 (우선순위별)
        self.message_queues = {
            MessagePriority.CRITICAL: [],
            MessagePriority.HIGH: [],
            MessagePriority.NORMAL: [],
            MessagePriority.LOW: []
        }
        
        logger.info("MessageHandler initialized")
        
    def register_handler(self, message_type: str, handler: Callable[[Dict[str, Any]], None]):
        """메시지 타입별 핸들러 등록"""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
            
        if handler not in self.message_handlers[message_type]:
            self.message_handlers[message_type].append(handler)
            logger.debug(f"Handler registered for message type: {message_type}")
            
    def unregister_handler(self, message_type: str, handler: Callable):
        """메시지 핸들러 등록 해제"""
        if message_type in self.message_handlers:
            if handler in self.message_handlers[message_type]:
                self.message_handlers[message_type].remove(handler)
                logger.debug(f"Handler unregistered for message type: {message_type}")
                
    def set_default_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """기본 메시지 핸들러 설정"""
        self.default_handler = handler
        logger.debug("Default message handler set")
        
    async def process_received_message(self, raw_message: str) -> bool:
        """수신된 메시지 처리"""
        try:
            # JSON 파싱
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {raw_message[:100]}...")
                self.message_stats["validation_errors"] += 1
                return False
                
            # 메시지 유효성 검증
            if not self._validate_message_structure(message):
                self.message_stats["validation_errors"] += 1
                return False
                
            message_type = message.get("type")
            
            # 타입별 유효성 검증
            if message_type in self.validation_rules:
                if not self.validation_rules[message_type](message):
                    self.message_stats["validation_errors"] += 1
                    return False
                    
            # 메시지 처리
            await self._dispatch_message(message)
            
            # 통계 업데이트
            self._update_message_stats(message_type, "received")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing received message: {e}")
            self.message_stats["processing_errors"] += 1
            return False
            
    async def _dispatch_message(self, message: Dict[str, Any]):
        """메시지 디스패치"""
        message_type = message.get("type")
        
        # 타입별 핸들러 실행
        if message_type in self.message_handlers:
            for handler in self.message_handlers[message_type]:
                try:
                    await self._execute_handler(handler, message)
                except Exception as e:
                    logger.error(f"Error in message handler for {message_type}: {e}")
                    
        # 기본 핸들러 실행
        elif self.default_handler:
            try:
                await self._execute_handler(self.default_handler, message)
            except Exception as e:
                logger.error(f"Error in default message handler: {e}")
        else:
            logger.warning(f"No handler found for message type: {message_type}")
            
    async def _execute_handler(self, handler: Callable, message: Dict[str, Any]):
        """핸들러 실행 (동기/비동기 모두 지원)"""
        import asyncio
        import inspect
        
        if inspect.iscoroutinefunction(handler):
            await handler(message)
        else:
            # 동기 함수를 별도 스레드에서 실행
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, handler, message)
            
    def create_message(self, message_type: str, data: Dict[str, Any] = None, 
                      priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """메시지 생성"""
        message = {
            "type": message_type,
            "timestamp": time.time(),
            "version": "1.0"
        }
        
        if data:
            message.update(data)
            
        # 메시지 타입별 기본 필드 추가
        message = self._add_default_fields(message)
        
        return message
        
    def _add_default_fields(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """메시지 타입별 기본 필드 추가"""
        message_type = message.get("type")
        
        if message_type == MessageType.CLIENT_REGISTER.value:
            message.setdefault("client_type", "omniverse_extension")
            message.setdefault("metadata", {
                "version": "1.0.0",
                "capabilities": ["coordinate_tracking", "object_selection"]
            })
            
        elif message_type == MessageType.COORDINATE_UPDATE.value:
            message.setdefault("metadata", {})
            
        elif message_type == MessageType.STATUS_UPDATE.value:
            message.setdefault("details", {})
            
        return message
        
    def queue_message(self, message: Dict[str, Any], priority: MessagePriority = MessagePriority.NORMAL):
        """메시지를 우선순위 큐에 추가"""
        self.message_queues[priority].append(message)
        logger.debug(f"Message queued with priority {priority.name}")
        
    def get_next_message(self) -> Optional[Dict[str, Any]]:
        """우선순위에 따라 다음 메시지 가져오기"""
        for priority in [MessagePriority.CRITICAL, MessagePriority.HIGH, 
                        MessagePriority.NORMAL, MessagePriority.LOW]:
            if self.message_queues[priority]:
                return self.message_queues[priority].pop(0)
        return None
        
    def get_queue_size(self, priority: MessagePriority = None) -> int:
        """큐 크기 조회"""
        if priority:
            return len(self.message_queues[priority])
        return sum(len(queue) for queue in self.message_queues.values())
        
    def clear_queue(self, priority: MessagePriority = None):
        """큐 정리"""
        if priority:
            self.message_queues[priority].clear()
            logger.debug(f"Cleared {priority.name} priority queue")
        else:
            for queue in self.message_queues.values():
                queue.clear()
            logger.debug("Cleared all message queues")
            
    def _validate_message_structure(self, message: Dict[str, Any]) -> bool:
        """메시지 기본 구조 검증"""
        if not isinstance(message, dict):
            logger.error("Message must be a dictionary")
            return False
            
        if "type" not in message:
            logger.error("Message must have 'type' field")
            return False
            
        if not isinstance(message["type"], str):
            logger.error("Message type must be a string")
            return False
            
        return True
        
    def _validate_client_register(self, message: Dict[str, Any]) -> bool:
        """클라이언트 등록 메시지 검증"""
        required_fields = ["client_type"]
        return self._check_required_fields(message, required_fields)
        
    def _validate_coordinate_update(self, message: Dict[str, Any]) -> bool:
        """좌표 업데이트 메시지 검증"""
        required_fields = ["prim_path", "latitude", "longitude"]
        
        if not self._check_required_fields(message, required_fields):
            return False
            
        # 좌표 범위 검증
        lat = message.get("latitude")
        lng = message.get("longitude")
        
        if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
            logger.error(f"Invalid latitude: {lat}")
            return False
            
        if not isinstance(lng, (int, float)) or not (-180 <= lng <= 180):
            logger.error(f"Invalid longitude: {lng}")
            return False
            
        return True
        
    def _validate_status_update(self, message: Dict[str, Any]) -> bool:
        """상태 업데이트 메시지 검증"""
        required_fields = ["status"]
        return self._check_required_fields(message, required_fields)
        
    def _validate_select_object(self, message: Dict[str, Any]) -> bool:
        """객체 선택 메시지 검증"""
        required_fields = ["prim_path"]
        
        if not self._check_required_fields(message, required_fields):
            return False
            
        # Prim 경로 형식 검증
        prim_path = message.get("prim_path")
        if not isinstance(prim_path, str) or not prim_path.startswith("/"):
            logger.error(f"Invalid prim_path format: {prim_path}")
            return False
            
        return True
        
    def _check_required_fields(self, message: Dict[str, Any], required_fields: List[str]) -> bool:
        """필수 필드 존재 확인"""
        for field in required_fields:
            if field not in message:
                logger.error(f"Missing required field: {field}")
                return False
        return True
        
    def _update_message_stats(self, message_type: str, direction: str):
        """메시지 통계 업데이트"""
        self.message_stats["total_processed"] += 1
        self.message_stats["last_processed"] = time.time()
        
        if message_type not in self.message_stats["by_type"]:
            self.message_stats["by_type"][message_type] = {
                "received": 0,
                "sent": 0
            }
            
        self.message_stats["by_type"][message_type][direction] += 1
        
    def get_message_stats(self) -> Dict[str, Any]:
        """메시지 통계 조회"""
        stats = self.message_stats.copy()
        
        # 큐 통계 추가
        stats["queue_stats"] = {
            priority.name.lower(): len(queue) 
            for priority, queue in self.message_queues.items()
        }
        
        # 처리율 계산
        if stats["last_processed"]:
            stats["processing_rate"] = stats["total_processed"] / (time.time() - stats["last_processed"])
        else:
            stats["processing_rate"] = 0.0
            
        return stats
        
    def export_message_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """메시지 로그 내보내기 (디버깅용)"""
        # 실제 구현에서는 메시지 로그를 저장하고 반환
        # 여기서는 통계 정보만 반환
        return [self.get_message_stats()]
        
    def cleanup(self):
        """정리 작업"""
        self.message_handlers.clear()
        self.default_handler = None
        self.clear_queue()
        
        # 통계 초기화
        self.message_stats = {
            "total_processed": 0,
            "total_sent": 0,
            "by_type": {},
            "validation_errors": 0,
            "processing_errors": 0,
            "last_processed": None
        }
        
        logger.info("MessageHandler cleaned up")