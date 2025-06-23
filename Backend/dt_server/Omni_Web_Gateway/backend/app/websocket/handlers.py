import json
from typing import Dict
from ..core.logger import logger
from ..core.exceptions import InvalidMessageFormat, ClientNotRegistered
from ..models.message import (
    ClientRegisterMessage, CoordinateUpdateMessage, 
    SelectObjectMessage, ErrorMessage
)
from .manager import websocket_manager


class MessageHandler:
    
    async def handle_message(self, client_id: str, raw_message: str):
        """받은 메시지를 파싱하고 적절한 핸들러로 라우팅"""
        try:
            message_data = json.loads(raw_message)
            message_type = message_data.get("type")
            
            if not message_type:
                raise InvalidMessageFormat("Message type is required")
            
            logger.info(f"Received message from {client_id}: {message_type}")
            
            # 메시지 타입별 처리
            if message_type == "client_register":
                await self._handle_client_register(client_id, message_data)
            elif message_type == "coordinate_update":
                await self._handle_coordinate_update(client_id, message_data)
            elif message_type == "select_object":
                await self._handle_select_object(client_id, message_data)
            else:
                await self._send_error(client_id, "UNKNOWN_MESSAGE_TYPE", 
                                     f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self._send_error(client_id, "INVALID_JSON", "Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
            await self._send_error(client_id, "INTERNAL_ERROR", str(e))
    
    async def _handle_client_register(self, client_id: str, message_data: Dict):
        """클라이언트 등록 처리"""
        try:
            register_message = ClientRegisterMessage(**message_data)
            await websocket_manager.register_client(client_id, register_message)
        except Exception as e:
            await self._send_error(client_id, "REGISTRATION_FAILED", str(e))
    
    async def _handle_coordinate_update(self, client_id: str, message_data: Dict):
        """좌표 업데이트 처리 (Omniverse → Web)"""
        try:
            # 클라이언트 등록 상태 확인
            client_info = websocket_manager.get_client_info(client_id)
            if not client_info or not client_info.is_registered:
                raise ClientNotRegistered("Client must register first")
            
            # Omniverse Extension에서 오는 메시지인지 확인
            if client_info.client_type != "omniverse_extension":
                await self._send_error(client_id, "UNAUTHORIZED", 
                                     "Only Omniverse Extension can send coordinate updates")
                return
            
            # 메시지 검증
            coord_message = CoordinateUpdateMessage(**message_data)
            
            # Web 클라이언트들에게 브로드캐스트
            await websocket_manager.broadcast_to_web_clients(coord_message.dict())
            
            logger.info(f"Coordinate update broadcasted: {coord_message.prim_path}")
            
        except Exception as e:
            await self._send_error(client_id, "COORDINATE_UPDATE_FAILED", str(e))
    
    async def _handle_select_object(self, client_id: str, message_data: Dict):
        """객체 선택 처리 (Web → Omniverse)"""
        try:
            # 클라이언트 등록 상태 확인
            client_info = websocket_manager.get_client_info(client_id)
            if not client_info or not client_info.is_registered:
                raise ClientNotRegistered("Client must register first")
            
            # Web UI에서 오는 메시지인지 확인
            if client_info.client_type != "web_ui":
                await self._send_error(client_id, "UNAUTHORIZED", 
                                     "Only Web UI can send object selection commands")
                return
            
            # 메시지 검증
            select_message = SelectObjectMessage(**message_data)
            
            # Omniverse Extension 클라이언트들에게 전송
            await websocket_manager.send_to_omniverse_clients(select_message.dict())
            
            logger.info(f"Object selection sent: {select_message.prim_path}")
            
        except Exception as e:
            await self._send_error(client_id, "OBJECT_SELECTION_FAILED", str(e))
    
    async def _send_error(self, client_id: str, error_code: str, error_message: str):
        """에러 메시지 전송"""
        error_msg = ErrorMessage(
            error_code=error_code,
            error_message=error_message
        )
        await websocket_manager._send_to_client(client_id, error_msg.dict())


# 전역 메시지 핸들러 인스턴스
message_handler = MessageHandler()