"""


--- 최초 작성일 :2024.05.02 송인용 ---

ekf 용 훈련 데이터를 DB에 저장하는 작업을 위해 만들었던 코드
EKF 성능 측정을 위해 일단 모든 데이터를 최적화 고려 안하고 저장하고 있음
6월에 논문 작성 이후 시간 남을때 다른 DB 쿼리 함수들과 같이 리팩토링 예정


"""


import json
import psycopg2
import os
from datetime import datetime

class DataManager:
    def __init__(self, config_path):
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
            print("Database connection successfully established.")
        except Exception as e:
            print(f"Failed to connect to the database: {e}")

    def store_data_in_db(self, tag_id, posX, posY, timestamp, min_diff, imu_data):
        imu_data = json.loads(imu_data)
        if not self.conn:
            print("Database connection is not available.")
            return
        
        try:
            query = """
            INSERT INTO ros_imu_0950 (stamp, orientation_x, orientation_y, orientation_z, orientation_w,
        orientation_covariance, angular_velocity_x, angular_velocity_y, angular_velocity_z, angular_velocity_covariance, linear_acceleration_x, linear_acceleration_y, linear_acceleration_z,
        linear_acceleration_covariance, tag_id, uwb_x, uwb_y, time_diff, uwb_timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )
            """

            params = (
            imu_data['stamp'],
            imu_data['orientation']['x'],
            imu_data['orientation']['y'],
            imu_data['orientation']['z'],
            imu_data['orientation']['w'],
            imu_data['orientation_covariance'],
            imu_data['angular_velocity']['x'],
            imu_data['angular_velocity']['y'],
            imu_data['angular_velocity']['z'],
            imu_data['angular_velocity_covariance'],
            imu_data['linear_acceleration']['x'],
            imu_data['linear_acceleration']['y'],
            imu_data['linear_acceleration']['z'],
            imu_data['linear_acceleration_covariance'],
            tag_id,
            posX,  # UWB X 좌표
            posY,  # UWB Y 좌표
            min_diff,  # 시간 차이
            timestamp
        )
            self.cursor.execute(query, params)
            self.conn.commit()

        except Exception as e:
            print(f"Failed to insert data: {e}")
            self.conn.rollback()
    # 특정 구간에서 로봇이 움직인 시간만큼 저장 
    def auto_saved_line(self, start_timestamp, end_timestamp, line_id, start_x, start_y, end_x, end_y):
        if not self.conn:
            print("Database connection is not available.")
            return

        try:

            query = """
            INSERT INTO auto_saved_movements_ros (
                start_timestamp, end_timestamp, line_id, 
                x_position_start, y_position_start, 
                x_position_end, y_position_end
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            # 튜플 형식으로 각 필드 값 확인
            params = start_timestamp, end_timestamp, line_id, start_x, start_y, end_x, end_y
            print(f"Params being inserted: {params}")  # 데이터 확인 로그 추가
            self.cursor.execute(query, params)
            self.conn.commit()

        except Exception as e:
            print(f"Failed to insert data: {e}")
            self.conn.rollback()