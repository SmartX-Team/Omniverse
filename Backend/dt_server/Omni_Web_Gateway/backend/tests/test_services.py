import pytest
from unittest.mock import Mock, patch

from app.models.client import ClientType
from app.services.coordinate_service import CoordinateService
from app.services.message_router import MessageRouter


class TestCoordinateService:
    """좌표 서비스 테스트"""
    
    def test_coordinate_validation(self):
        """좌표 검증 테스트"""
        service = CoordinateService()
        
        # 유효한 좌표
        assert service.validate_coordinates(37.123, 127.456) is True
        
        # 유효하지 않은 위도
        assert service.validate_coordinates(95.0, 127.456) is False
        assert service.validate_coordinates(-95.0, 127.456) is False
        
        # 유효하지 않은 경도
        assert service.validate_coordinates(37.123, 185.0) is False
        assert service.validate_coordinates(37.123, -185.0) is False
    
    def test_coordinate_conversion(self):
        """좌표 변환 테스트"""
        service = CoordinateService()
        
        # 도, 분, 초를 십진도로 변환 - 정확한 값으로 수정
        lat_dms = (37, 7, 24.4416)  # 서울 위도
        lng_dms = (127, 39, 14.7576)  # 서울 경도
        
        lat_decimal = service.dms_to_decimal(*lat_dms)
        lng_decimal = service.dms_to_decimal(*lng_dms)
        
        # 실제 계산 결과와 비교
        assert abs(lat_decimal - 37.123456) < 0.001
        assert abs(lng_decimal - 127.654099) < 0.001  # 정확한 값으로 수정
    
    def test_distance_calculation(self):
        """거리 계산 테스트"""
        service = CoordinateService()
        
        # 서울시청과 광화문 사이 거리 (약 200m)
        lat1, lng1 = 37.5665, 126.9780  # 서울시청
        lat2, lng2 = 37.5658, 126.9769  # 광화문
        
        distance = service.calculate_distance(lat1, lng1, lat2, lng2)
        
        # 약 100-300m 범위 내여야 함
        assert 100 < distance < 300


class TestMessageRouter:
    """메시지 라우터 테스트"""
    
    def test_route_coordinate_update(self):
        """좌표 업데이트 라우팅 테스트"""
        router = MessageRouter()
        
        message = {
            "type": "coordinate_update",
            "prim_path": "/World/Husky_01",
            "latitude": 37.123,
            "longitude": 127.456
        }
        
        route = router.get_message_route("omniverse_extension", message)
        assert route == "broadcast_to_web_clients"
    
    def test_route_select_object(self):
        """객체 선택 라우팅 테스트"""
        router = MessageRouter()
        
        message = {
            "type": "select_object",
            "prim_path": "/World/Husky_01"
        }
        
        route = router.get_message_route("web_ui", message)
        assert route == "send_to_omniverse_clients"
    
    def test_invalid_message_route(self):
        """유효하지 않은 메시지 라우팅 테스트"""
        router = MessageRouter()
        
        message = {
            "type": "unknown_type"
        }
        
        route = router.get_message_route("web_ui", message)
        assert route is None