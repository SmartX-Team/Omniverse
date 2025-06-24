"""
Logging utilities for Cesium Digital Twin Extension
"""

import carb
import time
import json
from typing import Any, Dict, Optional, List
from enum import Enum


class LogLevel(Enum):
    """로그 레벨 열거형"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Logger:
    """Extension 전용 로거 클래스"""
    
    def __init__(self, name: str = "CesiumDigitalTwin"):
        self.logger = carb.log.get_log()
        self.name = name
        self.log_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
        
        # 성능 모니터링
        self.performance_logs = []
        self.max_performance_logs = 100
        
    def _add_to_history(self, level: str, message: str, timestamp: float = None):
        """로그 히스토리에 추가"""
        if timestamp is None:
            timestamp = time.time()
            
        entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "module": self.name
        }
        
        self.log_history.append(entry)
        
        # 히스토리 크기 제한
        if len(self.log_history) > self.max_history_size:
            self.log_history.pop(0)
            
    def debug(self, message: str, *args: Any):
        """디버그 메시지 로깅"""
        formatted_message = f"[{self.name}] {message}" % args if args else f"[{self.name}] {message}"
        self.logger.debug(formatted_message)
        self._add_to_history("DEBUG", message)
        
    def info(self, message: str, *args: Any):
        """정보 메시지 로깅"""
        formatted_message = f"[{self.name}] {message}" % args if args else f"[{self.name}] {message}"
        self.logger.info(formatted_message)
        self._add_to_history("INFO", message)
        
    def warning(self, message: str, *args: Any):
        """경고 메시지 로깅"""
        formatted_message = f"[{self.name}] {message}" % args if args else f"[{self.name}] {message}"
        self.logger.warn(formatted_message)
        self._add_to_history("WARNING", message)
        
    def error(self, message: str, *args: Any, exc_info: Optional[Exception] = None):
        """에러 메시지 로깅"""
        formatted_message = f"[{self.name}] {message}" % args if args else f"[{self.name}] {message}"
        
        if exc_info:
            formatted_message += f" | Exception: {str(exc_info)}"
            
        self.logger.error(formatted_message)
        self._add_to_history("ERROR", message)
        
    def websocket_debug(self, action: str, data: Dict[str, Any] = None):
        """WebSocket 관련 디버그 로깅"""
        if data:
            # 민감한 데이터 마스킹
            safe_data = self._mask_sensitive_data(data)
            message = f"WebSocket {action}: {json.dumps(safe_data, indent=2)}"
        else:
            message = f"WebSocket {action}"
            
        self.debug(message)
        
    def coordinate_debug(self, prim_path: str, lat: float, lng: float, height: float):
        """좌표 관련 디버그 로깅"""
        message = f"Coordinates [{prim_path}]: {lat:.6f}, {lng:.6f}, {height:.1f}m"
        self.debug(message)
        
    def performance_log(self, operation: str, duration: float, details: Dict[str, Any] = None):
        """성능 로그 기록"""
        entry = {
            "timestamp": time.time(),
            "operation": operation,
            "duration": duration,
            "details": details or {}
        }
        
        self.performance_logs.append(entry)
        
        # 성능 로그 크기 제한
        if len(self.performance_logs) > self.max_performance_logs:
            self.performance_logs.pop(0)
            
        # 느린 작업 경고
        if duration > 1.0:  # 1초 이상
            self.warning(f"Slow operation detected: {operation} took {duration:.3f}s")
        elif duration > 0.5:  # 0.5초 이상
            self.debug(f"Operation timing: {operation} took {duration:.3f}s")
            
    def connection_log(self, event: str, details: Dict[str, Any] = None):
        """연결 관련 로그"""
        message = f"Connection {event}"
        if details:
            safe_details = self._mask_sensitive_data(details)
            message += f": {json.dumps(safe_details)}"
            
        self.info(message)
        
    def error_with_context(self, message: str, context: Dict[str, Any] = None, 
                          exc_info: Optional[Exception] = None):
        """컨텍스트 정보와 함께 에러 로깅"""
        full_message = message
        
        if context:
            safe_context = self._mask_sensitive_data(context)
            full_message += f" | Context: {json.dumps(safe_context)}"
            
        self.error(full_message, exc_info=exc_info)
        
    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """민감한 데이터 마스킹"""
        if not isinstance(data, dict):
            return data
            
        masked_data = data.copy()
        sensitive_keys = ['password', 'token', 'key', 'secret', 'auth']
        
        for key, value in masked_data.items():
            if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                if isinstance(value, str) and len(value) > 4:
                    masked_data[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
                else:
                    masked_data[key] = "***"
            elif isinstance(value, dict):
                masked_data[key] = self._mask_sensitive_data(value)
                
        return masked_data
        
    def get_log_history(self, level: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """로그 히스토리 조회"""
        history = self.log_history
        
        if level:
            history = [entry for entry in history if entry["level"] == level]
            
        if limit > 0:
            history = history[-limit:]
            
        return history
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 조회"""
        if not self.performance_logs:
            return {"total_operations": 0}
            
        durations = [log["duration"] for log in self.performance_logs]
        operations = [log["operation"] for log in self.performance_logs]
        
        # 작업별 통계
        operation_stats = {}
        for operation in set(operations):
            op_durations = [log["duration"] for log in self.performance_logs if log["operation"] == operation]
            operation_stats[operation] = {
                "count": len(op_durations),
                "avg_duration": sum(op_durations) / len(op_durations),
                "max_duration": max(op_durations),
                "min_duration": min(op_durations)
            }
            
        return {
            "total_operations": len(self.performance_logs),
            "avg_duration": sum(durations) / len(durations),
            "max_duration": max(durations),
            "min_duration": min(durations),
            "operations": operation_stats,
            "slow_operations_count": len([d for d in durations if d > 1.0])
        }
        
    def clear_history(self):
        """로그 히스토리 클리어"""
        self.log_history.clear()
        self.performance_logs.clear()
        self.info("Log history cleared")
        
    def export_logs(self, filepath: str, include_performance: bool = True) -> bool:
        """로그를 파일로 내보내기"""
        try:
            export_data = {
                "timestamp": time.time(),
                "logger_name": self.name,
                "log_history": self.log_history
            }
            
            if include_performance:
                export_data["performance_logs"] = self.performance_logs
                export_data["performance_stats"] = self.get_performance_stats()
                
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            self.info(f"Logs exported to: {filepath}")
            return True
            
        except Exception as e:
            self.error(f"Failed to export logs: {e}", exc_info=e)
            return False
            
    def set_log_level_filter(self, min_level: LogLevel):
        """최소 로그 레벨 설정 (구현 예정)"""
        # Carb 로깅 시스템의 레벨 필터링 구현
        pass
        
    def create_child_logger(self, child_name: str) -> 'Logger':
        """자식 로거 생성"""
        full_name = f"{self.name}.{child_name}"
        return Logger(full_name)


