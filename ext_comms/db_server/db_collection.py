"""


--- 작성일 :2024.09.05 송인용 ---
 기존 DB 연결 작업 

"""

import json
import psycopg2
import os
from kafka import KafkaConsumer

"""

MVC 신경 안쓰고 오르지 외부에서 UWB 데이터 받아오는 Kafka topic uwb-raw-out 의 데이터를 DB에만 적재하도록 작성된 코드

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
            self.consumer = KafkaConsumer(
                self.config['topic_name_out'],  # Kafka topic to consume from
                bootstrap_servers=self.config['kafka_server'],
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id='my-consumer',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print("Kafka consumer successfully established.")
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

    config_path = os.getenv('CONFIG_PATH', '/home/netai/Omniverse/ext_comms/db_server/config.json')

    manager = DataManager(config_path)



if __name__ == "__main__":
    main()
