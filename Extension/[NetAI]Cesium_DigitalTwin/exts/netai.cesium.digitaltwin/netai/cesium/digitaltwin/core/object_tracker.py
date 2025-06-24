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
    
    def __init__(self, coordinate_reader: Optional[CoordinateReader] = None):
        self.config = Config()
        self.coordinate_reader = coordinate_reader or CoordinateReader()
        self.tracked_objects = self.config.get_tracked_objects()
        self.update_interval = self.config.get_update_interval()
        
        # 상태 관리
        self.is_running = False
        self.is_tracking = False
        self.tracking_task = None
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
        
        # 유효한 객체들만 추적하도록 필터링
        self._validate_tracked_objects()
        
        logger.info(f"ObjectTracker initialized with {len(self.tracked_objects)} objects")
        
    def _validate_tracked_objects(self):
        """추적 객체들의 유효성 검증"""
        try:
            valid_objects = self.coordinate_reader.validate_prim_paths(self.tracked_objects)
            if len(valid_objects) != len(self.tracked_objects):
                invalid_count = len(self.tracked_objects) - len(valid_objects)
                logger.warning(f"Found {invalid_count} invalid prim paths in tracked objects")
                self.tracked_objects = valid_objects
                self.config.set_tracked_objects(valid_objects)
        except Exception as e:
            logger.error(f"Error validating tracked objects: {e}")
        
    def add_coordinate_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """좌표 업데이트 콜백 추가"""
        if callback not in self.coordinate_callbacks:
            self.coordinate_callbacks.append(callback)
            logger.debug(f"Coordinate callback added. Total: {len(self.coordinate_callbacks)}")
        
    def add_error_callback(self, callback: Callable[[str, Exception], None]):
        """에러 콜백 추가"""
        if callback not in self.error_callbacks:
            self.error_callbacks.append(callback)
            logger.debug(f"Error callback added. Total: {len(self.error_callbacks)}")
        
    def remove_coordinate_callback(self, callback: Callable):
        """좌표 업데이트 콜백 제거"""
        if callback in self.coordinate_callbacks:
            self.coordinate_callbacks.remove(callback)
            logger.debug(f"Coordinate callback removed. Total: {len(self.coordinate_callbacks)}")
            
    def remove_error_callback(self, callback: Callable):
        """에러 콜백 제거"""
        if callback in self.error_callbacks:
            self.error_callbacks.remove(callback)
            logger.debug(f"Error callback removed. Total: {len(self.error_callbacks)}")
            
    def set_tracked_objects(self, prim_paths: List[str]):
        """추적할 객체 목록 설정"""
        # 유효성 검증 후 설정
        valid_paths = self.coordinate_reader.validate_prim_paths(prim_paths)
        self.tracked_objects = valid_paths.copy()
        self.config.set_tracked_objects(valid_paths)
        
        # 기존 좌표 캐시 정리 (새로운 객체 목록에 없는 것들)
        self._cleanup_coordinate_cache(valid_paths)
        
        logger.info(f"Tracked objects updated: {len(valid_paths)} valid objects")
        if len(valid_paths) != len(prim_paths):
            invalid_count = len(prim_paths) - len(valid_paths)
            logger.warning(f"Excluded {invalid_count} invalid prim paths")
        
    def _cleanup_coordinate_cache(self, current_objects: List[str]):
        """좌표 캐시 정리"""
        try:
            objects_to_remove = []
            for prim_path in self.last_coordinates.keys():
                if prim_path not in current_objects:
                    objects_to_remove.append(prim_path)
                    
            for prim_path in objects_to_remove:
                del self.last_coordinates[prim_path]
                
            if objects_to_remove:
                logger.debug(f"Cleaned up coordinate cache for {len(objects_to_remove)} objects")
                
        except Exception as e:
            logger.error(f"Error cleaning up coordinate cache: {e}")
        
    def set_update_interval(self, interval: float):
        """업데이트 주기 설정"""
        old_interval = self.update_interval
        self.update_interval = max(0.1, interval)  # 최소 0.1초
        self.config.set_update_interval(self.update_interval)
        
        logger.info(f"Update interval changed from {old_interval} to {self.update_interval} seconds")
        
    def start_tracking(self):
        """추적 시작"""
        if self.is_tracking:
            logger.warning("Tracking is already running")
            return
            
        if not self.tracked_objects:
            logger.warning("No objects to track")
            return
            
        if not self.coordinate_reader.test_connection():
            logger.error("Cannot start tracking: CoordinateReader test failed")
            return
            
        self.is_tracking = True
        self.stats["start_time"] = time.time()
        logger.info(f"Object tracking started for {len(self.tracked_objects)} objects")
        
    def stop_tracking(self):
        """추적 중지"""
        if not self.is_tracking:
            logger.warning("Tracking is not running")
            return
            
        self.is_tracking = False
        
        # 추적 태스크 취소
        if self.tracking_task and not self.tracking_task.done():
            self.tracking_task.cancel()
            
        logger.info("Object tracking stopped")
        
    async def tracking_loop(self):
        """추적 메인 루프 (비동기)"""
        if not self.is_tracking:
            logger.warning("Tracking is not started. Call start_tracking() first.")
            return
            
        self.is_running = True
        logger.info("Tracking loop started")
        
        try:
            while self.is_running and self.is_tracking:
                await self._update_all_coordinates()
                await asyncio.sleep(self.update_interval)
                
        except asyncio.CancelledError:
            logger.info("Tracking loop was cancelled")
        except Exception as e:
            logger.error(f"Tracking loop error: {e}")
            self._notify_error("tracking_loop", e)
            
        finally:
            self.is_running = False
            logger.info("Tracking loop stopped")
            
    async def _update_all_coordinates(self):
        """모든 추적 객체의 좌표 업데이트"""
        if not self.tracked_objects:
            return
            
        self.stats["total_updates"] += 1
        self.stats["last_update_time"] = time.time()
        
        try:
            # 모든 객체의 좌표를 한 번에 읽기 (배치 처리)
            coordinates_batch = self.coordinate_reader.get_multiple_coordinates(self.tracked_objects)
            
            # 각 객체별로 처리
            successful_updates = 0
            failed_updates = 0
            
            for prim_path in self.tracked_objects:
                try:
                    if prim_path in coordinates_batch:
                        coordinates = coordinates_batch[prim_path]
                        await self._process_coordinate_update(prim_path, coordinates)
                        successful_updates += 1
                    else:
                        # 좌표를 읽지 못한 경우
                        failed_updates += 1
                        if self.config.get_debug_mode():
                            logger.debug(f"No coordinates available for {prim_path}")
                            
                except Exception as e:
                    failed_updates += 1
                    logger.error(f"Error processing {prim_path}: {e}")
                    self._notify_error(prim_path, e)
                    
            # 통계 업데이트
            self.stats["successful_reads"] += successful_updates
            self.stats["failed_reads"] += failed_updates
            
            if self.config.get_debug_mode():
                logger.debug(f"Coordinate update: {successful_updates} success, {failed_updates} failed")
                    
        except Exception as e:
            logger.error(f"Error in coordinate batch update: {e}")
            self._notify_error("batch_update", e)
            
    async def _process_coordinate_update(self, prim_path: str, coordinates: Dict[str, Any]):
        """개별 좌표 업데이트 처리"""
        try:
            # 좌표 변화 감지
            last_coords = self.last_coordinates.get(prim_path)
            coordinates_changed = False
            
            if last_coords:
                coordinates_changed = self._coordinates_changed(last_coords, coordinates)
                if coordinates_changed:
                    logger.debug(f"Coordinates changed for {prim_path}")
                    coordinates["metadata"]["position_changed"] = True
                    coordinates["metadata"]["last_position_change"] = time.time()
                else:
                    # 변화가 없으면 메타데이터만 업데이트
                    coordinates["metadata"]["position_changed"] = False
                    coordinates["metadata"]["last_position_change"] = last_coords.get("metadata", {}).get("last_position_change")
            else:
                # 첫 번째 좌표 읽기
                coordinates_changed = True
                coordinates["metadata"]["position_changed"] = True
                coordinates["metadata"]["last_position_change"] = time.time()
                
            # 좌표 저장
            self.last_coordinates[prim_path] = coordinates.copy()
            
            # 콜백 호출 (좌표가 변했거나 첫 번째 읽기인 경우만)
            if coordinates_changed or not last_coords:
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
            total_reads = stats["successful_reads"] + stats["failed_reads"]
            if total_reads > 0:
                stats["success_rate"] = stats["successful_reads"] / total_reads
            else:
                stats["success_rate"] = 0.0
        else:
            stats["uptime"] = 0.0
            stats["success_rate"] = 0.0
            
        stats["is_tracking"] = self.is_tracking
        stats["is_running"] = self.is_running
        stats["tracked_objects_count"] = len(self.tracked_objects)
        stats["update_interval"] = self.update_interval
        stats["coordinate_reader_status"] = self.coordinate_reader.get_status()
        
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
        
    def add_tracked_object(self, prim_path: str):
        """단일 추적 객체 추가"""
        if prim_path not in self.tracked_objects:
            # 유효성 검증
            valid_paths = self.coordinate_reader.validate_prim_paths([prim_path])
            if valid_paths:
                self.tracked_objects.append(prim_path)
                self.config.set_tracked_objects(self.tracked_objects)
                logger.info(f"Added tracked object: {prim_path}")
            else:
                logger.warning(f"Cannot add invalid prim path: {prim_path}")
        else:
            logger.warning(f"Object already tracked: {prim_path}")
            
    def remove_tracked_object(self, prim_path: str):
        """단일 추적 객체 제거"""
        if prim_path in self.tracked_objects:
            self.tracked_objects.remove(prim_path)
            self.config.set_tracked_objects(self.tracked_objects)
            
            # 좌표 캐시에서도 제거
            if prim_path in self.last_coordinates:
                del self.last_coordinates[prim_path]
                
            logger.info(f"Removed tracked object: {prim_path}")
        else:
            logger.warning(f"Object not in tracked list: {prim_path}")
            
    def has_coordinates(self, prim_path: str) -> bool:
        """특정 객체의 좌표가 캐시되어 있는지 확인"""
        return prim_path in self.last_coordinates
        
    def cleanup(self):
        """정리 작업"""
        self.stop_tracking()
        self.is_running = False
        
        # 콜백 정리
        self.coordinate_callbacks.clear()
        self.error_callbacks.clear()
        
        # 캐시 정리
        self.last_coordinates.clear()
        
        # CoordinateReader 정리
        if self.coordinate_reader:
            self.coordinate_reader.cleanup()
            
        logger.info("ObjectTracker cleaned up")