# 특수 목적 로거들
class ComponentLogger(Logger):
    """컴포넌트별 로거"""
    
    def __init__(self, component_name: str):
        super().__init__(f"CesiumDigitalTwin.{component_name}")
        self.component_name = component_name
        
    def component_info(self, message: str, *args: Any):
        """컴포넌트 정보 로깅"""
        self.info(f"[{self.component_name}] {message}", *args)
        
    def component_error(self, message: str, *args: Any, exc_info: Optional[Exception] = None):
        """컴포넌트 에러 로깅"""
        self.error(f"[{self.component_name}] {message}", *args, exc_info=exc_info)


class NetworkLogger(Logger):
    """네트워크 관련 로거"""
    
    def __init__(self):
        super().__init__("CesiumDigitalTwin.Network")
        
    def connection_attempt(self, url: str, attempt: int):
        """연결 시도 로깅"""
        self.info(f"Connection attempt #{attempt} to {url}")
        
    def connection_success(self, url: str, duration: float):
        """연결 성공 로깅"""
        self.info(f"Successfully connected to {url} in {duration:.3f}s")
        
    def connection_failure(self, url: str, error: str):
        """연결 실패 로깅"""
        self.error(f"Failed to connect to {url}: {error}")
        
    def message_sent(self, message_type: str, size: int):
        """메시지 전송 로깅"""
        self.debug(f"Sent {message_type} message ({size} bytes)")
        
    def message_received(self, message_type: str, size: int):
        """메시지 수신 로깅"""
        self.debug(f"Received {message_type} message ({size} bytes)")


# 전역 로거 인스턴스들
logger = Logger()
component_logger = ComponentLogger
network_logger = NetworkLogger()

# 컴포넌트별 로거 팩토리 함수
def get_component_logger(component_name: str) -> ComponentLogger:
    """컴포넌트 로거 생성"""
    return ComponentLogger(component_name)

def get_network_logger() -> NetworkLogger:
    """네트워크 로거 반환"""
    return network_logger