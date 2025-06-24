"""
Configuration management for Cesium Digital Twin Extension
"""

import carb


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
    
    def __init__(self):
        self.settings = carb.settings.get_settings()
        
    def get_websocket_url(self) -> str:
        """WebSocket 서버 URL 가져오기"""
        return self.settings.get(self.WEBSOCKET_URL) or "ws://localhost:8000/ws"
        
    def get_update_interval(self) -> float:
        """업데이트 주기 가져오기 (초)"""
        return self.settings.get(self.UPDATE_INTERVAL) or 1.0
        
    def get_auto_connect(self) -> bool:
        """자동 연결 설정 가져오기"""
        return self.settings.get(self.AUTO_CONNECT) or True
        
    def get_debug_mode(self) -> bool:
        """디버그 모드 설정 가져오기"""
        return self.settings.get(self.DEBUG_MODE) or False
        
    def get_tracked_objects(self) -> list:
        """추적할 객체 목록 가져오기"""
        objects = self.settings.get(self.TRACKED_OBJECTS)
        if objects:
            return list(objects)
        return ["/World/Husky_01", "/World/Husky_02"]  # 기본값
        
    def get_show_window_on_startup(self) -> bool:
        """시작 시 윈도우 표시 설정"""
        return self.settings.get(self.SHOW_WINDOW_ON_STARTUP) or True
        
    def get_window_size(self) -> tuple:
        """윈도우 크기 가져오기"""
        width = self.settings.get(self.WINDOW_WIDTH) or 400
        height = self.settings.get(self.WINDOW_HEIGHT) or 600
        return (width, height)
        
    def get_log_level(self) -> str:
        """로그 레벨 가져오기"""
        return self.settings.get(self.LOG_LEVEL) or "INFO"
        
    def get_log_websocket_messages(self) -> bool:
        """WebSocket 메시지 로깅 설정"""
        return self.settings.get(self.LOG_WEBSOCKET_MESSAGES) or False
        
    def set_websocket_url(self, url: str):
        """WebSocket URL 설정"""
        self.settings.set(self.WEBSOCKET_URL, url)
        
    def set_update_interval(self, interval: float):
        """업데이트 주기 설정"""
        self.settings.set(self.UPDATE_INTERVAL, interval)
        
    def set_tracked_objects(self, objects: list):
        """추적 객체 목록 설정"""
        self.settings.set(self.TRACKED_OBJECTS, objects)