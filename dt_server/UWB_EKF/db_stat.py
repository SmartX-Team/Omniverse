""" 

--- 최초 작성일 :2024.05.01 송인용 ---


DB에서 READ 작업 모음 

코드 길어지기 전에 SQL 쿼리들을 따로 별도 파일에서 저장해서 관리할 '예정'


"""

import psycopg2
import json

# row_limit 은 분석 진행하는 전체 행수
# 해당 클래스는 분석을 위해 DB READ QUERY 작업 모음
class DBStatManager:
    def __init__(self, config_path, row_limit=1000000):
        self.config_path = config_path
        self.load_config()
        self.db_connect()
        self.row_limit = row_limit

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = json.load(file)

    def db_connect(self):
        try:
            self.conn = psycopg2.connect(
                dbname=self.config['db_name'],
                user=self.config['db_user'],
                password=self.config['db_password'],
                host=self.config['db_host'],
                port=self.config['db_port']
            )
            self.cursor = self.conn.cursor()
            print("Database connection successfully established.")
        except Exception as e:
            print(f"Failed to connect to the database: {e}")


    def get_tag_statistics(self, tag_id, start=None, end=None):
        try:
            # 조건 문자열 구성
            conditions = "WHERE tag_id = %s"
            params = [tag_id]

            # 시작 시간과 종료 시간 조건 추가
            if start:
                conditions += " AND timestamp >= %s"
                params.append(start)
            if end:
                conditions += " AND timestamp <= %s"
                params.append(end)

            # 총 행 수 쿼리
            self.cursor.execute(f"""
                SELECT COUNT(*)
                FROM (
                    SELECT * FROM uwb_raw {conditions} ORDER BY timestamp DESC LIMIT %s
                ) AS limited
            """, params + [self.row_limit])
            row_count = self.cursor.fetchone()[0]

            # 평균 간격 계산 쿼리
            self.cursor.execute(f"""
                WITH TimeDifferences AS (
                    SELECT EXTRACT(EPOCH FROM (timestamp - LAG(timestamp) OVER (ORDER BY timestamp))) AS interval
                    FROM (
                        SELECT * FROM uwb_raw {conditions} ORDER BY timestamp DESC LIMIT %s
                    ) AS limited
                )
                SELECT AVG(interval) FROM TimeDifferences
            """, params + [self.row_limit])
            avg_interval = self.cursor.fetchone()[0]

            if avg_interval is None:
                avg_interval = 'No sufficient data for interval calculation'

            return {
                "total_rows": row_count,
                "average_interval": avg_interval
            }
        except Exception as e:
            print(f"Error fetching statistics for tag_id {tag_id}: {e}")
            return None
        
    # 특정 시간 구간 내 x, y 좌표 값 가져오는 함수 
    def get_tag_movements(self, tag_id, start=None, end=None):
        try:
            # 조건 문자열 구성
            conditions = "WHERE tag_id = %s"
            params = [tag_id]

            # 시작 시간과 종료 시간 조건 추가
            if start:
                conditions += " AND timestamp >= %s"
                params.append(start)
            if end:
                conditions += " AND timestamp <= %s"
                params.append(end)

            # x, y 좌표와 타임스탬프 쿼리
            self.cursor.execute(f"""
                SELECT x_position, y_position, timestamp
                FROM uwb_raw
                {conditions}
                ORDER BY timestamp ASC
                LIMIT %s
            """, params + [self.row_limit])

            movements = self.cursor.fetchall()
            # 각 움직임은 (x_position, y_position, timestamp) 튜플 형태로 반환
            return movements

        except Exception as e:
            print(f"Error fetching movements for tag_id {tag_id}: {e}")
            return None
        

    # EKF 테스트를 위해 모든 행 가져오는 함수
    # 현재 IMU 설치된 장비는 tag 15 장착된 HUSKY 0950 이므로 쿼리 고정 시킴
    def get_all_ekf_data(self):
        try:
            self.cursor.execute(f"""
                SELECT orientation_z, uwb_x, uwb_y, stamp  FROM ros_imu_0950 ORDER BY stamp ASC
            """)
            data = self.cursor.fetchall()
            return data
        except Exception as e:
            print(f"Error fetching EKF data: {e}")
            return None

# 시스템 관련 DB 작업
# 해당 클래스는 분석 관련 내용 

class DBSystemManager:
    def __init__(self, config_path,):
        self.config_path = config_path
        self.load_config()
        self.db_connect()

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = json.load(file)

    def db_connect(self):
        try:
            self.conn = psycopg2.connect(
                dbname=self.config['db_name'],
                user=self.config['db_user'],
                password=self.config['db_password'],
                host=self.config['db_host'],
                port=self.config['db_port']
            )
            self.cursor = self.conn.cursor()
            print("Database connection successfully established system Manager.")
        except Exception as e:
            print(f"Failed to connect to the database: {e}")

    def get_taglist(self):
        try:
            self.cursor.execute("SELECT tag_id, kube_id, nuc_id FROM uwb_tag")
            tag_list = self.cursor.fetchall()
            return tag_list
        except Exception as e:
            print(f"Failed to retrieve tag list from database: {e}")
            return []
        
    def get_space_bounds(self):
        try:
            self.cursor.execute("SELECT x_position_min, x_position_max, y_position_min, y_position_max FROM uwb_space WHERE id = 1")
            bounds = self.cursor.fetchone()
            return bounds
        except Exception as e:
            print(f"Failed to retrieve space bounds from database: {e}")
            return None