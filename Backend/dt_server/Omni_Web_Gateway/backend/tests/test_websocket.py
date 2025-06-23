import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi import WebSocket

from app.websocket.manager import WebSocketManager
from app.websocket.handlers import MessageHandler
from app.models.client import ClientType
from app.models.message import ClientRegisterMessage


class TestWebSocketManager:
    """WebSocket 매니저 테스트"""
    
    @pytest.mark.asyncio
    async def test_connect_client(self):
        """클라이언트 연결 테스트"""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        
        client_id = await manager.connect(mock_websocket)
        
        assert client_id in manager.clients
        assert manager.clients[client_id].websocket == mock_websocket
        assert manager.clients[client_id].is_registered is False
        mock_websocket.accept.assert_called_once()
    
    def test_disconnect_client(self):
        """클라이언트 연결 해제 테스트"""
        manager = WebSocketManager()
        
        # 가짜 클라이언트 추가
        from app.models.client import ClientInfo
        client_id = "test-client-123"
        client_info = ClientInfo(client_id=client_id)
        manager.clients[client_id] = client_info
        
        # 연결 해제
        manager.disconnect(client_id)
        
        assert client_id not in manager.clients
    
    @pytest.mark.asyncio
    async def test_register_client(self):
        """클라이언트 등록 테스트"""
        manager = WebSocketManager()
        
        # Mock 클라이언트 생성
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.send_text = AsyncMock()
        
        client_id = await manager.connect(mock_websocket)
        
        # 등록 메시지 생성
        register_msg = ClientRegisterMessage(
            client_type=ClientType.WEB_UI
        )
        
        # 클라이언트 등록
        await manager.register_client(client_id, register_msg)
        
        client_info = manager.clients[client_id]
        assert client_info.client_type == ClientType.WEB_UI
        assert client_info.is_registered is True
        
        # ACK 메시지 전송 확인
        mock_websocket.send_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_broadcast_to_web_clients(self):
        """Web 클라이언트 브로드캐스트 테스트"""
        manager = WebSocketManager()
        
        # Mock Web UI 클라이언트들 생성
        web_clients = []
        for i in range(3):
            mock_websocket = Mock(spec=WebSocket)
            mock_websocket.send_text = AsyncMock()
            
            client_id = await manager.connect(mock_websocket)
            register_msg = ClientRegisterMessage(client_type=ClientType.WEB_UI)
            await manager.register_client(client_id, register_msg)
            
            web_clients.append(mock_websocket)
        
        # Omniverse 클라이언트도 하나 추가 (브로드캐스트 대상 아님)
        omni_websocket = Mock(spec=WebSocket)
        omni_websocket.send_text = AsyncMock()
        omni_client_id = await manager.connect(omni_websocket)
        omni_register_msg = ClientRegisterMessage(client_type=ClientType.OMNIVERSE_EXTENSION)
        await manager.register_client(omni_client_id, omni_register_msg)
        
        # send_text 호출 횟수 초기화 (등록 ACK 메시지 때문에 이미 호출됨)
        for web_client in web_clients:
            web_client.send_text.reset_mock()
        omni_websocket.send_text.reset_mock()
        
        # 브로드캐스트 실행
        test_message = {"type": "coordinate_update", "data": "test"}
        await manager.broadcast_to_web_clients(test_message)
        
        # Web 클라이언트들에게만 전송되었는지 확인
        for web_client in web_clients:
            web_client.send_text.assert_called_once()
        
        # Omniverse 클라이언트에게는 전송되지 않았는지 확인
        omni_websocket.send_text.assert_not_called()
    
    def test_get_connected_clients_summary(self):
        """연결된 클라이언트 요약 정보 테스트"""
        manager = WebSocketManager()
        
        # 가짜 클라이언트들 추가
        from app.models.client import ClientInfo
        
        # Web UI 클라이언트 2개
        for i in range(2):
            client_info = ClientInfo(
                client_id=f"web-{i}",
                client_type=ClientType.WEB_UI,
                is_registered=True
            )
            manager.clients[f"web-{i}"] = client_info
        
        # Omniverse 클라이언트 1개
        omni_client = ClientInfo(
            client_id="omni-1",
            client_type=ClientType.OMNIVERSE_EXTENSION,
            is_registered=True
        )
        manager.clients["omni-1"] = omni_client
        
        # 등록되지 않은 클라이언트 1개
        unregistered_client = ClientInfo(
            client_id="unregistered-1",
            is_registered=False
        )
        manager.clients["unregistered-1"] = unregistered_client
        
        summary = manager.get_connected_clients_summary()
        
        assert summary["total"] == 4
        assert summary["registered"] == 3
        assert summary["web_clients"] == 2
        assert summary["omniverse_clients"] == 1


class TestMessageHandler:
    """메시지 핸들러 테스트"""
    
    @pytest.mark.asyncio
    async def test_handle_client_register(self):
        """클라이언트 등록 메시지 처리 테스트"""
        handler = MessageHandler()
        
        with patch('app.websocket.handlers.websocket_manager') as mock_manager:
            mock_manager.register_client = AsyncMock()
            
            register_data = {
                "type": "client_register",
                "client_type": "web_ui"
            }
            
            await handler.handle_message("test-client", json.dumps(register_data))
            
            mock_manager.register_client.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_coordinate_update(self):
        """좌표 업데이트 메시지 처리 테스트"""
        handler = MessageHandler()
        
        with patch('app.websocket.handlers.websocket_manager') as mock_manager:
            # Mock 클라이언트 정보
            from app.models.client import ClientInfo
            mock_client = ClientInfo(
                client_id="test-client",
                client_type=ClientType.OMNIVERSE_EXTENSION,
                is_registered=True
            )
            mock_manager.get_client_info.return_value = mock_client
            mock_manager.broadcast_to_web_clients = AsyncMock()
            
            coord_data = {
                "type": "coordinate_update",
                "prim_path": "/World/Husky_01",
                "latitude": 37.123,
                "longitude": 127.456,
                "height": 100.0
            }
            
            await handler.handle_message("test-client", json.dumps(coord_data))
            
            mock_manager.broadcast_to_web_clients.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_invalid_json(self):
        """유효하지 않은 JSON 처리 테스트"""
        handler = MessageHandler()
        
        with patch('app.websocket.handlers.websocket_manager') as mock_manager:
            mock_manager._send_to_client = AsyncMock()
            
            # 유효하지 않은 JSON
            invalid_json = '{"type": "test", invalid json}'
            
            await handler.handle_message("test-client", invalid_json)
            
            # 에러 메시지가 전송되었는지 확인
            mock_manager._send_to_client.assert_called_once()
            call_args = mock_manager._send_to_client.call_args
            error_msg = call_args[0][1]  # 두 번째 인자가 메시지
            
            assert error_msg["type"] == "error"
            assert error_msg["error_code"] == "INVALID_JSON"