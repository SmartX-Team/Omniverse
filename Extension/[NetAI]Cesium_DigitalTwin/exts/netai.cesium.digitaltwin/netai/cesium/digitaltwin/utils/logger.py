"""
Logging utilities for Cesium Digital Twin Extension
"""

import carb
from typing import Any


class Logger:
    """Extension 전용 로거 클래스"""
    
    def __init__(self, name: str = "CesiumDigitalTwin"):
        self.logger = carb.log.get_log()
        self.name = name
        
    def debug(self, message: str, *args: Any):
        """디버그 메시지 로깅"""
        self.logger.debug(f"[{self.name}] {message}", *args)
        
    def info(self, message: str, *args: Any):
        """정보 메시지 로깅"""
        self.logger.info(f"[{self.name}] {message}", *args)
        
    def warning(self, message: str, *args: Any):
        """경고 메시지 로깅"""
        self.logger.warn(f"[{self.name}] {message}", *args)
        
    def error(self, message: str, *args: Any):
        """에러 메시지 로깅"""
        self.logger.error(f"[{self.name}] {message}", *args)
        
    def websocket_debug(self, message: str, data: dict = None):
        """WebSocket 관련 디버그 로깅"""
        if data:
            self.debug(f"WebSocket: {message} - {data}")
        else:
            self.debug(f"WebSocket: {message}")
            
    def coordinate_debug(self, prim_path: str, lat: float, lng: float, height: float):
        """좌표 관련 디버그 로깅"""
        self.debug(f"Coordinates [{prim_path}]: {lat:.6f}, {lng:.6f}, {height:.1f}m")


# 전역 로거 인스턴스
logger = Logger()