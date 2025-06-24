"""
Configuration management for Cesium Digital Twin Extension
"""

import carb
from typing import List, Tuple, Any, Optional, Dict
import json

from .logger import logger


class Config:
    """Extension 설정 관리 클래스"""
    
    # 설정 키 상수들
    WEBSOCKET_URL = "exts/netai.cesium.digitaltwin/websocket_url"
    UPDATE_INTERVAL = "exts/netai.cesium.digitaltwin/update_interval"
    AUTO_CONNECT = "exts/netai.cesium.digitaltwin/auto_connect"
    DEBUG_MODE = "exts/netai.cesium.digitaltwin/debug_mode"
    TRACKED_OBJECTS = "exts/netai.cesium.digitaltwin/tracked_objects"
    SHOW_WINDOW_ON_STARTUP = "exts/netai.cesium.digitaltwin/show_window_on_startup"
    WINDOW_WIDTH = "exts/netai.cesium.digitaltwin/window_width"
    WINDOW_HEIGHT = "exts/netai.cesium.digitaltwin/window_height"
    LOG_LEVEL = "exts/netai.cesium.digitaltwin/log_level"
    LOG_WEBSOCKET_MESSAGES = "exts/netai.cesium.digitaltwin/log_websocket_messages"
    
    # WebSocket 관련 추가 설정
    WEBSOCKET_MAX_RETRIES = "exts/netai.cesium.digitaltwin/websocket_max_retries"
    WEBSOCKET_RETRY_DELAY = "exts/netai.cesium.digitaltwin/websocket_retry_delay"
    WEBSOCKET_CONNECT_TIMEOUT = "exts/netai.cesium.digitaltwin/websocket_connect_timeout"
    WEBSOCKET_PING_INTERVAL = "exts/netai.cesium.digitaltwin/websocket_ping_interval"
    
    # 좌표 관련 설정
    COORDINATE_PRECISION = "exts/netai.cesium.digitaltwin/coordinate_precision"
    COORDINATE_CHANGE_THRESHOLD = "exts/netai.cesium.digitaltwin/coordinate_change_threshold"
    
    # UI 관련 설정
    UI_UPDATE_INTERVAL = "exts/netai.cesium.digitaltwin/ui_update_interval"
    STATISTICS_DISPLAY_ENABLED = "exts/netai.cesium.digitaltwin/statistics_display_enabled"
    
    def __init__(self):
        self.settings = carb.settings.get_settings()
        self._init_default_values()
        
    def _init_default_values(self):
        """기본값 설정"""
        defaults = {
            self.WEBSOCKET_URL: "ws://localhost:8000/ws",
            self.UPDATE_INTERVAL: 1.0,
            self.AUTO_CONNECT: True,
            self.DEBUG_MODE: False,
            self.TRACKED_OBJECTS: ["/World/Husky_01", "/World/Husky_02"],
            self.SHOW_WINDOW_ON_STARTUP: True,
            self.WINDOW_WIDTH: 400,
            self.WINDOW_HEIGHT: 600,
            self.LOG_LEVEL: "INFO",
            self.LOG_WEBSOCKET_MESSAGES: False,
            self.WEBSOCKET_MAX_RETRIES: 5,
            self.WEBSOCKET_RETRY_DELAY: 5.0,
            self.WEBSOCKET_CONNECT_TIMEOUT: 10.0,
            self.WEBSOCKET_PING_INTERVAL: 30.0,
            self.COORDINATE_PRECISION: 6,
            self.COORDINATE_CHANGE_THRESHOLD: 0.000001,
            self.UI_UPDATE_INTERVAL: 2.0,
            self.STATISTICS_DISPLAY_ENABLED: True
        }
        
        # 설정되지 않은 값들에 대해 기본값 설정
        for key, default_value in defaults.items():
            if self.settings.get(key) is None:
                self.settings.set(key, default_value)
                logger.debug(f"Set default config value: {key} = {default_value}")
        
    # WebSocket 설정
    def get_websocket_url(self) -> str:
        """WebSocket 서버 URL 가져오기"""
        return self.settings.get(self.WEBSOCKET_URL) or "ws://localhost:8000/ws"
        
    def set_websocket_url(self, url: str):
        """WebSocket URL 설정"""
        if self._validate_websocket_url(url):
            self.settings.set(self.WEBSOCKET_URL, url)
            logger.info(f"WebSocket URL updated: {url}")
        else:
            logger.error(f"Invalid WebSocket URL: {url}")
            
    def get_websocket_max_retries(self) -> int:
        """WebSocket 최대 재시도 횟수"""
        return self.settings.get(self.WEBSOCKET_MAX_RETRIES) or 5
        
    def get_websocket_retry_delay(self) -> float:
        """WebSocket 재시도 지연 시간"""
        return self.settings.get(self.WEBSOCKET_RETRY_DELAY) or 5.0
        
    def get_websocket_connect_timeout(self) -> float:
        """WebSocket 연결 타임아웃"""
        return self.settings.get(self.WEBSOCKET_CONNECT_TIMEOUT) or 10.0
        
    def get_websocket_ping_interval(self) -> float:
        """WebSocket ping 간격"""
        return self.settings.get(self.WEBSOCKET_PING_INTERVAL) or 30.0
        
    # 업데이트 설정
    def get_update_interval(self) -> float:
        """업데이트 주기 가져오기 (초)"""
        return max(0.1, self.settings.get(self.UPDATE_INTERVAL) or 1.0)
        
    def set_update_interval(self, interval: float):
        """업데이트 주기 설정"""
        if interval >= 0.1:
            self.settings.set(self.UPDATE_INTERVAL, interval)
            logger.info(f"Update interval set to: {interval}s")
        else:
            logger.error(f"Update interval must be >= 0.1s, got: {interval}")
            
    # 연결 설정
    def get_auto_connect(self) -> bool:
        """자동 연결 설정 가져오기"""
        return self.settings.get(self.AUTO_CONNECT) or True
        
    def set_auto_connect(self, enabled: bool):
        """자동 연결 설정"""
        self.settings.set(self.AUTO_CONNECT, enabled)
        logger.info(f"Auto connect set to: {enabled}")
        
    # 디버그 설정
    def get_debug_mode(self) -> bool:
        """디버그 모드 설정 가져오기"""
        return self.settings.get(self.DEBUG_MODE) or False
        
    def set_debug_mode(self, enabled: bool):
        """디버그 모드 설정"""
        self.settings.set(self.DEBUG_MODE, enabled)
        logger.info(f"Debug mode set to: {enabled}")
        
    # 추적 객체 설정
    def get_tracked_objects(self) -> List[str]:
        """추적할 객체 목록 가져오기"""
        objects = self.settings.get(self.TRACKED_OBJECTS)
        if isinstance(objects, list) and objects:
            return objects
        return ["/World/Husky_01", "/World/Husky_02"]  # 기본값
        
    def set_tracked_objects(self, objects: List[str]):
        """추적 객체 목록 설정"""
        if isinstance(objects, list):
            # 유효한 prim path만 필터링
            valid_objects = [obj for obj in objects if self._validate_prim_path(obj)]
            self.settings.set(self.TRACKED_OBJECTS, valid_objects)
            logger.info(f"Tracked objects updated: {len(valid_objects)} objects")
        else:
            logger.error("Tracked objects must be a list")
            
    def add_tracked_object(self, prim_path: str):
        """추적 객체 추가"""
        if self._validate_prim_path(prim_path):
            objects = self.get_tracked_objects()
            if prim_path not in objects:
                objects.append(prim_path)
                self.set_tracked_objects(objects)
                logger.info(f"Added tracked object: {prim_path}")
            else:
                logger.warning(f"Object already tracked: {prim_path}")
        else:
            logger.error(f"Invalid prim path: {prim_path}")
            
    def remove_tracked_object(self, prim_path: str):
        """추적 객체 제거"""
        objects = self.get_tracked_objects()
        if prim_path in objects:
            objects.remove(prim_path)
            self.set_tracked_objects(objects)
            logger.info(f"Removed tracked object: {prim_path}")
        else:
            logger.warning(f"Object not in tracked list: {prim_path}")
            
    # UI 설정
    def get_show_window_on_startup(self) -> bool:
        """시작 시 윈도우 표시 설정"""
        return self.settings.get(self.SHOW_WINDOW_ON_STARTUP) or True
        
    def get_window_size(self) -> Tuple[int, int]:
        """윈도우 크기 가져오기"""
        width = self.settings.get(self.WINDOW_WIDTH) or 400
        height = self.settings.get(self.WINDOW_HEIGHT) or 600
        return (max(300, width), max(400, height))  # 최소 크기 보장
        
    def set_window_size(self, width: int, height: int):
        """윈도우 크기 설정"""
        if width >= 300 and height >= 400:
            self.settings.set(self.WINDOW_WIDTH, width)
            self.settings.set(self.WINDOW_HEIGHT, height)
            logger.debug(f"Window size set to: {width}x{height}")
        else:
            logger.error(f"Invalid window size: {width}x{height}")
            
    def get_ui_update_interval(self) -> float:
        """UI 업데이트 주기"""
        return self.settings.get(self.UI_UPDATE_INTERVAL) or 2.0
        
    def get_statistics_display_enabled(self) -> bool:
        """통계 표시 활성화 여부"""
        return self.settings.get(self.STATISTICS_DISPLAY_ENABLED) or True
        
    # 로깅 설정
    def get_log_level(self) -> str:
        """로그 레벨 가져오기"""
        level = self.settings.get(self.LOG_LEVEL) or "INFO"
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        return level if level in valid_levels else "INFO"
        
    def set_log_level(self, level: str):
        """로그 레벨 설정"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if level in valid_levels:
            self.settings.set(self.LOG_LEVEL, level)
            logger.info(f"Log level set to: {level}")
        else:
            logger.error(f"Invalid log level: {level}")
            
    def get_log_websocket_messages(self) -> bool:
        """WebSocket 메시지 로깅 설정"""
        return self.settings.get(self.LOG_WEBSOCKET_MESSAGES) or False
        
    def set_log_websocket_messages(self, enabled: bool):
        """WebSocket 메시지 로깅 설정"""
        self.settings.set(self.LOG_WEBSOCKET_MESSAGES, enabled)
        logger.info(f"WebSocket message logging set to: {enabled}")
        
    # 좌표 관련 설정
    def get_coordinate_precision(self) -> int:
        """좌표 정밀도 (소수점 자릿수)"""
        return max(1, min(10, self.settings.get(self.COORDINATE_PRECISION) or 6))
        
    def get_coordinate_change_threshold(self) -> float:
        """좌표 변화 감지 임계값"""
        return self.settings.get(self.COORDINATE_CHANGE_THRESHOLD) or 0.000001
        
    # 설정 유효성 검증
    def _validate_websocket_url(self, url: str) -> bool:
        """WebSocket URL 유효성 검증"""
        if not isinstance(url, str):
            return False
        return url.startswith(('ws://', 'wss://')) and len(url) > 8
        
    def _validate_prim_path(self, prim_path: str) -> bool:
        """Prim 경로 유효성 검증"""
        if not isinstance(prim_path, str):
            return False
        return prim_path.startswith('/') and len(prim_path) > 1
        
    # 설정 내보내기/가져오기
    def export_settings(self) -> Dict[str, Any]:
        """현재 설정을 딕셔너리로 내보내기"""
        settings_keys = [
            self.WEBSOCKET_URL, self.UPDATE_INTERVAL, self.AUTO_CONNECT,
            self.DEBUG_MODE, self.TRACKED_OBJECTS, self.SHOW_WINDOW_ON_STARTUP,
            self.WINDOW_WIDTH, self.WINDOW_HEIGHT, self.LOG_LEVEL,
            self.LOG_WEBSOCKET_MESSAGES, self.WEBSOCKET_MAX_RETRIES,
            self.WEBSOCKET_RETRY_DELAY, self.WEBSOCKET_CONNECT_TIMEOUT,
            self.COORDINATE_PRECISION, self.COORDINATE_CHANGE_THRESHOLD
        ]
        
        settings_dict = {}
        for key in settings_keys:
            value = self.settings.get(key)
            if value is not None:
                # 키에서 prefix 제거하여 저장
                short_key = key.split('/')[-1]
                settings_dict[short_key] = value
                
        return settings_dict
        
    def import_settings(self, settings_dict: Dict[str, Any]) -> bool:
        """딕셔너리에서 설정 가져오기"""
        try:
            key_mapping = {
                'websocket_url': self.WEBSOCKET_URL,
                'update_interval': self.UPDATE_INTERVAL,
                'auto_connect': self.AUTO_CONNECT,
                'debug_mode': self.DEBUG_MODE,
                'tracked_objects': self.TRACKED_OBJECTS,
                'show_window_on_startup': self.SHOW_WINDOW_ON_STARTUP,
                'window_width': self.WINDOW_WIDTH,
                'window_height': self.WINDOW_HEIGHT,
                'log_level': self.LOG_LEVEL,
                'log_websocket_messages': self.LOG_WEBSOCKET_MESSAGES,
                'websocket_max_retries': self.WEBSOCKET_MAX_RETRIES,
                'websocket_retry_delay': self.WEBSOCKET_RETRY_DELAY,
                'websocket_connect_timeout': self.WEBSOCKET_CONNECT_TIMEOUT,
                'coordinate_precision': self.COORDINATE_PRECISION,
                'coordinate_change_threshold': self.COORDINATE_CHANGE_THRESHOLD
            }
            
            for short_key, value in settings_dict.items():
                if short_key in key_mapping:
                    full_key = key_mapping[short_key]
                    self.settings.set(full_key, value)
                    
            logger.info("Settings imported successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import settings: {e}")
            return False
            
    def reset_to_defaults(self):
        """설정을 기본값으로 리셋"""
        try:
            # 모든 설정 삭제
            settings_keys = [
                self.WEBSOCKET_URL, self.UPDATE_INTERVAL, self.AUTO_CONNECT,
                self.DEBUG_MODE, self.TRACKED_OBJECTS, self.SHOW_WINDOW_ON_STARTUP,
                self.WINDOW_WIDTH, self.WINDOW_HEIGHT, self.LOG_LEVEL,
                self.LOG_WEBSOCKET_MESSAGES, self.WEBSOCKET_MAX_RETRIES,
                self.WEBSOCKET_RETRY_DELAY, self.WEBSOCKET_CONNECT_TIMEOUT,
                self.COORDINATE_PRECISION, self.COORDINATE_CHANGE_THRESHOLD
            ]
            
            for key in settings_keys:
                self.settings.set(key, None)
                
            # 기본값 다시 설정
            self._init_default_values()
            
            logger.info("Settings reset to defaults")
            
        except Exception as e:
            logger.error(f"Failed to reset settings: {e}")
            
    def get_all_settings(self) -> Dict[str, Any]:
        """모든 설정 조회 (디버깅용)"""
        return {
            "websocket_url": self.get_websocket_url(),
            "update_interval": self.get_update_interval(),
            "auto_connect": self.get_auto_connect(),
            "debug_mode": self.get_debug_mode(),
            "tracked_objects": self.get_tracked_objects(),
            "show_window_on_startup": self.get_show_window_on_startup(),
            "window_size": self.get_window_size(),
            "log_level": self.get_log_level(),
            "log_websocket_messages": self.get_log_websocket_messages(),
            "websocket_max_retries": self.get_websocket_max_retries(),
            "websocket_retry_delay": self.get_websocket_retry_delay(),
            "coordinate_precision": self.get_coordinate_precision(),
            "coordinate_change_threshold": self.get_coordinate_change_threshold()
        }