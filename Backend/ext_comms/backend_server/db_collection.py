"""


--- 작성일 :2024.05.12 송인용 ---

기존 버그는 좀 고치고 Collection 코드는 유지하기로 해서 Signal 신호 처리 로직 추가해서 안정성 추가

--- 작성일 :2024.04.30 송인용 ---

심플하게 DB 연결하고 UWB 데이터 들어오는대로 table에 집어넣는 코드

Wwebsocket_raw.py 랑 같이 넣어서 간단하게 UWB 움직일때마다 DB에 적재하는 간단한 컨테이너로 만듬

"""

import json
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
        self.kafka_connect()

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = json.load(file)


    def kafka_connect(self):
        try:
            self.producer = KafkaProducer(bootstrap_servers=self.config['kafka_server'],
                                          value_serializer=lambda v: json.dumps(v).encode('utf-8'))
            self.topic_name = self.config['topic_name_in']

            print("Kafka connection successfully established.")
        except Exception as e:
            print(f"Failed to connect to Kafka: {e}")

    def send_data_to_kafka(self, data):
        # 데이터를 JSON 문자열로 변환합니다.
        #coord_data = {'id': tag_id, 'latitude': posX, 'longitude': posY}
        self.producer.send(self.topic_name, data)
        
        self.producer.flush()

    def close_producer(self):
        if self.producer is not None:
            self.producer.close()


def main():
    url = "ws://10.76.20.88/sensmapserver/api"
    config_path = os.getenv('CONFIG_PATH', '/home/netai/Omniverse/ext_comms/backend_server/config.json')

    manager = DataManager(config_path)

    client = SewioWebSocketClient_v2(url, data_callback=manager.send_data_to_kafka, config_path=config_path)
    try:
        client.run_forever()
    finally:
        manager.close_producer()

if __name__ == "__main__":
    main()
