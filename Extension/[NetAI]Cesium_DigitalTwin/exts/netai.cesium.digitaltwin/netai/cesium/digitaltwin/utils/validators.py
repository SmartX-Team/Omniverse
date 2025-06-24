"""
Validation utilities for Cesium Digital Twin Extension
"""

import re
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urlparse

from .logger import logger


class ValidationError(Exception):
    """유효성 검증 에러"""
    def __init__(self, message: str, field: str = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(message)


class CoordinateValidator:
    """좌표 유효성 검증"""
    
    @staticmethod
    def validate_latitude(latitude: Union[int, float]) -> bool:
        """위도 유효성 검증"""
        try:
            lat = float(latitude)
            return -90.0 <= lat <= 90.0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_longitude(longitude: Union[int, float]) -> bool:
        """경도 유효성 검증"""
        try:
            lng = float(longitude)
            return -180.0 <= lng <= 180.0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_height(height: Union[int, float]) -> bool:
        """높이 유효성 검증"""
        try:
            h = float(height)
            # 지구 중심 기준 -12000m ~ +50000m (마리아나 해구 ~ 성층권)
            return -12000.0 <= h <= 50000.0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_coordinates(coordinates: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """좌표 딕셔너리 전체 검증"""
        errors = []
        
        # 필수 필드 확인
        required_fields = ['latitude', 'longitude']
        for field in required_fields:
            if field not in coordinates:
                errors.append(f"Missing required field: {field}")
                continue
        
        # 위도 검증
        if 'latitude' in coordinates:
            if not CoordinateValidator.validate_latitude(coordinates['latitude']):
                errors.append(f"Invalid latitude: {coordinates['latitude']}")
        
        # 경도 검증
        if 'longitude' in coordinates:
            if not CoordinateValidator.validate_longitude(coordinates['longitude']):
                errors.append(f"Invalid longitude: {coordinates['longitude']}")
        
        # 높이 검증 (선택적)
        if 'height' in coordinates:
            if not CoordinateValidator.validate_height(coordinates['height']):
                errors.append(f"Invalid height: {coordinates['height']}")
        
        return len(errors) == 0, errors


class PrimPathValidator:
    """Prim 경로 유효성 검증"""
    
    # USD Prim 경로 정규 표현식
    PRIM_PATH_PATTERN = re.compile(r'^/[\w/]+$')
    VALID_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    
    @staticmethod
    def validate_prim_path(prim_path: str) -> bool:
        """Prim 경로 기본 형식 검증"""
        if not isinstance(prim_path, str):
            return False
        
        if not prim_path.startswith('/'):
            return False
        
        if prim_path == '/':
            return True  # Root path
        
        # 경로 분할 및 각 부분 검증
        parts = prim_path.strip('/').split('/')
        for part in parts:
            if not part:  # 빈 부분 (연속된 슬래시)
                return False
            if not PrimPathValidator.VALID_NAME_PATTERN.match(part):
                return False
        
        return True
    
    @staticmethod
    def validate_prim_path_list(prim_paths: List[str]) -> Tuple[bool, List[str], List[str]]:
        """Prim 경로 리스트 검증"""
        valid_paths = []
        invalid_paths = []
        
        for path in prim_paths:
            if PrimPathValidator.validate_prim_path(path):
                valid_paths.append(path)
            else:
                invalid_paths.append(path)
        
        return len(invalid_paths) == 0, valid_paths, invalid_paths
    
    @staticmethod
    def normalize_prim_path(prim_path: str) -> str:
        """Prim 경로 정규화"""
        if not isinstance(prim_path, str):
            raise ValidationError("Prim path must be a string", "prim_path", prim_path)
        
        # 앞뒤 공백 제거
        normalized = prim_path.strip()
        
        # 루트 경로 처리
        if normalized == '' or normalized == '/':
            return '/'
        
        # 시작 슬래시 확인
        if not normalized.startswith('/'):
            normalized = '/' + normalized
        
        # 끝 슬래시 제거
        if normalized.endswith('/') and normalized != '/':
            normalized = normalized.rstrip('/')
        
        # 연속된 슬래시 제거
        while '//' in normalized:
            normalized = normalized.replace('//', '/')
        
        return normalized


class WebSocketValidator:
    """WebSocket 관련 유효성 검증"""
    
    @staticmethod
    def validate_websocket_url(url: str) -> bool:
        """WebSocket URL 유효성 검증"""
        if not isinstance(url, str):
            return False
        
        try:
            parsed = urlparse(url)
            
            # 스키마 확인
            if parsed.scheme not in ['ws', 'wss']:
                return False
            
            # 호스트 확인
            if not parsed.hostname:
                return False
            
            # 포트 확인 (선택적)
            if parsed.port is not None:
                if not (1 <= parsed.port <= 65535):
                    return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def validate_message_structure(message: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """WebSocket 메시지 구조 검증"""
        errors = []
        
        # 기본 타입 확인
        if not isinstance(message, dict):
            errors.append("Message must be a dictionary")
            return False, errors
        
        # 필수 필드 확인
        if 'type' not in message:
            errors.append("Message must have 'type' field")
        
        # 타입 필드 검증
        if 'type' in message:
            if not isinstance(message['type'], str):
                errors.append("Message type must be a string")
            elif not message['type'].strip():
                errors.append("Message type cannot be empty")
        
        # 타임스탬프 검증 (선택적)
        if 'timestamp' in message:
            if not isinstance(message['timestamp'], (int, float)):
                errors.append("Timestamp must be a number")
            elif message['timestamp'] <= 0:
                errors.append("Timestamp must be positive")
        
        return len(errors) == 0, errors


class ConfigValidator:
    """설정 값 유효성 검증"""
    
    @staticmethod
    def validate_update_interval(interval: Union[int, float]) -> bool:
        """업데이트 주기 검증"""
        try:
            interval_val = float(interval)
            return 0.1 <= interval_val <= 3600.0  # 0.1초 ~ 1시간
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_window_size(width: int, height: int) -> bool:
        """윈도우 크기 검증"""
        try:
            w, h = int(width), int(height)
            return (300 <= w <= 3840) and (400 <= h <= 2160)  # 최소~4K 해상도
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_log_level(level: str) -> bool:
        """로그 레벨 검증"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        return isinstance(level, str) and level.upper() in valid_levels
    
    @staticmethod
    def validate_retry_settings(max_retries: int, retry_delay: float) -> Tuple[bool, List[str]]:
        """재시도 설정 검증"""
        errors = []
        
        try:
            retries = int(max_retries)
            if not (1 <= retries <= 20):
                errors.append("Max retries must be between 1 and 20")
        except (ValueError, TypeError):
            errors.append("Max retries must be an integer")
        
        try:
            delay = float(retry_delay)
            if not (0.1 <= delay <= 300.0):
                errors.append("Retry delay must be between 0.1 and 300 seconds")
        except (ValueError, TypeError):
            errors.append("Retry delay must be a number")
        
        return len(errors) == 0, errors


class MessageValidator:
    """메시지별 특수 검증"""
    
    @staticmethod
    def validate_coordinate_update_message(message: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """좌표 업데이트 메시지 검증"""
        errors = []
        
        # 기본 구조 검증
        is_valid, struct_errors = WebSocketValidator.validate_message_structure(message)
        errors.extend(struct_errors)
        
        # 필수 필드 확인
        required_fields = ['prim_path', 'latitude', 'longitude']
        for field in required_fields:
            if field not in message:
                errors.append(f"Missing required field: {field}")
        
        # Prim 경로 검증
        if 'prim_path' in message:
            if not PrimPathValidator.validate_prim_path(message['prim_path']):
                errors.append(f"Invalid prim_path: {message['prim_path']}")
        
        # 좌표 검증
        coord_data = {k: v for k, v in message.items() if k in ['latitude', 'longitude', 'height']}
        if coord_data:
            is_coord_valid, coord_errors = CoordinateValidator.validate_coordinates(coord_data)
            errors.extend(coord_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_select_object_message(message: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """객체 선택 메시지 검증"""
        errors = []
        
        # 기본 구조 검증
        is_valid, struct_errors = WebSocketValidator.validate_message_structure(message)
        errors.extend(struct_errors)
        
        # 필수 필드 확인
        if 'prim_path' not in message:
            errors.append("Missing required field: prim_path")
        elif not PrimPathValidator.validate_prim_path(message['prim_path']):
            errors.append(f"Invalid prim_path: {message['prim_path']}")
        
        # 액션 검증 (선택적)
        if 'action' in message:
            valid_actions = ['select', 'clear', 'toggle', 'focus', 'select_and_focus', 'add_to_selection']
            if message['action'] not in valid_actions:
                errors.append(f"Invalid action: {message['action']}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_client_register_message(message: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """클라이언트 등록 메시지 검증"""
        errors = []
        
        # 기본 구조 검증
        is_valid, struct_errors = WebSocketValidator.validate_message_structure(message)
        errors.extend(struct_errors)
        
        # 필수 필드 확인
        if 'client_type' not in message:
            errors.append("Missing required field: client_type")
        elif not isinstance(message['client_type'], str):
            errors.append("client_type must be a string")
        
        # 메타데이터 검증 (선택적)
        if 'metadata' in message:
            if not isinstance(message['metadata'], dict):
                errors.append("metadata must be a dictionary")
        
        return len(errors) == 0, errors


class DataSanitizer:
    """데이터 정제 및 안전화"""
    
    @staticmethod
    def sanitize_coordinates(coordinates: Dict[str, Any]) -> Dict[str, Any]:
        """좌표 데이터 정제"""
        sanitized = {}
        
        # 위도 정제
        if 'latitude' in coordinates:
            try:
                lat = float(coordinates['latitude'])
                sanitized['latitude'] = max(-90.0, min(90.0, lat))
            except (ValueError, TypeError):
                logger.warning(f"Invalid latitude value: {coordinates['latitude']}")
        
        # 경도 정제
        if 'longitude' in coordinates:
            try:
                lng = float(coordinates['longitude'])
                # 경도를 -180~180 범위로 정규화
                lng = lng % 360
                if lng > 180:
                    lng -= 360
                sanitized['longitude'] = lng
            except (ValueError, TypeError):
                logger.warning(f"Invalid longitude value: {coordinates['longitude']}")
        
        # 높이 정제
        if 'height' in coordinates:
            try:
                height = float(coordinates['height'])
                sanitized['height'] = max(-12000.0, min(50000.0, height))
            except (ValueError, TypeError):
                sanitized['height'] = 0.0
        
        # 메타데이터 복사 (안전한 것만)
        if 'metadata' in coordinates and isinstance(coordinates['metadata'], dict):
            sanitized['metadata'] = coordinates['metadata'].copy()
        
        return sanitized
    
    @staticmethod
    def sanitize_prim_path(prim_path: str) -> str:
        """Prim 경로 정제"""
        try:
            return PrimPathValidator.normalize_prim_path(prim_path)
        except ValidationError:
            logger.warning(f"Failed to sanitize prim path: {prim_path}")
            return "/World/UnknownObject"
    
    @staticmethod
    def sanitize_message(message: Dict[str, Any]) -> Dict[str, Any]:
        """메시지 전체 정제"""
        sanitized = {}
        
        # 기본 필드들
        safe_fields = ['type', 'timestamp', 'prim_path', 'latitude', 'longitude', 
                      'height', 'metadata', 'action', 'client_type', 'status']
        
        for field in safe_fields:
            if field in message:
                sanitized[field] = message[field]
        
        # Prim 경로 정제
        if 'prim_path' in sanitized:
            sanitized['prim_path'] = DataSanitizer.sanitize_prim_path(sanitized['prim_path'])
        
        # 좌표 정제
        if any(field in sanitized for field in ['latitude', 'longitude', 'height']):
            coord_data = {k: v for k, v in sanitized.items() if k in ['latitude', 'longitude', 'height']}
            sanitized_coords = DataSanitizer.sanitize_coordinates(coord_data)
            sanitized.update(sanitized_coords)
        
        return sanitized


# 편의 함수들
def validate_coordinate_message(message: Dict[str, Any]) -> bool:
    """좌표 메시지 간단 검증"""
    is_valid, _ = MessageValidator.validate_coordinate_update_message(message)
    return is_valid

def validate_prim_path(prim_path: str) -> bool:
    """Prim 경로 간단 검증"""
    return PrimPathValidator.validate_prim_path(prim_path)

def validate_websocket_url(url: str) -> bool:
    """WebSocket URL 간단 검증"""
    return WebSocketValidator.validate_websocket_url(url)

def sanitize_input(data: Any) -> Any:
    """입력 데이터 일반 정제"""
    if isinstance(data, dict):
        return DataSanitizer.sanitize_message(data)
    elif isinstance(data, str) and data.startswith('/'):
        return DataSanitizer.sanitize_prim_path(data)
    else:
        return data