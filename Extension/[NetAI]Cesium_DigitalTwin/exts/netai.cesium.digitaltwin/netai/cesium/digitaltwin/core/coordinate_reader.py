"""
Coordinate reading module using Cesium Globe Anchor API
"""

import time
import omni.usd
from pxr import Sdf, UsdGeom
from typing import Optional, Dict, Any, List

from ..utils.logger import logger

# Cesium import with fallback
try:
    from cesium.usd.plugins.CesiumUsdSchemas import GlobeAnchorAPI
    CESIUM_AVAILABLE = True
    logger.info("Cesium for Omniverse extension loaded successfully")
except ImportError:
    GlobeAnchorAPI = None
    CESIUM_AVAILABLE = False
    logger.warning("Cesium for Omniverse extension not available")


class CoordinateReader:
    """Globe Anchor API를 사용한 좌표 읽기 클래스"""
    
    def __init__(self):
        self.stage = None
        self._update_stage_reference()
        
        # 성능 최적화를 위한 캐시
        self._prim_cache = {}
        self._anchor_cache = {}
        
    def _update_stage_reference(self):
        """Stage 참조 업데이트"""
        try:
            context = omni.usd.get_context()
            if context:
                self.stage = context.get_stage()
                if self.stage:
                    logger.debug("Stage reference updated successfully")
                    # Stage가 변경되면 캐시 클리어
                    self._clear_cache()
                else:
                    logger.warning("Stage is not available")
            else:
                logger.warning("USD context is not available")
        except Exception as e:
            logger.error(f"Failed to update stage reference: {e}")
            self.stage = None
            
    def _clear_cache(self):
        """캐시 클리어"""
        self._prim_cache.clear()
        self._anchor_cache.clear()
        
    def is_cesium_available(self) -> bool:
        """Cesium 확장 사용 가능 여부 확인"""
        return CESIUM_AVAILABLE
        
    def get_object_coordinates(self, prim_path: str) -> Optional[Dict[str, Any]]:
        """
        특정 객체의 지리적 좌표 가져오기
        
        Args:
            prim_path: 객체의 Prim 경로 (예: "/World/Husky_01")
            
        Returns:
            좌표 정보 딕셔너리 또는 None
        """
        if not self.is_cesium_available():
            logger.warning("Cesium extension is not available")
            return None
            
        # Stage 참조 확인 및 업데이트
        if not self.stage:
            self._update_stage_reference()
            if not self.stage:
                return None
                
        try:
            # Prim 가져오기 (캐시 활용)
            prim = self._get_prim_cached(prim_path)
            if not prim or not prim.IsValid():
                logger.debug(f"Prim not found or invalid: {prim_path}")
                return None
                
            # Globe Anchor API 적용 (캐시 활용)
            anchor = self._get_anchor_cached(prim_path, prim)
            if not anchor:
                logger.warning(f"Failed to apply Globe Anchor API to {prim_path}")
                return None
                
            # 좌표 읽기
            latitude_attr = anchor.GetAnchorLatitudeAttr()
            longitude_attr = anchor.GetAnchorLongitudeAttr()
            height_attr = anchor.GetAnchorHeightAttr()
            
            if not latitude_attr or not longitude_attr:
                logger.warning(f"Latitude or longitude attributes not found for {prim_path}")
                return None
                
            latitude = latitude_attr.Get()
            longitude = longitude_attr.Get()
            height = height_attr.Get() if height_attr else 0.0
            
            if latitude is None or longitude is None:
                logger.debug(f"Coordinates not set for {prim_path}")
                return None
                
            # 좌표 유효성 검증
            if not self._validate_coordinates(latitude, longitude):
                logger.warning(f"Invalid coordinates for {prim_path}: {latitude}, {longitude}")
                return None
                
            # 메타데이터 수집
            metadata = self._collect_metadata(prim, prim_path)
            
            coordinates = {
                "latitude": float(latitude),
                "longitude": float(longitude),
                "height": float(height),
                "metadata": metadata
            }
            
            logger.coordinate_debug(prim_path, latitude, longitude, height)
            return coordinates
            
        except Exception as e:
            logger.error(f"Error reading coordinates for {prim_path}: {e}")
            return None
            
    def _get_prim_cached(self, prim_path: str):
        """캐시된 Prim 가져오기"""
        if prim_path not in self._prim_cache:
            prim = self.stage.GetPrimAtPath(Sdf.Path(prim_path))
            if prim.IsValid():
                self._prim_cache[prim_path] = prim
            else:
                return None
        return self._prim_cache[prim_path]
        
    def _get_anchor_cached(self, prim_path: str, prim):
        """캐시된 Globe Anchor 가져오기"""
        if prim_path not in self._anchor_cache:
            try:
                anchor = GlobeAnchorAPI.Apply(prim)
                if anchor:
                    self._anchor_cache[prim_path] = anchor
                else:
                    return None
            except Exception as e:
                logger.error(f"Error applying Globe Anchor to {prim_path}: {e}")
                return None
        return self._anchor_cache[prim_path]
        
    def _validate_coordinates(self, latitude: float, longitude: float) -> bool:
        """좌표 유효성 검증"""
        return (-90.0 <= latitude <= 90.0) and (-180.0 <= longitude <= 180.0)
        
    def _collect_metadata(self, prim, prim_path: str) -> Dict[str, Any]:
        """객체의 메타데이터 수집"""
        metadata = {
            "timestamp": time.time(),
            "prim_name": prim.GetName(),
            "prim_path": prim_path,
            "prim_type": prim.GetTypeName()
        }
        
        try:
            # Transform 정보 수집
            if prim.IsA(UsdGeom.Xformable):
                xformable = UsdGeom.Xformable(prim)
                transform_matrix = xformable.GetLocalTransformation()
                
                # 변환 행렬에서 회전 정보 추출 (heading 계산)
                import math
                from pxr import Gf
                
                # 회전 추출 (간단한 Y축 회전만 계산)
                rotation = transform_matrix.ExtractRotation()
                # 실제로는 더 복잡한 계산이 필요할 수 있음
                
            # 사용자 정의 속성 읽기
            self._collect_custom_attributes(prim, metadata)
            
            # 시뮬레이션 데이터 (실제 환경에서는 로봇 API 연동)
            self._add_simulation_data(metadata)
            
        except Exception as e:
            logger.error(f"Error collecting metadata for {prim_path}: {e}")
            
        return metadata
        
    def _collect_custom_attributes(self, prim, metadata: Dict[str, Any]):
        """사용자 정의 속성 수집"""
        try:
            # 일반적인 로봇 속성들 확인
            attribute_names = [
                "battery_level", "speed", "status", "heading", 
                "linear_velocity", "angular_velocity"
            ]
            
            for attr_name in attribute_names:
                attr = prim.GetAttribute(attr_name)
                if attr and attr.IsValid():
                    value = attr.Get()
                    if value is not None:
                        metadata[attr_name] = value
                        
        except Exception as e:
            logger.debug(f"Error collecting custom attributes: {e}")
            
    def _add_simulation_data(self, metadata: Dict[str, Any]):
        """시뮬레이션 데이터 추가 (실제 환경에서는 제거)"""
        try:
            import random
            
            # 실제 로봇 상태가 없을 때 시뮬레이션 데이터
            if "battery_level" not in metadata:
                metadata["battery_level"] = random.randint(20, 100)
                
            if "speed" not in metadata:
                metadata["speed"] = round(random.uniform(0, 5), 1)
                
            if "status" not in metadata:
                metadata["status"] = random.choice(["idle", "moving", "charging", "working"])
                
            if "heading" not in metadata:
                metadata["heading"] = round(random.uniform(0, 360), 1)
                
            metadata["last_update"] = time.time()
            
        except Exception as e:
            logger.debug(f"Error adding simulation data: {e}")
        
    def get_multiple_coordinates(self, prim_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        여러 객체의 좌표를 한 번에 가져오기 (배치 처리)
        
        Args:
            prim_paths: Prim 경로 리스트
            
        Returns:
            {prim_path: coordinates_dict} 형태의 딕셔너리
        """
        results = {}
        
        if not prim_paths:
            return results
            
        logger.debug(f"Reading coordinates for {len(prim_paths)} objects")
        
        # Stage 참조 확인
        if not self.stage:
            self._update_stage_reference()
            if not self.stage:
                logger.error("Stage not available for batch coordinate reading")
                return results
        
        # 배치 처리로 성능 최적화
        start_time = time.time()
        
        for prim_path in prim_paths:
            coords = self.get_object_coordinates(prim_path)
            if coords:
                results[prim_path] = coords
                
        elapsed_time = time.time() - start_time
        logger.debug(f"Batch coordinate reading completed in {elapsed_time:.3f}s")
        
        return results
        
    def validate_prim_paths(self, prim_paths: List[str]) -> List[str]:
        """
        Prim 경로들의 유효성 검증
        
        Args:
            prim_paths: 검증할 Prim 경로 리스트
            
        Returns:
            유효한 Prim 경로 리스트
        """
        valid_paths = []
        
        if not self.stage:
            self._update_stage_reference()
            if not self.stage:
                return valid_paths
                
        for prim_path in prim_paths:
            try:
                prim = self.stage.GetPrimAtPath(Sdf.Path(prim_path))
                if prim.IsValid():
                    valid_paths.append(prim_path)
                else:
                    logger.warning(f"Invalid prim path: {prim_path}")
            except Exception as e:
                logger.error(f"Error validating prim path {prim_path}: {e}")
                
        return valid_paths
        
    def has_globe_anchor(self, prim_path: str) -> bool:
        """
        객체가 Globe Anchor를 가지고 있는지 확인
        
        Args:
            prim_path: 확인할 객체의 Prim 경로
            
        Returns:
            Globe Anchor 존재 여부
        """
        if not self.is_cesium_available() or not self.stage:
            return False
            
        try:
            prim = self._get_prim_cached(prim_path)
            if not prim or not prim.IsValid():
                return False
                
            anchor = GlobeAnchorAPI.Get(prim)  # Apply 대신 Get 사용
            return anchor is not None
            
        except Exception as e:
            logger.debug(f"Error checking Globe Anchor for {prim_path}: {e}")
            return False
        
    def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            if not self.is_cesium_available():
                logger.error("Test failed: Cesium extension not available")
                return False
                
            if not self.stage:
                self._update_stage_reference()
                if not self.stage:
                    logger.error("Test failed: Stage not available")
                    return False
                    
            logger.info("CoordinateReader test passed")
            return True
            
        except Exception as e:
            logger.error(f"CoordinateReader test failed: {e}")
            return False
            
    def get_status(self) -> Dict[str, Any]:
        """CoordinateReader 상태 정보"""
        return {
            "cesium_available": self.is_cesium_available(),
            "stage_available": self.stage is not None,
            "cached_prims": len(self._prim_cache),
            "cached_anchors": len(self._anchor_cache)
        }
        
    def cleanup(self):
        """정리 작업"""
        self._clear_cache()
        self.stage = None
        logger.info("CoordinateReader cleaned up")