"""

--- 작성일 :2024.05.03 송인용 ---

구간 측정 및 분석 작업을 수월하게 해주는데 필요한 테이블 생성 쿼리 모음


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

cursor.execute("""DROP TABLE IF EXISTS auto_saved_movements_rosavg;""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS auto_saved_movements_rosavg (
    id SERIAL PRIMARY KEY,
    tag_id REAL,
    uwb_x REAL,
    uwb_y REAL,
    stamp DOUBLE PRECISION,
    avg_yaw REAL,
    avg_ax REAL,
    avg_ay REAL,
    uwb_timestamp TIMESTAMP without time zone               
);
""")