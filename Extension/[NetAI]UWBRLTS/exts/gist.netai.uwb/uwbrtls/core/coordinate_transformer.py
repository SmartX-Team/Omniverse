import math
import numpy as np
from typing import Tuple, Dict, List, Optional, Any
from .db_manager import get_db_manager
from .config_manager import get_config_manager

class CoordinateTransformer:
    """좌표 변환 처리 클래스 v2"""
    
    def __init__(self):
        self.db_manager = get_db_manager()
        self.config_manager = get_config_manager()
        self.uwb_config = self.config_manager.get_uwb_config()
        self.omniverse_config = self.config_manager.get_omniverse_config()
        
        # 캐시된 매핑 정보
        self._coordinate_mapping = None
        self._calibration_points = None
        self._gps_reference_points = None
        self._space_id = self.uwb_config.get('default_space_id', 1)
    
    async def initialize(self, space_id: Optional[int] = None):
        """좌표 변환기 초기화 - DB에서 매핑 정보 로드"""
        if space_id is not None:
            self._space_id = space_id
        
        print(f"Initializing coordinate transformer for space_id: {self._space_id}")
        
        # 좌표 매핑 정보 로드
        self._coordinate_mapping = await self.db_manager.fetch_coordinate_mapping(self._space_id)
        if not self._coordinate_mapping:
            print(f"Warning: No coordinate mapping found for space_id {self._space_id}")
            return False
        
        # 캘리브레이션 포인트 로드
        mapping_id = self._coordinate_mapping['id']
        self._calibration_points = await self.db_manager.fetch_calibration_points(mapping_id)
        
        # GPS 기준점 로드
        self._gps_reference_points = await self.db_manager.fetch_gps_reference_points(self._space_id)
        
        print(f"Loaded {len(self._calibration_points)} calibration points and {len(self._gps_reference_points)} GPS reference points")
        return True
    
    def is_valid_uwb_coordinate(self, x: float, y: float) -> bool:
        """UWB 좌표가 유효한 범위 내에 있는지 확인"""
        if not self._coordinate_mapping:
            return True  # 매핑 정보가 없으면 기본적으로 허용
        
        min_x = self._coordinate_mapping.get('uwb_min_x', float('-inf'))
        max_x = self._coordinate_mapping.get('uwb_max_x', float('inf'))
        min_y = self._coordinate_mapping.get('uwb_min_y', float('-inf'))
        max_y = self._coordinate_mapping.get('uwb_max_y', float('inf'))
        
        return min_x <= x <= max_x and min_y <= y <= max_y
    

    def transform_uwb_to_omniverse_simple(self, uwb_x: float, uwb_y: float, input_height: Optional[float] = None) -> Tuple[float, float, float]:
        """간단한 변환 - coordinate_mapping 파라미터 사용"""
        precision = self.uwb_config.get('coordinate_precision', 2)
        
        # coordinate_mapping에서 변환 파라미터 가져오기 (없으면 기존 하드코딩 값)
        if self._coordinate_mapping:
            scale_x = self._coordinate_mapping.get('scale_x', -100.0)    
            scale_y = self._coordinate_mapping.get('scale_y', 100.0)     
            translate_x = self._coordinate_mapping.get('translate_x', 0.0)
            translate_y = self._coordinate_mapping.get('translate_y', 0.0)
            translate_z = self._coordinate_mapping.get('translate_z', None)
            rotation_z = self._coordinate_mapping.get('rotation_z', 0.0)
            print(f"Using coordinate_mapping params: scale_x={scale_x}, scale_y={scale_y}, translate_x={translate_x}, translate_y={translate_y}, translate_z={translate_z}, rotation_z={rotation_z}")
        else:
            # 매핑 정보가 없으면 기존 하드코딩된 값 사용
            scale_x = -100.0
            scale_y = 100.0
            translate_x = 0.0
            translate_y = 0.0
            translate_z = None
            rotation_z = 0.0
            print("No coordinate_mapping found, using hardcoded values: scale_x=-100, scale_y=100")
        
        # 회전 변환 적용 (필요한 경우)
        if rotation_z != 0:
            import math
            cos_r = math.cos(rotation_z)
            sin_r = math.sin(rotation_z)
            rotated_x = uwb_x * cos_r - uwb_y * sin_r
            rotated_y = uwb_x * sin_r + uwb_y * cos_r
            uwb_x, uwb_y = rotated_x, rotated_y
            print(f"Applied rotation {rotation_z} rad: ({uwb_x:.2f}, {uwb_y:.2f})")
        
        # 변환 공식 (파라미터 적용)
        omni_x = round(uwb_y * scale_x + translate_x, precision)  # UWB Y → Omni X
        omni_z = round(uwb_x * scale_y + translate_y, precision)  # UWB X → Omni Z
        
        # Y축 높이 결정 (우선순위: input_height > translate_z > 기본값)
        if input_height is not None:
            omni_y = round(input_height, precision)
        elif translate_z is not None:
            omni_y = round(translate_z, precision)
        else:
            omni_y = self.omniverse_config.get('default_y_height', 90.0)
        
        print(f"Simple transform: UWB({uwb_x:.2f}, {uwb_y:.2f}) → Omni({omni_x}, {omni_y}, {omni_z})")
        return omni_x, omni_y, omni_z
    
    def transform_uwb_to_omniverse_advanced(self, uwb_x: float, uwb_y: float, tag_id: str = None, input_height: Optional[float] = None) -> Tuple[float, float, float]:
        """고급 변환 - DB 매핑 정보 사용"""
        print("Warning: coordinate mapping available, using advance transform")
        if not self._coordinate_mapping:
            print("Warning: No coordinate mapping available, using simple transform")
            return self.transform_uwb_to_omniverse_simple(uwb_x, uwb_y, input_height)
        
        # 매핑 파라미터 적용
        scale_x = self._coordinate_mapping.get('scale_x', 1.0)
        scale_y = self._coordinate_mapping.get('scale_y', 1.0)
        translate_x = self._coordinate_mapping.get('translate_x', 0.0)
        translate_y = self._coordinate_mapping.get('translate_y', 0.0)
        translate_z = self._coordinate_mapping.get('translate_z', 0.0)
        rotation_z = self._coordinate_mapping.get('rotation_z', 0.0)
        
        # 회전 변환 적용
        if rotation_z != 0:
            cos_r = math.cos(rotation_z)
            sin_r = math.sin(rotation_z)
            rotated_x = uwb_x * cos_r - uwb_y * sin_r
            rotated_y = uwb_x * sin_r + uwb_y * cos_r
            uwb_x, uwb_y = rotated_x, rotated_y
        
        # 스케일링 및 평행이동
        omni_x = uwb_y * scale_x + translate_x
        omni_z = uwb_x * scale_y + translate_y
        
        # Y축 높이 결정 (우선순위: input_height > 태그별 특별 높이 > DB translate_z > 기본 높이)
        if input_height is not None:
            omni_y = input_height
        else:
            special_heights = self.omniverse_config.get('special_heights', {})
            if tag_id and tag_id in special_heights:
                omni_y = special_heights[tag_id]
            else:
                omni_y = self._coordinate_mapping.get('translate_z', 
                         self.omniverse_config.get('default_y_height', 90.0))
        
        precision = self.uwb_config.get('coordinate_precision', 2)
        return round(omni_x, precision), round(omni_y, precision), round(omni_z, precision)
    
    async def transform_uwb_to_omniverse(self, uwb_x: float, uwb_y: float, tag_id: str = None, input_height: Optional[float] = None) -> Tuple[float, float, float]:
        """UWB 좌표를 Omniverse 좌표로 변환"""
        # 좌표 유효성 검사
        if not self.is_valid_uwb_coordinate(uwb_x, uwb_y):
            print(f"Warning: UWB coordinate ({uwb_x}, {uwb_y}) is outside valid range")
        
        # 매핑 정보가 있으면 고급 변환, 없으면 간단한 변환 사용
        if self._coordinate_mapping:
            return self.transform_uwb_to_omniverse_advanced(uwb_x, uwb_y, tag_id, input_height)
        else:
            return self.transform_uwb_to_omniverse_simple(uwb_x, uwb_y, input_height)
    
    def transform_uwb_to_gps(self, uwb_x: float, uwb_y: float) -> Optional[Tuple[float, float]]:
        """UWB 좌표를 GPS 좌표로 변환"""
        if not self._gps_reference_points or len(self._gps_reference_points) < 2:
            print("Warning: Insufficient GPS reference points for coordinate transformation")
            return None
        
        # 최소 2개의 기준점으로 선형 변환 수행
        ref_points = self._gps_reference_points[:2]
        
        # 기준점 1과 2 사이의 UWB 및 GPS 벡터 계산
        uwb_vec = (ref_points[1]['uwb_x'] - ref_points[0]['uwb_x'],
                   ref_points[1]['uwb_y'] - ref_points[0]['uwb_y'])
        gps_vec = (ref_points[1]['longitude'] - ref_points[0]['longitude'],
                   ref_points[1]['latitude'] - ref_points[0]['latitude'])
        
        # 현재 점과 기준점 1 사이의 UWB 벡터
        current_uwb_vec = (uwb_x - ref_points[0]['uwb_x'],
                          uwb_y - ref_points[0]['uwb_y'])
        
        # 스케일 팩터 계산
        if uwb_vec[0] != 0 and uwb_vec[1] != 0:
            scale_x = gps_vec[0] / uwb_vec[0]
            scale_y = gps_vec[1] / uwb_vec[1]
            
            # GPS 좌표 계산
            gps_lon = ref_points[0]['longitude'] + current_uwb_vec[0] * scale_x
            gps_lat = ref_points[0]['latitude'] + current_uwb_vec[1] * scale_y
            
            return gps_lat, gps_lon
        
        return None
    
    async def transform_and_save(self, tag_id: str, input_x: float, input_y: float, 
                               space_id: int, raw_timestamp: str, 
                               input_height: Optional[float] = None) -> Tuple[float, float, float]:
        """좌표 변환 후 DB에 저장 (v2 - input_height 파라미터 추가)"""
        # Omniverse 좌표 변환
        omni_x, omni_y, omni_z = await self.transform_uwb_to_omniverse(
            input_x, input_y, tag_id, input_height
        )
        
        # GPS 좌표 변환 (선택사항)
        gps_coords = self.transform_uwb_to_gps(input_x, input_y)
        gps_lat, gps_lon = gps_coords if gps_coords else (None, None)
        
        # DB에 변환된 좌표 저장
        mapping_id = self._coordinate_mapping['id'] if self._coordinate_mapping else None
        await self.db_manager.save_transformed_coordinates(
            tag_id=tag_id,
            space_id=space_id,
            uwb_x=input_x,
            uwb_y=input_y,
            uwb_timestamp=raw_timestamp,
            omniverse_x=omni_x,
            omniverse_y=omni_y,
            omniverse_z=omni_z,
            mapping_id=mapping_id
        )
        
        return omni_x, omni_y, omni_z
    
    def calibrate_with_points(self, calibration_data: List[Dict[str, Any]]) -> bool:
        """캘리브레이션 포인트를 사용한 좌표계 보정"""
        if len(calibration_data) < 3:
            print("Warning: Need at least 3 calibration points for accurate transformation")
            return False
        
        try:
            # 최소자승법을 사용한 변환 매트릭스 계산
            uwb_points = np.array([[p['uwb_x'], p['uwb_y']] for p in calibration_data])
            omni_points = np.array([[p['omniverse_x'], p['omniverse_z']] for p in calibration_data])
            
            # 어파인 변환 매트릭스 계산 (A * uwb + b = omni)
            # [x'] = [a b] [x] + [tx]
            # [y'] = [c d] [y] + [ty]
            
            ones = np.ones((len(uwb_points), 1))
            A = np.hstack([uwb_points, ones])
            
            # 최소자승법으로 변환 매트릭스 계산
            transform_x = np.linalg.lstsq(A, omni_points[:, 0], rcond=None)[0]
            transform_y = np.linalg.lstsq(A, omni_points[:, 1], rcond=None)[0]
            
            # 변환 매트릭스 업데이트
            if self._coordinate_mapping:
                self._coordinate_mapping.update({
                    'scale_x': transform_x[1],  # b coefficient
                    'scale_y': transform_x[0],  # a coefficient  
                    'translate_x': transform_x[2],  # tx
                    'translate_y': transform_y[2],  # ty
                    'rotation_z': math.atan2(transform_y[0], transform_x[0])  # 회전각 추정
                })
                
                print("Coordinate mapping updated with calibration data")
                return True
            
        except Exception as e:
            print(f"Error in calibration: {e}")
        
        return False
    
    async def reload_mapping_data(self, space_id: Optional[int] = None):
        """매핑 데이터 다시 로드"""
        await self.initialize(space_id)
    
    def get_transform_info(self) -> Dict[str, Any]:
        """현재 변환 정보 반환"""
        if not self._coordinate_mapping:
            return {
                'space_id': self._space_id,
                'mapping_name': 'No mapping available',
                'status': 'Using simple transformation'
            }
        
        return {
            'space_id': self._space_id,
            'mapping_name': self._coordinate_mapping.get('mapping_name'),
            'status': 'Using advanced transformation',
            'uwb_bounds': {
                'min_x': self._coordinate_mapping.get('uwb_min_x'),
                'max_x': self._coordinate_mapping.get('uwb_max_x'),
                'min_y': self._coordinate_mapping.get('uwb_min_y'),
                'max_y': self._coordinate_mapping.get('uwb_max_y')
            },
            'transform_params': {
                'scale_x': self._coordinate_mapping.get('scale_x'),
                'scale_y': self._coordinate_mapping.get('scale_y'),
                'translate_x': self._coordinate_mapping.get('translate_x'),
                'translate_y': self._coordinate_mapping.get('translate_y'),
                'translate_z': self._coordinate_mapping.get('translate_z'),
                'rotation_z': self._coordinate_mapping.get('rotation_z')
            },
            'calibration_points_count': len(self._calibration_points) if self._calibration_points else 0,
            'gps_reference_points_count': len(self._gps_reference_points) if self._gps_reference_points else 0
        }

# 전역 좌표 변환기 인스턴스
_coordinate_transformer = None

def get_coordinate_transformer() -> CoordinateTransformer:
    """전역 좌표 변환기 인스턴스 반환"""
    global _coordinate_transformer
    if _coordinate_transformer is None:
        _coordinate_transformer = CoordinateTransformer()
    return _coordinate_transformer