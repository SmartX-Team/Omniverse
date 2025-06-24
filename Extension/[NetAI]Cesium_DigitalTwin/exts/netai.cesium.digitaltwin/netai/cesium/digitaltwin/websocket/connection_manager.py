"""
WebSocket connection management module
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable, List
from enum import Enum

from ..utils.logger import logger
from ..utils.config import Config


class ConnectionState(Enum):
    """연결 상태 열거형"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    REGISTERING = "registering"
    REGISTERED = "registered"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class ConnectionManager:
    """WebSocket 연결 관리 클래스"""
    
    def __init__(self):
        self.config = Config()
        
        # 연결 상태 관리
        self._state = ConnectionState.DISCONNECTED
        self._previous_state = ConnectionState.DISCONNECTED
        self._state_change_time = time.time()
        
        # 연결 설정
        self.server_url = self.config.get_websocket_url()
        self.max_retries = self.config.get_websocket_max_retries() or 5
        self.retry_delays = [1, 2, 4, 8, 16]  # 지수 백오프
        self.current_retry = 0
        
        # 연결 품질 모니터링
        self.connection_quality = {
            "latency": 0.0,
            "packet_loss": 0.0,
            "throughput": 0.0,
            "stability_score": 1.0
        }
        
        # 상태 변경 콜백
        self.state_change_callbacks: List[Callable] = []
        
        # 연결 히스토리
        self.connection_history = []
        self.max_history_size = 100
        
        logger.info("ConnectionManager initialized")
        
    def add_state_change_callback(self, callback: Callable[[ConnectionState, ConnectionState], None]):
        """상태 변경 콜백 추가"""
        if callback not in self.state_change_callbacks:
            self.state_change_callbacks.append(callback)
            logger.debug(f"State change callback added. Total: {len(self.state_change_callbacks)}")
            
    def remove_state_change_callback(self, callback: Callable):
        """상태 변경 콜백 제거"""
        if callback in self.state_change_callbacks:
            self.state_change_callbacks.remove(callback)
            logger.debug(f"State change callback removed. Total: {len(self.state_change_callbacks)}")
    
    @property
    def state(self) -> ConnectionState:
        """현재 연결 상태"""
        return self._state
        
    @property
    def is_connected(self) -> bool:
        """연결 여부"""
        return self._state in [ConnectionState.CONNECTED, ConnectionState.REGISTERED]
        
    @property
    def is_registered(self) -> bool:
        """등록 여부"""
        return self._state == ConnectionState.REGISTERED
        
    @property
    def can_send_messages(self) -> bool:
        """메시지 전송 가능 여부"""
        return self._state == ConnectionState.REGISTERED
        
    def set_state(self, new_state: ConnectionState, reason: str = ""):
        """연결 상태 변경"""
        if new_state != self._state:
            old_state = self._state
            self._previous_state = old_state
            self._state = new_state
            self._state_change_time = time.time()
            
            # 히스토리 추가
            self._add_to_history(old_state, new_state, reason)
            
            logger.info(f"Connection state changed: {old_state.value} -> {new_state.value} ({reason})")
            
            # 콜백 호출
            self._notify_state_change(old_state, new_state)
            
    def _add_to_history(self, old_state: ConnectionState, new_state: ConnectionState, reason: str):
        """연결 히스토리에 추가"""
        entry = {
            "timestamp": time.time(),
            "from_state": old_state.value,
            "to_state": new_state.value,
            "reason": reason,
            "retry_count": self.current_retry
        }
        
        self.connection_history.append(entry)
        
        # 히스토리 크기 제한
        if len(self.connection_history) > self.max_history_size:
            self.connection_history.pop(0)
            
    def _notify_state_change(self, old_state: ConnectionState, new_state: ConnectionState):
        """상태 변경 콜백 호출"""
        for callback in self.state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
                
    def get_retry_delay(self) -> float:
        """현재 재시도 지연 시간 계산"""
        if self.current_retry >= len(self.retry_delays):
            return self.retry_delays[-1]
        return self.retry_delays[self.current_retry]
        
    def should_retry(self) -> bool:
        """재시도 가능 여부 확인"""
        return self.current_retry < self.max_retries
        
    def increment_retry(self):
        """재시도 카운터 증가"""
        self.current_retry += 1
        logger.debug(f"Retry count incremented to {self.current_retry}")
        
    def reset_retry_count(self):
        """재시도 카운터 리셋"""
        if self.current_retry > 0:
            logger.debug(f"Retry count reset from {self.current_retry} to 0")
            self.current_retry = 0
            
    def update_connection_quality(self, latency: float = None, packet_loss: float = None, 
                                throughput: float = None):
        """연결 품질 업데이트"""
        if latency is not None:
            self.connection_quality["latency"] = latency
            
        if packet_loss is not None:
            self.connection_quality["packet_loss"] = packet_loss
            
        if throughput is not None:
            self.connection_quality["throughput"] = throughput
            
        # 안정성 점수 계산 (0.0 ~ 1.0)
        stability_score = 1.0
        
        # 지연시간 기반 점수 (100ms 이하면 만점)
        if latency is not None:
            if latency > 1000:  # 1초 이상
                stability_score *= 0.1
            elif latency > 500:  # 500ms 이상
                stability_score *= 0.5
            elif latency > 100:  # 100ms 이상
                stability_score *= 0.8
                
        # 패킷 손실 기반 점수
        if packet_loss is not None:
            stability_score *= (1.0 - min(packet_loss, 1.0))
            
        self.connection_quality["stability_score"] = stability_score
        
        if stability_score < 0.5:
            logger.warning(f"Connection quality degraded: {stability_score:.2f}")
            
    def get_connection_info(self) -> Dict[str, Any]:
        """현재 연결 정보"""
        state_duration = time.time() - self._state_change_time
        
        return {
            "state": self._state.value,
            "previous_state": self._previous_state.value,
            "state_duration": state_duration,
            "server_url": self.server_url,
            "retry_count": self.current_retry,
            "max_retries": self.max_retries,
            "next_retry_delay": self.get_retry_delay() if self.should_retry() else None,
            "connection_quality": self.connection_quality.copy(),
            "can_send_messages": self.can_send_messages
        }
        
    def get_connection_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """연결 히스토리 가져오기"""
        if limit <= 0:
            return self.connection_history.copy()
        return self.connection_history[-limit:]
        
    def get_uptime_stats(self) -> Dict[str, Any]:
        """업타임 통계 계산"""
        if not self.connection_history:
            return {
                "total_uptime": 0.0,
                "connection_count": 0,
                "average_session_duration": 0.0,
                "longest_session": 0.0,
                "shortest_session": 0.0
            }
            
        total_uptime = 0.0
        session_durations = []
        current_session_start = None
        
        for i, entry in enumerate(self.connection_history):
            if entry["to_state"] in ["connected", "registered"]:
                current_session_start = entry["timestamp"]
            elif entry["to_state"] in ["disconnected", "error"] and current_session_start:
                session_duration = entry["timestamp"] - current_session_start
                session_durations.append(session_duration)
                total_uptime += session_duration
                current_session_start = None
                
        # 현재 연결 중인 세션 포함
        if current_session_start and self.is_connected:
            current_session_duration = time.time() - current_session_start
            session_durations.append(current_session_duration)
            total_uptime += current_session_duration
            
        stats = {
            "total_uptime": total_uptime,
            "connection_count": len(session_durations),
            "average_session_duration": sum(session_durations) / len(session_durations) if session_durations else 0.0,
            "longest_session": max(session_durations) if session_durations else 0.0,
            "shortest_session": min(session_durations) if session_durations else 0.0
        }
        
        return stats
        
    def diagnose_connection_issues(self) -> Dict[str, Any]:
        """연결 문제 진단"""
        issues = []
        recommendations = []
        
        # 연결 품질 체크
        quality = self.connection_quality
        if quality["latency"] > 1000:
            issues.append("High latency detected")
            recommendations.append("Check network connection")
            
        if quality["packet_loss"] > 0.1:
            issues.append("High packet loss detected")
            recommendations.append("Check network stability")
            
        if quality["stability_score"] < 0.5:
            issues.append("Poor connection stability")
            recommendations.append("Consider using a more stable network")
            
        # 재시도 패턴 분석
        if self.current_retry >= self.max_retries:
            issues.append("Max retries reached")
            recommendations.append("Check server availability")
            
        # 최근 연결 히스토리 분석
        recent_history = self.get_connection_history(10)
        if len(recent_history) > 5:
            error_count = sum(1 for entry in recent_history if entry["to_state"] == "error")
            if error_count > 3:
                issues.append("Frequent connection errors")
                recommendations.append("Check server logs and network configuration")
                
        return {
            "issues": issues,
            "recommendations": recommendations,
            "severity": "high" if len(issues) >= 3 else "medium" if issues else "low"
        }
        
    def update_server_url(self, new_url: str):
        """서버 URL 업데이트"""
        if new_url != self.server_url:
            old_url = self.server_url
            self.server_url = new_url
            self.config.set_websocket_url(new_url)
            
            logger.info(f"Server URL updated from {old_url} to {new_url}")
            
            # 연결 중이면 재연결 필요 상태로 설정
            if self.is_connected:
                self.set_state(ConnectionState.RECONNECTING, "Server URL changed")
                
    def force_reconnect(self, reason: str = "Manual reconnect"):
        """강제 재연결"""
        logger.info(f"Force reconnect requested: {reason}")
        self.reset_retry_count()
        
        if self.is_connected:
            self.set_state(ConnectionState.RECONNECTING, reason)
        else:
            self.set_state(ConnectionState.CONNECTING, reason)
            
    def cleanup(self):
        """정리 작업"""
        self.set_state(ConnectionState.DISCONNECTED, "Cleanup")
        self.state_change_callbacks.clear()
        self.connection_history.clear()
        logger.info("ConnectionManager cleaned up")