import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import asyncio
from .config_manager import get_config_manager

class DatabaseManager:
    """데이터베이스 연결 및 쿼리 관리 클래스"""
    
    def __init__(self, max_workers: int = 3):
        self.config_manager = get_config_manager()
        self.db_config = self.config_manager.get_postgres_config()
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="db_worker")
        self.connection_pool = None
        self._initialize_connection_pool()
    
    def _initialize_connection_pool(self):
        """연결 풀 초기화"""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                **self.db_config
            )
            print("Database connection pool initialized successfully")
        except Exception as e:
            print(f"Failed to initialize database connection pool: {e}")
    
    def get_connection(self):
        """연결 풀에서 연결 가져오기"""
        if self.connection_pool:
            try:
                return self.connection_pool.getconn()
            except Exception as e:
                print(f"Error getting connection from pool: {e}")
        
        # 풀이 없거나 실패한 경우 직접 연결
        try:
            return psycopg2.connect(**self.db_config)
        except Exception as e:
            print(f"Failed to create direct database connection: {e}")
            return None
    
    def return_connection(self, conn):
        """연결을 풀에 반환"""
        if self.connection_pool and conn:
            try:
                self.connection_pool.putconn(conn)
            except Exception as e:
                print(f"Error returning connection to pool: {e}")
                if conn:
                    conn.close()
        elif conn:
            conn.close()
    
    async def run_in_thread(self, func, *args):
        """데이터베이스 작업을 스레드 풀에서 실행"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args)
    
    # === UWB 태그 매핑 관련 ===
    def fetch_tag_mappings_sync(self) -> Dict[str, str]:
        """UWB 태그 ID와 NUC ID 매핑 조회 (동기)"""
        conn = self.get_connection()
        if not conn:
            return {}
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT tag_id, nuc_id FROM uwb_tag WHERE nuc_id IS NOT NULL")
            rows = cursor.fetchall()
            mapping = {str(row[0]): row[1] for row in rows}
            print(f"Successfully fetched {len(mapping)} tag mappings from database")
            return mapping
        except Exception as e:
            print(f"Failed to fetch tag mappings from database: {e}")
            return {}
        finally:
            self.return_connection(conn)
    
    async def fetch_tag_mappings(self) -> Dict[str, str]:
        """UWB 태그 ID와 NUC ID 매핑 조회 (비동기)"""
        return await self.run_in_thread(self.fetch_tag_mappings_sync)
    
    # === 좌표계 매핑 관련 ===
    def fetch_coordinate_mapping_sync(self, space_id: int) -> Optional[Dict[str, Any]]:
        """좌표 매핑 정보 조회 (동기)"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT 
                    cm.*,
                    ucs.min_x as uwb_min_x, ucs.max_x as uwb_max_x,
                    ucs.min_y as uwb_min_y, ucs.max_y as uwb_max_y,
                    ocs.scale_factor, ocs.offset_x, ocs.offset_y, ocs.offset_z,
                    ocs.rotation_degrees
                FROM coordinate_mappings cm
                JOIN uwb_coordinate_systems ucs ON cm.uwb_coordinate_system_id = ucs.id
                JOIN omniverse_coordinate_systems ocs ON cm.omniverse_coordinate_system_id = ocs.id
                WHERE cm.space_id = %s AND cm.is_active = true
                LIMIT 1
            """
            cursor.execute(query, (space_id,))
            result = cursor.fetchone()
            
            if result:
                return dict(result)
            else:
                print(f"No active coordinate mapping found for space_id {space_id}")
                return None
        except Exception as e:
            print(f"Failed to fetch coordinate mapping: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    async def fetch_coordinate_mapping(self, space_id: int) -> Optional[Dict[str, Any]]:
        """좌표 매핑 정보 조회 (비동기)"""
        return await self.run_in_thread(self.fetch_coordinate_mapping_sync, space_id)
    
    def fetch_calibration_points_sync(self, mapping_id: int) -> List[Dict[str, Any]]:
        """캘리브레이션 포인트 조회 (동기)"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT * FROM calibration_points 
                WHERE coordinate_mapping_id = %s
                ORDER BY is_reference_point DESC, point_name
            """
            cursor.execute(query, (mapping_id,))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"Failed to fetch calibration points: {e}")
            return []
        finally:
            self.return_connection(conn)
    
    async def fetch_calibration_points(self, mapping_id: int) -> List[Dict[str, Any]]:
        """캘리브레이션 포인트 조회 (비동기)"""
        return await self.run_in_thread(self.fetch_calibration_points_sync, mapping_id)
    
    # === 타임스탬프 기록 ===
    def record_timestamp_sync(self, tag_id: str, raw_timestamp: str, omniverse_timestamp: str):
        """타임스탬프 기록 (동기)"""
        conn = self.get_connection()
        if not conn:
            print("Failed to connect to database for timestamp recording")
            return
        
        try:
            cursor = conn.cursor()
            insert_query = """
                INSERT INTO uwb_timestamp_tracking (tag_id, raw_timestamp, omniverse_timestamp)
                VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (tag_id, raw_timestamp, omniverse_timestamp))
            conn.commit()
            print(f"Successfully recorded timestamps for tag {tag_id}")
        except Exception as e:
            print(f"Error recording timestamps to database: {e}")
            if conn:
                conn.rollback()
        finally:
            self.return_connection(conn)
    
    async def record_timestamp(self, tag_id: str, raw_timestamp: str):
        """타임스탬프 기록 (비동기)"""
        omniverse_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        await self.run_in_thread(self.record_timestamp_sync, tag_id, raw_timestamp, omniverse_timestamp)
    
    # === 변환된 좌표 저장 ===
    def save_transformed_coordinates_sync(self, tag_id: str, space_id: int, 
                                        uwb_x: float, uwb_y: float, uwb_timestamp: str,
                                        omniverse_x: float, omniverse_y: float, omniverse_z: float,
                                        gps_lat: Optional[float] = None, gps_lon: Optional[float] = None,
                                        mapping_id: Optional[int] = None):
        """변환된 좌표 저장 (동기)"""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            insert_query = """
                INSERT INTO transformed_coordinates 
                (tag_id, space_id, uwb_x, uwb_y, uwb_timestamp, 
                 omniverse_x, omniverse_y, omniverse_z, 
                 gps_latitude, gps_longitude, coordinate_mapping_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                tag_id, space_id, uwb_x, uwb_y, uwb_timestamp,
                omniverse_x, omniverse_y, omniverse_z,
                gps_lat, gps_lon, mapping_id
            ))
            conn.commit()
        except Exception as e:
            print(f"Error saving transformed coordinates: {e}")
            if conn:
                conn.rollback()
        finally:
            self.return_connection(conn)
    
    async def save_transformed_coordinates(self, tag_id: str, space_id: int,
                                         uwb_x: float, uwb_y: float, uwb_timestamp: str,
                                         omniverse_x: float, omniverse_y: float, omniverse_z: float,
                                         gps_lat: Optional[float] = None, gps_lon: Optional[float] = None,
                                         mapping_id: Optional[int] = None):
        """변환된 좌표 저장 (비동기)"""
        await self.run_in_thread(
            self.save_transformed_coordinates_sync,
            tag_id, space_id, uwb_x, uwb_y, uwb_timestamp,
            omniverse_x, omniverse_y, omniverse_z,
            gps_lat, gps_lon, mapping_id
        )
    
    # === GPS 기준점 조회 ===
    def fetch_gps_reference_points_sync(self, space_id: int) -> List[Dict[str, Any]]:
        """GPS 기준점 조회 (동기)"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT * FROM gps_reference_points 
                WHERE space_id = %s
                ORDER BY point_name
            """
            cursor.execute(query, (space_id,))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"Failed to fetch GPS reference points: {e}")
            return []
        finally:
            self.return_connection(conn)
    
    async def fetch_gps_reference_points(self, space_id: int) -> List[Dict[str, Any]]:
        """GPS 기준점 조회 (비동기)"""
        return await self.run_in_thread(self.fetch_gps_reference_points_sync, space_id)
    
    def close(self):
        """리소스 정리"""
        if self.connection_pool:
            self.connection_pool.closeall()
        self.thread_pool.shutdown(wait=True)

# 전역 데이터베이스 매니저 인스턴스
_db_manager = None

def get_db_manager() -> DatabaseManager:
    """전역 데이터베이스 매니저 인스턴스 반환"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager