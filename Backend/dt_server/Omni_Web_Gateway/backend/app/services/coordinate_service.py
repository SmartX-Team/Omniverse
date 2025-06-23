import math


class CoordinateService:
    """좌표 관련 서비스"""
    
    def validate_coordinates(self, latitude: float, longitude: float) -> bool:
        """좌표 유효성 검증"""
        if not (-90 <= latitude <= 90):
            return False
        if not (-180 <= longitude <= 180):
            return False
        return True
    
    def dms_to_decimal(self, degrees: int, minutes: int, seconds: float) -> float:
        """도분초를 십진도로 변환"""
        return degrees + minutes/60 + seconds/3600
    
    def calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """두 좌표 간 거리 계산 (Haversine formula, 미터 단위)"""
        R = 6371000  # 지구 반지름 (미터)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng/2) * math.sin(delta_lng/2))
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c