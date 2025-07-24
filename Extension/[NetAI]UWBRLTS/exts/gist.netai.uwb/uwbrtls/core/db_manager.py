# ==============================================
# db_manager.py v2 - Prim Mappings 추가
# ==============================================

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from typing import Dict, List, Optional, Tuple, Any
import asyncio
from .config_manager import get_config_manager

class DatabaseManager:
    """데이터베이스 연결 및 쿼리 관리 클래스 v2"""
    
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
        if not conn:
            return
            
        if self.connection_pool:
            try:
                self.connection_pool.putconn(conn)
            except Exception as e:
                print(f"Error returning connection to pool: {e}")
                try:
                    conn.close()
                except:
                    pass
        else:
            try:
                conn.close()
            except:
                pass
    
    async def run_in_thread(self, func, *args):
        """데이터베이스 작업을 스레드 풀에서 실행"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args)
    
    # === 태그 매핑 관련 함수들 ===
    
    def fetch_tag_mappings_sync(self) -> Dict[str, str]:
        """UWB 태그 ID와 디바이스 이름 매핑 조회 (동기) - uwb_tag 테이블"""
        conn = self.get_connection()
        if not conn:
            print("No database connection available - using empty tag mappings")
            return {}
        
        try:
            cursor = conn.cursor()
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'uwb_tag'
                )
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("uwb_tag table does not exist - using empty tag mappings")
                return {}
                
            cursor.execute("SELECT tag_id, device_name FROM uwb_tag WHERE device_name IS NOT NULL")
            rows = cursor.fetchall()
            mapping = {str(row[0]): row[1] for row in rows}
            print(f"Successfully fetched {len(mapping)} tag mappings from uwb_tag table")
            return mapping
        except Exception as e:
            print(f"Failed to fetch tag mappings from database: {e}")
            return {}
        finally:
            self.return_connection(conn)
    
    async def fetch_tag_mappings(self) -> Dict[str, str]:
        """UWB 태그 ID와 디바이스 이름 매핑 조회 (비동기)"""
        return await self.run_in_thread(self.fetch_tag_mappings_sync)
    
    def fetch_prim_mappings_sync(self, space_id: int) -> Dict[str, str]:
        """UWB 태그 ID와 Prim 경로 매핑 조회 (동기) - uwb_prim_mappings 테이블"""
        conn = self.get_connection()
        if not conn:
            print("No database connection available - using empty prim mappings")
            return {}
        
        try:
            cursor = conn.cursor()
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'uwb_prim_mappings'
                )
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("uwb_prim_mappings table does not exist - using empty prim mappings")
                return {}
                
            cursor.execute("""
                SELECT tag_id, prim_path FROM uwb_prim_mappings 
                WHERE space_id = %s AND is_active = true
            """, (space_id,))
            rows = cursor.fetchall()
            mapping = {str(row[0]): row[1] for row in rows}
            print(f"Successfully fetched {len(mapping)} prim mappings from uwb_prim_mappings table (space_id: {space_id})")
            return mapping
        except Exception as e:
            print(f"Failed to fetch prim mappings from database: {e}")
            return {}
        finally:
            self.return_connection(conn)
    
    async def fetch_prim_mappings(self, space_id: int) -> Dict[str, str]:
        """UWB 태그 ID와 Prim 경로 매핑 조회 (비동기)"""
        return await self.run_in_thread(self.fetch_prim_mappings_sync, space_id)
    
    # === 좌표 매핑 관련 함수들 ===
    
    def fetch_coordinate_mapping_sync(self, space_id: int) -> Optional[Dict[str, Any]]:
            """좌표 매핑 정보 조회 (동기) - RealDictCursor 문제 해결"""
            conn = self.get_connection()
            if not conn:
                print("No database connection available")
                return None
            
            try:
                # EXISTS 쿼리는 일반 커서 사용 (인덱스 접근)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'coordinate_mappings'
                    )
                """)
                table_exists = cursor.fetchone()[0]
                print(f"coordinate_mappings table exists: {table_exists}")
                
                if not table_exists:
                    print("oordinate_mappings table does not exist")
                    return None
                
                # 디버깅용 카운트 쿼리들 (일반 커서)
                cursor.execute("SELECT COUNT(*) FROM coordinate_mappings")
                total_count = cursor.fetchone()[0]
                print(f"Total records in coordinate_mappings: {total_count}")
                
                cursor.execute("SELECT COUNT(*) FROM coordinate_mappings WHERE space_id = %s", (space_id,))
                space_count = cursor.fetchone()[0]
                print(f"Records for space_id {space_id}: {space_count}")
                
                cursor.execute("SELECT COUNT(*) FROM coordinate_mappings WHERE space_id = %s AND is_active = true", (space_id,))
                active_count = cursor.fetchone()[0]
                print(f"Active records for space_id {space_id}: {active_count}")
                
                # 실제 데이터 조회는 RealDictCursor 사용
                dict_cursor = conn.cursor(cursor_factory=RealDictCursor)
                query = """
                    SELECT * FROM coordinate_mappings 
                    WHERE space_id = %s AND is_active = true
                    LIMIT 1
                """
                dict_cursor.execute(query, (space_id,))
                result = dict_cursor.fetchone()
                
                if result:
                    print(f"Successfully fetched coordinate mapping for space_id {space_id}")
                    print(f"Mapping data: {dict(result)}")
                    return dict(result)
                else:
                    print(f"No active coordinate mapping found for space_id {space_id}")
                    return None
                    
            except Exception as e:
                print(f"Exception in fetch_coordinate_mapping: {e}")
                import traceback
                traceback.print_exc()
                return None
            finally:
                self.return_connection(conn)
    
    async def fetch_coordinate_mapping(self, space_id: int) -> Optional[Dict[str, Any]]:
        """좌표 매핑 정보 조회 (비동기)"""
        return await self.run_in_thread(self.fetch_coordinate_mapping_sync, space_id)
    
    # === 캘리브레이션 관련 함수들 ===
    
    def fetch_calibration_points_sync(self, mapping_id: int) -> List[Dict[str, Any]]:
        """캘리브레이션 포인트 조회 (동기)"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'calibration_points'
                )
            """)
            if not cursor.fetchone()[0]:
                print("calibration_points table does not exist - returning empty list")
                return []
                
            query = """
                SELECT * FROM calibration_points 
                WHERE coordinate_mapping_id = %s
                ORDER BY point_name
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
    
    def fetch_gps_reference_points_sync(self, space_id: int) -> List[Dict[str, Any]]:
        """GPS 기준점 조회 (동기)"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'gps_reference_points'
                )
            """)
            if not cursor.fetchone()[0]:
                print("gps_reference_points table does not exist - returning empty list")
                return []
                
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
    
    # === 데이터 저장 관련 함수들 ===
    
    def record_timestamp_sync(self, tag_id: str, raw_timestamp: str, omniverse_timestamp: str):
        """타임스탬프 기록 (동기)"""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'uwb_timestamp_tracking'
                )
            """)
            if not cursor.fetchone()[0]:
                print("uwb_timestamp_tracking table does not exist - skipping timestamp recording")
                return
                
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
                try:
                    conn.rollback()
                except:
                    pass
        finally:
            self.return_connection(conn)
    
    async def record_timestamp(self, tag_id: str, raw_timestamp: str):
        """타임스탬프 기록 (비동기)"""
        omniverse_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        await self.run_in_thread(self.record_timestamp_sync, tag_id, raw_timestamp, omniverse_timestamp)
    
    def save_transformed_coordinates_sync(self, tag_id: str, space_id: int, 
                                        uwb_x: float, uwb_y: float, uwb_timestamp: str,
                                        omniverse_x: float, omniverse_y: float, omniverse_z: float,
                                        mapping_id: Optional[int] = None):
        """변환된 좌표 저장 (동기) - 실제 테이블 스키마 호환 (최소 필수 컬럼만)"""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'transformed_coordinates'
                )
            """)
            if not cursor.fetchone()[0]:
                print("transformed_coordinates table does not exist - skipping coordinate saving")
                return
                
            insert_query = """
                INSERT INTO transformed_coordinates 
                (tag_id, space_id, mapping_id, uwb_x, uwb_y, uwb_timestamp, 
                 omniverse_x, omniverse_y, omniverse_z)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                tag_id, space_id, mapping_id, uwb_x, uwb_y, uwb_timestamp,
                omniverse_x, omniverse_y, omniverse_z
            ))
            conn.commit()
            print(f"Successfully saved transformed coordinates for tag {tag_id}")
        except Exception as e:
            print(f"Error saving transformed coordinates: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
        finally:
            self.return_connection(conn)
    
    async def save_transformed_coordinates(self, tag_id: str, space_id: int,
                                         uwb_x: float, uwb_y: float, uwb_timestamp: str,
                                         omniverse_x: float, omniverse_y: float, omniverse_z: float,
                                         mapping_id: Optional[int] = None):
        """변환된 좌표 저장 (비동기) - 실제 테이블 스키마 호환 (최소 필수 컬럼만)"""
        await self.run_in_thread(
            self.save_transformed_coordinates_sync,
            tag_id, space_id, uwb_x, uwb_y, uwb_timestamp,
            omniverse_x, omniverse_y, omniverse_z, mapping_id
        )
    
    # === 범용 쿼리 실행 함수 (하위 호환성) ===
    
    def execute_query_sync(self, query: str, params: tuple = None) -> List[tuple]:
        """범용 쿼리 실행 (동기) - 하위 호환성을 위해 유지하지만 사용 권장하지 않음"""
        print("Warning: execute_query_sync is deprecated. Use specific fetch/save methods instead.")
        
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # SELECT 쿼리인 경우 결과 반환
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                conn.commit()
                return []
        except Exception as e:
            print(f"Error executing query: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return []
        finally:
            self.return_connection(conn)
    
    async def execute_query(self, query: str, params: tuple = None) -> List[tuple]:
        """범용 쿼리 실행 (비동기) - 하위 호환성을 위해 유지하지만 사용 권장하지 않음"""
        return await self.run_in_thread(self.execute_query_sync, query, params)
    
    # === 연결 정리 ===
    
    def close(self):
        """리소스 정리"""
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
            except Exception as e:
                print(f"Error closing connection pool: {e}")
        
        try:
            self.thread_pool.shutdown(wait=True)
        except Exception as e:
            print(f"Error shutting down thread pool: {e}")


    def fetch_publishing_objects_sync(self, space_id: int) -> List[Dict[str, Any]]:
        """발행 대상 오브젝트 목록 조회 (동기) - 커서 타입 수정"""
        conn = self.get_connection()
        if not conn:
            print("No database connection available - using empty publishing objects")
            return []
        
        try:
            # 테이블 존재 확인은 일반 커서 사용
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'publishing_objects'
                )
            """)
            table_exists = cursor.fetchone()[0]
            print(f"publishing_objects table exists: {table_exists}")
            
            if not table_exists:
                print("publishing_objects table does not exist - returning empty list")
                return []
            
            # 전체 데이터 개수 확인 (일반 커서)
            cursor.execute("SELECT COUNT(*) FROM publishing_objects")
            total_count = cursor.fetchone()[0]
            print(f"Total records in publishing_objects: {total_count}")
            
            # space_id별 데이터 개수 확인 (일반 커서)
            cursor.execute("SELECT COUNT(*) FROM publishing_objects WHERE space_id = %s", (space_id,))
            space_count = cursor.fetchone()[0]
            print(f"Records for space_id {space_id}: {space_count}")
            
            # 활성화된 데이터 개수 확인 (일반 커서)
            cursor.execute("SELECT COUNT(*) FROM publishing_objects WHERE space_id = %s AND is_active = true", (space_id,))
            active_count = cursor.fetchone()[0]
            print(f"Active records for space_id {space_id}: {active_count}")
            
            # 실제 데이터 조회는 RealDictCursor 사용
            dict_cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT * FROM publishing_objects 
                WHERE space_id = %s AND is_active = true
                ORDER BY created_at DESC
            """
            print(f"Executing query: {query} with space_id={space_id}")
            dict_cursor.execute(query, (space_id,))
            results = dict_cursor.fetchall()
            
            objects_list = [dict(row) for row in results]
            print(f"Successfully fetched {len(objects_list)} publishing objects for space_id {space_id}")
            
            # 첫 번째 결과 출력 (있는 경우)
            if objects_list:
                print(f"First object: {objects_list[0]}")
            
            return objects_list
            
        except Exception as e:
            print(f"Failed to fetch publishing objects: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            self.return_connection(conn)
    
    def add_publishing_object_sync(self, space_id: int, object_path: str, 
                                  object_name: str = None, virtual_tag_id: str = None,
                                  publish_rate_hz: float = 10.0) -> bool:
        """발행 오브젝트 추가 (동기) - 디버깅 강화"""
        conn = self.get_connection()
        if not conn:
            print("No database connection available")
            return False
        
        try:
            cursor = conn.cursor()
            
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'publishing_objects'
                )
            """)
            table_exists = cursor.fetchone()[0]
            print(f"publishing_objects table exists: {table_exists}")
            
            if not table_exists:
                print("publishing_objects table does not exist - cannot add object")
                return False
            
            # 테이블 구조 확인 (PostgreSQL 방식)
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'publishing_objects'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            print("Table structure:")
            for col in columns:
                print(f"  {col[0]}: {col[1]}")
            
            # 중복 체크
            cursor.execute("""
                SELECT COUNT(*) FROM publishing_objects 
                WHERE space_id = %s AND object_path = %s AND is_active = true
            """, (space_id, object_path))
            
            duplicate_count = cursor.fetchone()[0]
            print(f"Duplicate check for {object_path}: {duplicate_count} existing records")
            
            if duplicate_count > 0:
                print(f"Object {object_path} already exists in publishing_objects for space_id {space_id}")
                return False
            
            # virtual_tag_id 자동 생성 (없는 경우)
            if not virtual_tag_id:
                publishing_config = self.config_manager.get_publishing_config()
                prefix = publishing_config.get('virtual_tag_prefix', 'OMNI_')
                # object_path에서 마지막 부분 추출하여 태그 ID 생성
                object_suffix = object_path.split('/')[-1] if '/' in object_path else object_path
                virtual_tag_id = f"{prefix}{object_suffix}"
                print(f"Generated virtual_tag_id: {virtual_tag_id}")
            
            # 데이터 삽입
            insert_query = """
                INSERT INTO publishing_objects 
                (space_id, object_path, object_name, virtual_tag_id, publish_rate_hz)
                VALUES (%s, %s, %s, %s, %s)
            """
            values = (space_id, object_path, object_name, virtual_tag_id, publish_rate_hz)
            print(f"Inserting: {values}")
            
            cursor.execute(insert_query, values)
            conn.commit()
            
            print(f"Successfully added publishing object: {object_path} (tag: {virtual_tag_id})")
            return True
            
        except Exception as e:
            print(f"Error adding publishing object: {e}")
            import traceback
            traceback.print_exc()
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return False
        finally:
            self.return_connection(conn)

    async def fetch_publishing_objects(self, space_id: int) -> List[Dict[str, Any]]:
        """발행 대상 오브젝트 목록 조회 (비동기)"""
        return await self.run_in_thread(self.fetch_publishing_objects_sync, space_id)

    async def add_publishing_object(self, space_id: int, object_path: str, 
                                object_name: str = None, virtual_tag_id: str = None,
                                publish_rate_hz: float = 10.0) -> bool:
        """발행 오브젝트 추가 (비동기)"""
        return await self.run_in_thread(
            self.add_publishing_object_sync, 
            space_id, object_path, object_name, virtual_tag_id, publish_rate_hz
        )

    def remove_publishing_object_sync(self, object_id: int) -> bool:
        """발행 오브젝트 제거 (동기) - is_active를 false로 설정"""
        conn = self.get_connection()
        if not conn:
            print("No database connection available")
            return False
        
        try:
            cursor = conn.cursor()
            # 테이블 존재 여부 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'publishing_objects'
                )
            """)
            if not cursor.fetchone()[0]:
                print("publishing_objects table does not exist - cannot remove object")
                return False
            
            # 오브젝트 존재 여부 확인
            cursor.execute("""
                SELECT object_path FROM publishing_objects 
                WHERE id = %s AND is_active = true
            """, (object_id,))
            
            result = cursor.fetchone()
            if not result:
                print(f"Publishing object with id {object_id} not found or already inactive")
                return False
            
            object_path = result[0]
            
            # is_active를 false로 설정 (soft delete)
            update_query = """
                UPDATE publishing_objects 
                SET is_active = false, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            cursor.execute(update_query, (object_id,))
            conn.commit()
            print(f"Successfully removed publishing object: {object_path} (id: {object_id})")
            return True
            
        except Exception as e:
            print(f"Error removing publishing object: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return False
        finally:
            self.return_connection(conn)

    async def remove_publishing_object(self, object_id: int) -> bool:
        """발행 오브젝트 제거 (비동기)"""
        return await self.run_in_thread(self.remove_publishing_object_sync, object_id)

    def update_publishing_object_sync(self, object_id: int, **kwargs) -> bool:
        """발행 오브젝트 정보 업데이트 (동기)"""
        conn = self.get_connection()
        if not conn:
            print("No database connection available")
            return False
        
        try:
            cursor = conn.cursor()
            # 업데이트 가능한 필드들
            allowed_fields = ['object_name', 'virtual_tag_id', 'publish_rate_hz', 'is_active']
            update_fields = []
            update_values = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    update_fields.append(f"{field} = %s")
                    update_values.append(value)
            
            if not update_fields:
                print("No valid fields to update")
                return False
            
            # updated_at 자동 추가
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            update_values.append(object_id)
            
            update_query = f"""
                UPDATE publishing_objects 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """
            
            cursor.execute(update_query, update_values)
            
            if cursor.rowcount == 0:
                print(f"Publishing object with id {object_id} not found")
                return False
            
            conn.commit()
            print(f"Successfully updated publishing object id {object_id}")
            return True
            
        except Exception as e:
            print(f"Error updating publishing object: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return False
        finally:
            self.return_connection(conn)

    async def update_publishing_object(self, object_id: int, **kwargs) -> bool:
        """발행 오브젝트 정보 업데이트 (비동기)"""
        return await self.run_in_thread(self.update_publishing_object_sync, object_id, **kwargs)            
# 전역 데이터베이스 매니저 인스턴스
_db_manager = None

def get_db_manager() -> DatabaseManager:
    """전역 데이터베이스 매니저 인스턴스 반환"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager