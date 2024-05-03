"""


--- 작성일 :2024.04.30 송인용 ---

심플하게 DB 연결하고 UWB 데이터 들어오는대로 table에 집어넣는 코드

Wwebsocket_raw.py 랑 같이 넣어서 간단하게 UWB 움직일때마다 DB에 적재하는 간단한 컨테이너로 만듬

"""


import json
import psycopg2
from Websocket_raw import SewioWebSocketClient
import os

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

    def store_data_in_db(self, tag_id, posX, posY, timestamp):
        query = """
        INSERT INTO uwb_raw (tag_id, x_position, y_position, timestamp) VALUES (%s, %s, %s, %s)
        """
        self.cursor.execute(query, (tag_id, posX, posY, timestamp))
        self.conn.commit()

    def handle_data(self, tag_id, posX, posY, timestamp):
        #print(f"Data received: Tag ID={tag_id}, Position X={posX}, Position Y={posY}, Timestamp={timestamp}")
        self.store_data_in_db(tag_id, posX, posY, timestamp)

def main():
    url = "ws://www.sewio-uwb.svc.ops.openark/sensmapserver/api"
    config_path = os.getenv('CONFIG_PATH', '/home/netai/dt_server/UWB_EKF/config.json')

    manager = DataManager(config_path)

    client = SewioWebSocketClient(url, calc_avg=False, store_db=True, data_callback=manager.handle_data)
    client.run_forever()

if __name__ == "__main__":
    main()
