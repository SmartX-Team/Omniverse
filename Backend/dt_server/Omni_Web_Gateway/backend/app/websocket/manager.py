import uuid
import json
from typing import Dict, List
from fastapi import WebSocket, WebSocketDisconnect
from ..core.logger import logger
from ..core.exceptions import ClientNotRegistered, UnsupportedClientType
from ..models.client import ClientInfo, ClientType
from ..models.message import (
    BaseMessage, ClientRegisterMessage, ErrorMessage,
    CoordinateUpdateMessage, SelectObjectMessage
)


class WebSocketManager:
    def __init__(self):
        self.clients: Dict[str, ClientInfo] = {}
    
    async def connect(self, websocket: WebSocket) -> str:
        """새로운 WebSocket 연결을 수락하고 클라이언트 ID 반환"""
        await websocket.accept()
        client_id = str(uuid.uuid4())
        
        client_info = ClientInfo(
            client_id=client_id,
            websocket=websocket,
            is_registered=False
        )
        self.clients[client_id] = client_info
        
        logger.info(f"New WebSocket connection: {client_id}")
        return client_id
    
    def disconnect(self, client_id: str):
        """클라이언트 연결 해제"""
        if client_id in self.clients:
            client_info = self.clients[client_id]
            logger.info(f"Client disconnected: {client_id} ({client_info.client_type})")
            del self.clients[client_id]
    
    async def register_client(self, client_id: str, message: ClientRegisterMessage):
        """클라이언트 등록 (타입 설정)"""
        if client_id not in self.clients:
            raise ClientNotRegistered(f"Client {client_id} not found")
        
        if message.client_type not in [ClientType.OMNIVERSE_EXTENSION, ClientType.WEB_UI]:
            raise UnsupportedClientType(f"Unsupported client type: {message.client_type}")
        
        client_info = self.clients[client_id]
        client_info.client_type = message.client_type
        client_info.is_registered = True
        
        logger.info(f"Client registered: {client_id} as {message.client_type}")
        
        # 등록 확인 응답
        await self._send_to_client(client_id, {
            "type": "ack",
            "original_type": "client_register",
            "status": "success"
        })
    
    async def broadcast_to_web_clients(self, message: Dict):
        """Web UI 클라이언트들에게 브로드캐스트"""
        web_clients = [
            client for client in self.clients.values()
            if client.client_type == ClientType.WEB_UI and client.is_registered
        ]
        
        for client in web_clients:
            try:
                await client.websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send to web client {client.client_id}: {e}")
    
    async def send_to_omniverse_clients(self, message: Dict):
        """Omniverse Extension 클라이언트들에게 전송"""
        omni_clients = [
            client for client in self.clients.values()
            if client.client_type == ClientType.OMNIVERSE_EXTENSION and client.is_registered
        ]
        
        for client in omni_clients:
            try:
                await client.websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send to omniverse client {client.client_id}: {e}")
    
    async def _send_to_client(self, client_id: str, message: Dict):
        """특정 클라이언트에게 메시지 전송"""
        if client_id in self.clients:
            try:
                await self.clients[client_id].websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send to client {client_id}: {e}")
    
    def get_client_info(self, client_id: str) -> ClientInfo:
        """클라이언트 정보 조회"""
        return self.clients.get(client_id)
    
    def get_connected_clients_summary(self) -> Dict:
        """연결된 클라이언트 요약 정보"""
        summary = {
            "total": len(self.clients),
            "registered": sum(1 for c in self.clients.values() if c.is_registered),
            "omniverse_clients": sum(1 for c in self.clients.values() 
                                   if c.client_type == ClientType.OMNIVERSE_EXTENSION),
            "web_clients": sum(1 for c in self.clients.values() 
                             if c.client_type == ClientType.WEB_UI)
        }
        return summary


# 전역 WebSocket 매니저 인스턴스
websocket_manager = WebSocketManager()
