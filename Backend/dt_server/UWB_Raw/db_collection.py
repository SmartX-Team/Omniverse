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
from Websocket_raw import SewioWebSocketClient_v2
import os
from kafka import KafkaProducer
from datetime import datetime

class DataManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.load_config()

        self.producer = None
        self.topic_name = None
        self.db_conn = None # conn을 인스턴스 변수로 변경하여 명시적으로 관리
        self.db_cursor = None # cursor도 인스턴스 변수로 변경
        self.db_connect()
        self.kafka_connect()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as file:
                self.config = json.load(file)
            print(f"Configuration loaded from {self.config_path}")
        except FileNotFoundError:
            print(f"ERROR: Configuration file not found at {self.config_path}")
            # 설정 파일이 없으면 실행이 어려우므로, 적절한 예외 처리 또는 프로그램 종료 로직 추가 가능
            raise
        except json.JSONDecodeError:
            print(f"ERROR: Could not decode JSON from {self.config_path}")
            raise # 혹은 기본 설정으로 폴백하거나 종료

    def db_connect(self):
        if not hasattr(self, 'config'): # config가 로드되지 않았으면 연결 시도하지 않음
            print("ERROR: Configuration not loaded. Cannot connect to database.")
            return

        try:
            # 1. 환경 변수에서 DB 호스트 주소 읽기 시도
            db_host_env = os.getenv('DB_HOST_OVERRIDE')

            # 2. 환경 변수에 값이 있으면 그 값을 사용, 없으면 설정 파일 값 사용
            db_host = db_host_env if db_host_env else self.config['postgres']['db_host']
            
            print(f"Attempting to connect to database at host: {db_host}") # 실제 연결 시도하는 호스트 주소 로깅

            self.db_conn = psycopg2.connect(
                dbname=self.config['postgres']['db_name'],
                user=self.config['postgres']['db_user'],
                password=self.config['postgres']['db_password'],
                host=db_host, # 수정된 호스트 주소 사용
                port=self.config['postgres']['db_port']
            )
            self.db_cursor = self.db_conn.cursor()
            print("Database connection successfully established.")
        except KeyError as e:
            print(f"Failed to connect to the database: Missing key {e} in postgres configuration.")
        except Exception as e:
            print(f"Failed to connect to the database: {e}")
            # 연결 실패 시 db_conn, db_cursor를 None으로 유지하거나 명시적 초기화
            self.db_conn = None
            self.db_cursor = None


    def kafka_connect(self):
        if not hasattr(self, 'config'):
            print("ERROR: Configuration not loaded. Cannot connect to Kafka.")
            return
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.config['kafka']['bootstrap_servers'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            self.topic_name = self.config['kafka']['uwb_rlts']['topic']
            print("Kafka connection successfully established.")
        except KeyError as e:
            print(f"Failed to connect to Kafka: Missing key {e} in kafka configuration.")
        except Exception as e:
            print(f"Failed to connect to Kafka: {e}")
            self.producer = None


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
        if self.db_conn is None or self.db_cursor is None: # DB 연결이 안되어 있으면 저장 시도 X
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
                self.db_conn.rollback() # 롤백 시도
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
    
    def close_db_connection(self): # DB 연결 종료 메소드 추가
        if self.db_cursor:
            self.db_cursor.close()
            print("Database cursor closed.")
        if self.db_conn:
            self.db_conn.close()
            print("Database connection closed.")


def main():
    config_path_env = os.getenv('CONFIG_PATH')
    if not config_path_env:
        print("Warning: CONFIG_PATH environment variable not set. Using default: '/mnt/ceph-pvc/config.json'")
        config_path_env = '/mnt/ceph-pvc/config.json'
    
    # 설정 파일 로드 및 DataManager 초기화
    try:
        # DataManager 생성 전에 config 파일에서 websocket url을 읽어야 함
        with open(config_path_env, 'r') as file:
            temp_config = json.load(file)
        
        if 'websocket' not in temp_config or 'url' not in temp_config['websocket']:
            print("ERROR: WebSocket URL missing from config.json")
            return # 혹은 적절한 예외 발생

        websocket_url = temp_config['websocket']['url']

        manager = DataManager(config_path_env) # DataManager는 내부적으로 config를 다시 로드함
    except Exception as e:
        print(f"Failed to initialize DataManager or load initial config: {e}")
        return # 초기화 실패 시 종료


    client = SewioWebSocketClient_v2(
        websocket_url, # config에서 읽어온 websocket_url 사용
        data_callback=manager.handle_data
        # config_path 인자가 SewioWebSocketClient_v2에 필요 없다면 아래 줄 제거
        # , config_path=config_path_env
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
        manager.close_db_connection() # DB 연결 종료 호출
        if hasattr(client, 'close') and callable(getattr(client, 'close')): # client에 close 메소드가 있다면 호출
             client.close()
        print("Shutdown complete.")


if __name__ == "__main__":
    main()