"""
Coordinate reading module using Cesium Globe Anchor API
"""

import time
import omni.usd
from pxr import Sdf
from typing import Optional, Dict, Any

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
        
    def _update_stage_reference(self):
        """Stage 참조 업데이트"""
        try:
            context = omni.usd.get_context()
            if context:
                self.stage = context.get_stage()
                if self.stage:
                    logger.debug("Stage reference updated successfully")
                else:
                    logger.warning("Stage is not available")
            else:
                logger.warning("USD context is not available")
        except Exception as e:
            logger.error(f"Failed to update stage reference: {e}")
            self.stage = None
            
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
            # Prim 가져오기
            prim = self.stage.GetPrimAtPath(Sdf.Path(prim_path))
            if not prim.IsValid():
                logger.debug(f"Prim not found or invalid: {prim_path}")
                return None
                
            # Globe Anchor API 적용
            anchor = GlobeAnchorAPI.Apply(prim)
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
            from pxr import UsdGeom
            if prim.IsA(UsdGeom.Xformable):
                xformable = UsdGeom.Xformable(prim)
                transform = xformable.GetLocalTransformation()
                # 회전 정보에서 heading 계산 등 추가 가능
                
            # 사용자 정의 속성 읽기 (예: 속도, 배터리 상태 등)
            # 실제 구현에서는 로봇의 실제 속성들을 읽어야 함
            
            # 예시: 임시 데이터 (실제로는 로봇 상태 API 연동)
            import random
            metadata.update({
                "speed": round(random.uniform(0, 5), 1),
                "battery": random.randint(20, 100),
                "status": random.choice(["idle", "moving", "charging"]),
                "last_update": time.time()
            })
            
        except Exception as e:
            logger.error(f"Error collecting metadata for {prim_path}: {e}")
            
        return metadata
        
    def get_multiple_coordinates(self, prim_paths: list) -> Dict[str, Dict[str, Any]]:
        """
        여러 객체의 좌표를 한 번에 가져오기
        
        Args:
            prim_paths: Prim 경로 리스트
            
        Returns:
            {prim_path: coordinates_dict} 형태의 딕셔너리
        """
        results = {}
        
        for prim_path in prim_paths:
            coords = self.get_object_coordinates(prim_path)
            if coords:
                results[prim_path] = coords
                
        return results
        
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