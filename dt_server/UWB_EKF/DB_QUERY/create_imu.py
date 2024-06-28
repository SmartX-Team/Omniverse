"""
seq (int): 메시지 순서 번호
stamp (Float): 타임스탬프 초.나노초 (Unix 타임)

orientation_x (float): 방향성 x
orientation_y (float): 방향성 y
orientation_z (float): 방향성 z
orientation_w (float): 방향성 w
orientation_covariance (float[]): 방향성 공분산 배열
angular_velocity_x (float): 각속도 x
angular_velocity_y (float): 각속도 y
angular_velocity_z (float): 각속도 z
angular_velocity_covariance (float[]): 각속도 공분산 배열
linear_acceleration_x (float): 선형 가속도 x
linear_acceleration_y (float): 선형 가속도 y
linear_acceleration_z (float): 선형 가속도 z
linear_acceleration_covariance (float[]): 선형 가속도 공분산 배열
tag_id (float4): 태그 ID
uwb_x (float4): UWB x
uwb_y (float4): UWB y
time_diff (float4): UWB 데이터와 IMU 데이터의 Stamp 시간 차이
uwb_timestamp (timestamp): UWB 타임스탬프

--- 작성일 :2024.05.02 송인용 ---
EKF 개선을 위해 IMU 데이터를 저장하는 테이블을 생성하는 쿼리입니다. PostgresSQL을 사용하고 있는데, 호옥시 참고용으로 필요한 분이 있을까 싶어서 남깁니다.
실제 운용에서 필요한 데이터 컬럼보다 많은 데이터를 저장하고 있는데, 나중에 실제 운용에서는 필요한 데이터만 저장하도록 수정해서 새로운 테이블 만들고, 데이터 형식도 필요한것만 float로 변경 요청

"""


import json
import psycopg2


# config.json 파일에서 설정 로드
with open('/home/netai/Omniverse/dt_server/UWB_EKF/config.json', 'r') as file:
    config = json.load(file)

# 데이터베이스 연결 설정
conn_string = f"host={config['db_host']} port={config['db_port']} dbname={config['db_name']} user={config['db_user']} password={config['db_password']}"

# 데이터베이스에 연결
conn = psycopg2.connect(conn_string)
conn.autocommit = True  # 자동 커밋 활성화

# 커서 생성
cursor = conn.cursor()


# 테이블 생성 테스트
cursor.execute("""
CREATE TABLE IF NOT EXISTS ros_imu_0950 (
    id SERIAL PRIMARY KEY,
    stamp DOUBLE PRECISION,
    orientation_x REAL,
    orientation_y REAL,
    orientation_z REAL,
    orientation_w REAL,
    orientation_covariance REAL[9],
    angular_velocity_x REAL,
    angular_velocity_y REAL,
    angular_velocity_z REAL,
    angular_velocity_covariance REAL[9],
    linear_acceleration_x REAL,
    linear_acceleration_y REAL,
    linear_acceleration_z REAL,
    linear_acceleration_covariance REAL[9],
    tag_id REAL,
    uwb_x REAL,
    uwb_y REAL,
    time_diff REAL,
    uwb_timestamp TIMESTAMP without time zone
);
""")