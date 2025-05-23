"""

25년도에 다시 한번 DB에 적재를 위해 한번 더 수정

--- 작성일 :2025.05.21 송인용 ---

--- 작성일 :2024.12.19 송인용 ---

DB상에 백엔드 처리후의 Timestamp도 추가하도록 수정함 

--- 작성일 :2024.05.12 송인용 ---

기존 버그는 좀 고치고 Collection 코드는 유지하기로 해서 Signal 신호 처리 로직 추가해서 안정성 추가

--- 작성일 :2024.04.30 송인용 ---

심플하게 DB 연결하고 UWB 데이터 들어오는대로 table에 집어넣는 코드

Wwebsocket_raw.py 랑 같이 넣어서 간단하게 UWB 움직일때마다 DB에 적재하는 간단한 컨테이너로 만듬

"""
import json
import psycopg2
from Websocket_raw import SewioWebSocketClient_v2 # Websocket_raw.py 파일이 동일 경로에 있다고 가정
import os
import kafka # KafkaProducer를 사용하려면 kafka.KafkaProducer로 명시하거나, from kafka import KafkaProducer 필요
from datetime import datetime
import sys # sys.exit()를 위해 추가
import signal # SewioWebSocketClient_v2 에서 사용

class DataManager:
    def __init__(self): # config_path 제거
        self.producer = None
        self.topic_name = None
        self.db_conn = None
        self.db_cursor = None
        
        # 초기화 시 바로 연결 시도
        self.db_connect()
        self.kafka_connect()

    def db_connect(self):
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', '5432') # 기본값 5432
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')

        if not all([db_host, db_name, db_user, db_password]):
            print("ERROR: Missing one or more required database environment variables (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD).")
            # 프로그램 종료 또는 적절한 에러 처리
            # 여기서는 연결 시도 없이 None으로 두어, store_data_in_db에서 확인하도록 함
            return

        try:
            print(f"Attempting to connect to database at host: {db_host}:{db_port}, dbname: {db_name}")
            self.db_conn = psycopg2.connect(
                dbname=db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port
            )
            self.db_cursor = self.db_conn.cursor()
            print("Database connection successfully established.")
        except Exception as e:
            print(f"Failed to connect to the database: {e}")
            self.db_conn = None
            self.db_cursor = None

    def kafka_connect(self):
        bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
        self.topic_name = os.getenv('KAFKA_TOPIC')

        if not all([bootstrap_servers, self.topic_name]):
            print("ERROR: Missing one or more required Kafka environment variables (KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC).")
            # self.producer는 None으로 유지됨
            return

        try:
            print(f"Attempting to connect to Kafka at: {bootstrap_servers}, topic: {self.topic_name}")
            self.producer = kafka.KafkaProducer( # kafka.KafkaProducer로 수정
                bootstrap_servers=bootstrap_servers.split(','), # 여러 서버일 경우 콤마로 구분된 문자열 처리
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print("Kafka connection successfully established.")
        except Exception as e:
            print(f"Failed to connect to Kafka: {e}")
            self.producer = None
    
    # send_data_to_kafka, close_producer, store_data_in_db, handle_data, close_db_connection 메소드는 이전과 동일하게 유지
    # (내부 로직은 환경변수에서 읽어온 값들을 사용하게 됨)

    def send_data_to_kafka(self, tag_id, posX, posY, raw_timestamp):
        if self.producer is None:
            print("Kafka producer not available. Skipping send.")
            return False
        coord_data = {
            'id': tag_id,
            'latitude': posX,
            'longitude': posY,
            'raw_timestamp': raw_timestamp
        }
        try:
            self.producer.send(self.topic_name, coord_data)
            self.producer.flush()
            return True
        except Exception as e:
            print(f"Failed to send data to Kafka: {e}")
            return False

    def close_producer(self):
        if self.producer is not None:
            self.producer.close()
            print("Kafka producer closed.")

    def store_data_in_db(self, tag_id, posX, posY, raw_timestamp, anchor_info):
        if self.db_conn is None or self.db_cursor is None:
            print("Database connection not available. Skipping data store.")
            return False
        query = """
        INSERT INTO uwb_raw (
            tag_id,
            x_position,
            y_position,
            raw_timestamp,
            anchor_info,
            process_timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        try:
            process_timestamp = datetime.now()
            self.db_cursor.execute(query, (
                tag_id,
                posX,
                posY,
                raw_timestamp,
                anchor_info,
                process_timestamp
            ))
            self.db_conn.commit()
            return True
        except Exception as e:
            print(f"Failed to store data in database: {e}")
            try:
                self.db_conn.rollback()
            except Exception as re:
                print(f"Failed to rollback database transaction: {re}")
            return False

    def handle_data(self, tag_id, posX, posY, raw_timestamp, anchor_info):
        kafka_success = self.send_data_to_kafka(tag_id, posX, posY, raw_timestamp)
        db_success = self.store_data_in_db(
            tag_id,
            posX,
            posY,
            raw_timestamp,
            anchor_info
        )

        if kafka_success and db_success:
            print(f"Data processed successfully: Tag ID={tag_id}, Raw TS: {raw_timestamp}")
        else:
            print(f"Warning: Data processing partially failed for Tag ID={tag_id}. Kafka: {kafka_success}, DB: {db_success}")
    
    def close_db_connection(self):
        if self.db_cursor:
            self.db_cursor.close()
            print("Database cursor closed.")
        if self.db_conn:
            self.db_conn.close()
            print("Database connection closed.")


def main():
    # DataManager 초기화 (config_path 불필요)
    manager = DataManager()

    # WebSocket URL 환경 변수에서 읽기
    websocket_url = os.getenv('WEBSOCKET_URL')
    if not websocket_url:
        print("ERROR: WEBSOCKET_URL environment variable not set.")
        sys.exit(1) # 필수 환경 변수 없으면 종료

    print(f"Using WebSocket URL: {websocket_url}")

    # SewioWebSocketClient_v2 초기화 (config_path 불필요)
    # SewioWebSocketClient_v2 내부에서 SEWIO_API_KEY, SEWIO_RECONNECT_DELAY 환경 변수를 읽도록 수정됨 (아래 Websocket_raw.py 참고)
    client = SewioWebSocketClient_v2(
        websocket_url,
        data_callback=manager.handle_data
    )
    
    try:
        print("Starting WebSocket client...")
        client.run_forever()
    except KeyboardInterrupt:
        print("Interrupted by user. Shutting down...")
    except Exception as e:
        print(f"An error occurred in WebSocket client: {e}")
    finally:
        print("Closing resources...")
        manager.close_producer()
        manager.close_db_connection()
        if hasattr(client, 'stop') and callable(getattr(client, 'stop')):
             client.stop() # SewioWebSocketClient_v2에는 stop 메소드가 있음
        print("Shutdown complete.")

if __name__ == "__main__":
    main()