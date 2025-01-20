"""



"""


import json
import os

from kafka import KafkaProducer, KafkaConsumer

class DataManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.load_config()
        self.producer = None
        self.consumer = None
        self.topic_name_in = None
        self.topic_name_out = None
        self.kafka_connect()

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = json.load(file)

    def kafka_connect(self):
        try:
            # Producer 설정
            self.producer = KafkaProducer(
                bootstrap_servers=self.config['kafka_server'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

            # Consumer 설정
            self.consumer = KafkaConsumer(
                self.config['topic_name_in'],
                bootstrap_servers=self.config['kafka_server'],
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                group_id=self.config['consumer_group_id']
            )

            self.topic_name_in = self.config['topic_name_in']
            self.topic_name_out = self.config['topic_name_out']

            print("Kafka connection successfully established.")
        except Exception as e:
            print(f"Failed to connect to Kafka: {e}")

    def send_data_to_kafka(self, tag_id, posX, posY):
        coord_data = {'id': tag_id, 'latitude': posX, 'longitude': posY}
        self.producer.send(self.topic_name_out, coord_data)
        self.producer.flush()

    def close_producer(self):
        if self.producer is not None:
            self.producer.close()

    def handle_data(self, data):
        tag_id = data.get('tag_id')
        posX = data.get('posX')
        posY = data.get('posY')
        timestamp = data.get('timestamp')
        anchor_info = data.get('anchor_info')

        if tag_id and posX and posY and timestamp and anchor_info:
            self.store_data_in_db(tag_id, posX, posY, timestamp, anchor_info)
            self.send_data_to_kafka(tag_id, posX, posY)
        else:
            print("Received data is missing required fields.")

    def consume_and_process_data(self):
        for message in self.consumer:
            data = message.value
            print(f"Received data: {data}")
            self.handle_data(data)


def main():
    config_path = os.getenv('CONFIG_PATH', '/home/netai/Omniverse/ext_comms/backend_server/config.json')

    manager = DataManager(config_path)

    try:
        manager.consume_and_process_data()
    finally:
        manager.close_producer()

if __name__ == "__main__":
    main()
