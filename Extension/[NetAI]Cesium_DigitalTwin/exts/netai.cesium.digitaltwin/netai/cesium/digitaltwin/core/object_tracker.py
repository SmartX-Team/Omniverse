"""
Object tracking management module
"""

import asyncio
import time
from typing import List, Dict, Any, Callable, Optional

from .coordinate_reader import CoordinateReader
from ..utils.logger import logger
from ..utils.config import Config


class ObjectTracker:
    """객체 추적 관리 클래스"""
    
    def __init__(self):
        self.config = Config()
        self.coordinate_reader = CoordinateReader()
        self.tracked_objects = self.config.get_tracked_objects()
        self.update_interval = self.config.get_update_interval()
        
        # 상태 관리
        self.is_running = False
        self.is_tracking = False
        self.last_coordinates = {}
        
        # 콜백 함수들
        self.coordinate_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        
        # 통계 정보
        self.stats = {
            "total_updates": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "start_time": None,
            "last_update_time": None
        }
        
        logger.info(f"ObjectTracker initialized with {len(self.tracked_objects)} objects")
        
    def add_coordinate_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """좌표 업데이트 콜백 추가"""
        self.coordinate_callbacks.append(callback)
        logger.debug(f"Coordinate callback added. Total: {len(self.coordinate_callbacks)}")
        
    def add_error_callback(self, callback: Callable[[str, Exception], None]):
        """에러 콜백 추가"""
        self.error_callbacks.append(callback)
        logger.debug(f"Error callback added. Total: {len(self.error_callbacks)}")
        
    def remove_coordinate_callback(self, callback: Callable):
        """좌표 업데이트 콜백 제거"""
        if callback in self.coordinate_callbacks:
            self.coordinate_callbacks.remove(callback)
            logger.debug(f"Coordinate callback removed. Total: {len(self.coordinate_callbacks)}")
            
    def set_tracked_objects(self, prim_paths: List[str]):
        """추적할 객체 목록 설정"""
        self.tracked_objects = prim_paths.copy()
        self.config.set_tracked_objects(prim_paths)
        logger.info(f"Tracked objects updated: {self.tracked_objects}")
        
    def set_update_interval(self, interval: float):
        """업데이트 주기 설정"""
        self.update_interval = max(0.1, interval)  # 최소 0.1초
        self.config.set_update_interval(self.update_interval)
        logger.info(f"Update interval set to {self.update_interval} seconds")
        
    def start_tracking(self):
        """추적 시작"""
        if self.is_tracking:
            logger.warning("Tracking is already running")
            return
            
        if not self.coordinate_reader.test_connection():
            logger.error("Cannot start tracking: CoordinateReader test failed")
            return
            
        self.is_tracking = True
        self.stats["start_time"] = time.time()
        logger.info("Object tracking started")
        
    def stop_tracking(self):
        """추적 중지"""
        if not self.is_tracking:
            logger.warning("Tracking is not running")
            return
            
        self.is_tracking = False
        logger.info("Object tracking stopped")
        
    async def tracking_loop(self):
        """추적 메인 루프 (비동기)"""
        self.is_running = True
        logger.info("Tracking loop started")
        
        try:
            while self.is_running and self.is_tracking:
                await self._update_all_coordinates()
                await asyncio.sleep(self.update_interval)
                
        except Exception as e:
            logger.error(f"Tracking loop error: {e}")
            self._notify_error("tracking_loop", e)
            
        finally:
            self.is_running = False
            logger.info("Tracking loop stopped")
            
    async def _update_all_coordinates(self):
        """모든 추적 객체의 좌표 업데이트"""
        self.stats["total_updates"] += 1
        self.stats["last_update_time"] = time.time()
        
        try:
            # 모든 객체의 좌표를 한 번에 읽기
            coordinates_batch = self.coordinate_reader.get_multiple_coordinates(self.tracked_objects)
            
            # 각 객체별로 처리
            for prim_path in self.tracked_objects:
                try:
                    if prim_path in coordinates_batch:
                        coordinates = coordinates_batch[prim_path]
                        await self._process_coordinate_update(prim_path, coordinates)
                        self.stats["successful_reads"] += 1
                    else:
                        # 좌표를 읽지 못한 경우
                        self.stats["failed_reads"] += 1
                        if self.config.get_debug_mode():
                            logger.debug(f"No coordinates available for {prim_path}")
                            
                except Exception as e:
                    self.stats["failed_reads"] += 1
                    logger.error(f"Error processing {prim_path}: {e}")
                    self._notify_error(prim_path, e)
                    
        except Exception as e:
            logger.error(f"Error in coordinate batch update: {e}")
            self._notify_error("batch_update", e)
            
    async def _process_coordinate_update(self, prim_path: str, coordinates: Dict[str, Any]):
        """개별 좌표 업데이트 처리"""
        try:
            # 좌표 변화 감지
            last_coords = self.last_coordinates.get(prim_path)
            if last_coords and self._coordinates_changed(last_coords, coordinates):
                logger.debug(f"Coordinates changed for {prim_path}")
            elif last_coords:
                # 변화가 없으면 메타데이터만 업데이트
                coordinates["metadata"].update({
                    "position_changed": False,
                    "last_position_change": last_coords.get("metadata", {}).get("last_position_change")
                })
            else:
                # 첫 번째 좌표 읽기
                coordinates["metadata"]["position_changed"] = True
                coordinates["metadata"]["last_position_change"] = time.time()
                
            # 좌표 저장
            self.last_coordinates[prim_path] = coordinates.copy()
            
            # 콜백 호출
            self._notify_coordinate_update(prim_path, coordinates)
            
        except Exception as e:
            logger.error(f"Error processing coordinate update for {prim_path}: {e}")
            self._notify_error(prim_path, e)
            
    def _coordinates_changed(self, old_coords: Dict, new_coords: Dict, threshold: float = 0.000001) -> bool:
        """좌표 변화 감지"""
        try:
            lat_diff = abs(old_coords["latitude"] - new_coords["latitude"])
            lng_diff = abs(old_coords["longitude"] - new_coords["longitude"])
            height_diff = abs(old_coords["height"] - new_coords["height"])
            
            return lat_diff > threshold or lng_diff > threshold or height_diff > 0.1
            
        except (KeyError, TypeError):
            return True  # 에러가 있으면 변화했다고 가정
            
    def _notify_coordinate_update(self, prim_path: str, coordinates: Dict[str, Any]):
        """좌표 업데이트 콜백 호출"""
        for callback in self.coordinate_callbacks:
            try:
                callback(prim_path, coordinates)
            except Exception as e:
                logger.error(f"Error in coordinate callback: {e}")
                
    def _notify_error(self, source: str, error: Exception):
        """에러 콜백 호출"""
        for callback in self.error_callbacks:
            try:
                callback(source, error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
                
    def get_last_coordinates(self, prim_path: str = None) -> Optional[Dict]:
        """마지막 좌표 가져오기"""
        if prim_path:
            return self.last_coordinates.get(prim_path)
        return self.last_coordinates.copy()
        
    def get_statistics(self) -> Dict[str, Any]:
        """추적 통계 정보 가져오기"""
        stats = self.stats.copy()
        
        if stats["start_time"]:
            stats["uptime"] = time.time() - stats["start_time"]
            if stats["total_updates"] > 0:
                stats["success_rate"] = stats["successful_reads"] / (stats["successful_reads"] + stats["failed_reads"])
            else:
                stats["success_rate"] = 0.0
        else:
            stats["uptime"] = 0.0
            stats["success_rate"] = 0.0
            
        stats["is_tracking"] = self.is_tracking
        stats["is_running"] = self.is_running
        stats["tracked_objects_count"] = len(self.tracked_objects)
        stats["update_interval"] = self.update_interval
        
        return stats
        
    def reset_statistics(self):
        """통계 정보 초기화"""
        self.stats = {
            "total_updates": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "start_time": time.time() if self.is_tracking else None,
            "last_update_time": None
        }
        logger.info("Statistics reset")
        
    def cleanup(self):
        """정리 작업"""
        self.stop_tracking()
        self.is_running = False
        self.coordinate_callbacks.clear()
        self.error_callbacks.clear()
        self.last_coordinates.clear()
        logger.info("ObjectTracker cleaned up")