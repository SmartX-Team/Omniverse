import pytest
from pydantic import ValidationError

from app.models.client import ClientType, ClientInfo
from app.models.message import (
    ClientRegisterMessage,
    CoordinateUpdateMessage, 
    SelectObjectMessage,
    ErrorMessage,
    AckMessage
)


class TestClientModels:
    """클라이언트 모델 테스트"""
    
    def test_client_type_enum(self):
        """ClientType enum 테스트"""
        assert ClientType.OMNIVERSE_EXTENSION == "omniverse_extension"
        assert ClientType.WEB_UI == "web_ui"
    
    def test_client_info_creation(self):
        """ClientInfo 생성 테스트"""
        client = ClientInfo(client_id="test-123")
        assert client.client_id == "test-123"
        assert client.client_type is None
        assert client.is_registered is False


class TestMessageModels:
    """메시지 모델 테스트"""
    
    def test_client_register_message(self):
        """클라이언트 등록 메시지 테스트"""
        data = {
            "type": "client_register",
            "client_type": "web_ui"
        }
        msg = ClientRegisterMessage(**data)
        assert msg.type == "client_register"
        assert msg.client_type == ClientType.WEB_UI
    
    def test_coordinate_update_message_valid(self):
        """유효한 좌표 업데이트 메시지 테스트"""
        data = {
            "type": "coordinate_update",
            "prim_path": "/World/Husky_01",
            "latitude": 37.123456,
            "longitude": 127.654321,
            "height": 100.0
        }
        msg = CoordinateUpdateMessage(**data)
        assert msg.prim_path == "/World/Husky_01"
        assert msg.latitude == 37.123456
        assert msg.longitude == 127.654321
        assert msg.height == 100.0
    
    def test_coordinate_update_message_invalid_latitude(self):
        """유효하지 않은 위도 테스트"""
        data = {
            "type": "coordinate_update",
            "prim_path": "/World/Husky_01",
            "latitude": 95.0,  # 범위 초과
            "longitude": 127.654321
        }
        with pytest.raises(ValidationError):
            CoordinateUpdateMessage(**data)
    
    def test_coordinate_update_message_invalid_longitude(self):
        """유효하지 않은 경도 테스트"""
        data = {
            "type": "coordinate_update", 
            "prim_path": "/World/Husky_01",
            "latitude": 37.123456,
            "longitude": 185.0  # 범위 초과
        }
        with pytest.raises(ValidationError):
            CoordinateUpdateMessage(**data)
    
    def test_select_object_message(self):
        """객체 선택 메시지 테스트"""
        data = {
            "type": "select_object",
            "prim_path": "/World/Husky_01"
        }
        msg = SelectObjectMessage(**data)
        assert msg.type == "select_object"
        assert msg.prim_path == "/World/Husky_01"
    
    def test_error_message(self):
        """에러 메시지 테스트"""
        data = {
            "type": "error",
            "error_code": "INVALID_MESSAGE_TYPE",
            "error_message": "Unknown message type"
        }
        msg = ErrorMessage(**data)
        assert msg.error_code == "INVALID_MESSAGE_TYPE"
        assert msg.error_message == "Unknown message type"
    
    def test_ack_message(self):
        """확인 메시지 테스트"""
        data = {
            "type": "ack",
            "original_type": "client_register",
            "status": "success"
        }
        msg = AckMessage(**data)
        assert msg.original_type == "client_register"
        assert msg.status == "success"