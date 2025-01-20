"""


--- 작성일 :2024.05.12 송인용 ---

기존 버그는 좀 고치고 Collection 코드는 유지하기로 해서 Signal 신호 처리 로직 추가해서 안정성 추가

--- 작성일 :2024.04.30 송인용 ---

심플하게 DB 연결하고 UWB 데이터 들어오는대로 table에 집어넣는 코드

Wwebsocket_raw.py 랑 같이 넣어서 간단하게 UWB 움직일때마다 DB에 적재하는 간단한 컨테이너로 만듬

"""

import json
import psycopg2
from Websocket_raw import  SewioWebSocketClient_v2
import os
from kafka import KafkaProducer

"""

MVC 신경 안쓰고 오르지 Sewio RLTS 에서 데이터 넘어오면 DB만 적재하도록 작성된 코드

"""
class DataManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.load_config()

        self.producer = None
        self.topic_name = None
        self.db_connect()
        self.kafka_connect()

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = json.load(file)

    def db_connect(self):
        try:
            self.conn = psycopg2.connect(
                dbname=self.config['postgres']['db_name'],
                user=self.config['postgres']['db_user'],
                password=self.config['postgres']['db_password'],
                host=self.config['postgres']['db_host'],
                port=self.config['postgres']['db_port']
            )
            self.cursor = self.conn.cursor()
            print("Database connection successfully established.")
        except Exception as e:
            print(f"Failed to connect to the database: {e}")

    def kafka_connect(self):
        try:
            self.producer = KafkaProducer(bootstrap_servers=self.config['kafka']['bootstrap_servers'],
                                          value_serializer=lambda v: json.dumps(v).encode('utf-8'))
            self.topic_name = self.config['kafka']['uwb_rlts']['topic']

            print("Kafka connection successfully established.")
        except Exception as e:
            print(f"Failed to connect to Kafka: {e}")

    def send_data_to_kafka(self, tag_id, posX, posY):
        # 데이터를 JSON 문자열로 변환합니다.
        coord_data = {'id': tag_id, 'latitude': posX, 'longitude': posY}
        self.producer.send(self.topic_name, coord_data)
        self.producer.flush()

    def close_producer(self):
        if self.producer is not None:
            self.producer.close()

    def store_data_in_db(self, tag_id, posX, posY, timestamp, anchor_info):
        query = """
        INSERT INTO uwb_raw (tag_id, x_position, y_position, timestamp, anchor_info) VALUES (%s, %s, %s, %s, %s)
        """
        self.cursor.execute(query, (tag_id, posX, posY, timestamp, anchor_info))
        self.conn.commit()

    def handle_data(self, tag_id, posX, posY, timestamp, anchor_info):
        #print(f"Data received: Tag ID={tag_id}, Position X={posX}, Position Y={posY}, Timestamp={timestamp}")
        self.store_data_in_db(tag_id, posX, posY, timestamp, anchor_info)
        self.send_data_to_kafka(tag_id, posX, posY)


def main():
    url = "ws://10.76.20.88/sensmapserver/api"
    config_path = os.getenv('CONFIG_PATH', '/mnt/ceph-pvc/config.json')

    manager = DataManager(config_path)

    client = SewioWebSocketClient_v2(url, data_callback=manager.handle_data, config_path=config_path)
    try:
        client.run_forever()
    finally:
        manager.close_producer()

if __name__ == "__main__":
    main()
