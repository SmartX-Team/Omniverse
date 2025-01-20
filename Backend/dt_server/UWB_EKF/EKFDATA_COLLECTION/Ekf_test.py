"""

--- 작성일 :2024.05.02 송인용 ---

UWB 데이터 timestamp 와 가장 가까운 IMU 데이터 찾아서 DB에 저장하는 코드
실제 EKF 동작은 분석 및 구현 완료되면 로봇에 탐재할 예정이라 메인 서버에서 작업한 코드라 test라고 분류함


"""


import websocket
import threading
import json
import time
import redis
from time_util import TimeUtil
from db_insert_ekf import DataManager

# 전역 메시지 큐 imu 메시지 계속 저장됨

class SewioWebSocketClient:
    def __init__(self, url, config_path, calc_avg=False, store_db=False, queue_name='imu_0950'):
        with open(config_path, 'r') as file:
            self.config = json.load(file)
        
        self.url = url
        self.calc_avg = calc_avg
        self.store_db = store_db
        self.reconnect_delay = self.config['reconnect_delay']  # 재연결 시도 간격(초)
        self.lock = threading.Lock()
        self.queue_name = queue_name
        self.time_util = TimeUtil()
        self.data_manager = DataManager(config_path)
        self.previous_uwb_timestamp = time.time()
        # 웹소켓 연결
        self.connect()

        # Redis 연결
        self.redis_manager = RedisManager()

    def on_message(self, ws, message):
        data = json.loads(message)
        tag_id = data["body"]["id"]

        
        if tag_id == '15':  # 선택한 태그 ID가 15번인 경우만 처리
            posX = float(data["body"]["datastreams"][0]["current_value"].replace('%', ''))
            posY = float(data["body"]["datastreams"][1]["current_value"].replace('%', ''))
            timestamp = data["body"]["datastreams"][0]["at"]

            with self.lock:
                self.handle_data(tag_id, posX, posY, timestamp, True)  # 스레드 풀에서 데이터 처리
           

    def on_error(self, ws, error):
        print("Error:", error)

    def on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")
        self.reconnect()

    def on_open(self, ws):
        print("Opened connection")
        subscribe_message = f'{{"headers": {{"X-ApiKey": "{self.config["X-ApiKey"]}"}}, "method": "subscribe", "resource": "/feeds/"}}'
        self.ws.send(subscribe_message)


    def connect(self):
        self.ws = websocket.WebSocketApp(self.url,
                                         on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        

        thread = threading.Thread(target=self.ws.run_forever)
        thread.start()

    def cleanup(self):
        print("Cleaning up...")
        self.executor.shutdown(wait=True)  # Executor가 완전히 종료될 때까지 기다림


    def run_forever(self):
        while True:
            self.ws = websocket.WebSocketApp(self.url,
                                             on_open=self.on_open,
                                             on_message=self.on_message,
                                             on_error=self.on_error,
                                             on_close=self.on_close)
            self.ws.run_forever()
            time.sleep(self.reconnect_delay)  # 재연결 전 딜레이

    def reconnect(self):
        print("Attempting to reconnect in {} seconds...".format(self.reconnect_delay))
        time.sleep(self.reconnect_delay)  # 재연결 전 딜레이
        self.run_forever()  # 재연결 시도

        # 인스턴스 생성 및 데이터 처리
    def handle_data(self, tag_id, posX, posY, timestamp, average_imu=False):
        try:
            unix_time = self.time_util.convert_to_unix_time(timestamp)
            print(f"UWB Data received - Tag: {tag_id}, Position X: {posX}, Y: {posY}, Timestamp: {timestamp}", "Unix Time:", unix_time)

            if average_imu:
                # UWB 데이터 타임스탬프 기준 이전 타임스탬프를 찾아서 평균 IMU 데이터를 계산
                
                imu_data = self.calculate_average_imu(self.previous_uwb_timestamp, unix_time)

                self.previous_uwb_timestamp = unix_time

                print(self.previous_uwb_timestamp)

                min_diff = 0

            else :
                closest_data, min_diff = self.find_closest_imu_data(unix_time)

                imu_data = self.redis_manager.get_imudata(closest_data)


            self.data_manager.store_data_in_db( tag_id, posX, posY, timestamp, min_diff, imu_data)

        except RuntimeError as e:
            print(f"Failed to handle data: {e}")

        except Exception as e:
            print(f"Failed to handle data Exception: {e}")

    # UWB 데이터와 timestamp가 가장 가까운 IMU 데이터 찾기
    def find_closest_imu_data(self, uwb_timestamp):
        closest_data = None
        min_diff = float('inf')
        for data in self.redis_manager.get_queue(self.queue_name):
            time_diff = abs(float(data) - uwb_timestamp)
            if time_diff < min_diff:
                min_diff = time_diff
                closest_data = data
        return closest_data, min_diff


    # IMU의 오차를 감안해서 UWB 데이터들의 간격의 timestamp들 평균 계산하여 반환
    def calculate_average_imu(self, start_time, end_time):
        imu_data_list = self.redis_manager.get_imu_data_range(start_time, end_time)

        print(len(imu_data_list))
        if not imu_data_list:
            return None
        avg_ax = sum(data['linear_acceleration_x'] for data in imu_data_list) / len(imu_data_list)
        avg_ay = sum(data['linear_acceleration_y'] for data in imu_data_list) / len(imu_data_list)
        avg_yaw = sum(data['orientation_z'] for data in imu_data_list) / len(imu_data_list)
        return {'ax': avg_ax, 'ay': avg_ay, 'yaw': avg_yaw}
"""
Redis 에 저장되는 IMU 데이터 접근하고 처리할려고 만든 클래스
"""
class RedisManager:
    def __init__(self, host='10.32.187.108', port=6379, db0=0, db1=1, queue_name='imu_0950', retry_delay=5, max_retries=5):
        self.host = host
        self.port = port
        self.db0 = db0
        self.db1 = db1
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.redis_client_db0 = None
        self.redis_client_db1 = None
        self.connect()

    def connect(self):
        self.redis_client_db0 = self.create_redis_client(self.db0)
        print('connected to Redis db0')
        self.redis_client_db1 = self.create_redis_client(self.db1)
        print('connected to Redis db1')

    def create_redis_client(self, db):
        retries = 0
        while retries < self.max_retries:
            try:
                client = redis.StrictRedis(host=self.host, port=self.port, db=db)
                if client.ping():
                    return client
            except redis.ConnectionError:
                time.sleep(self.retry_delay)
                retries += 1
        raise Exception(f"Failed to connect to Redis db{db} after {self.max_retries} attempts")
    
    def progress_queue(self, key):
        while True:
            data = self.redis_client_db0.rpop(key)
            if not data:
                break
            print(f"Processed data: {data.decode()}")
    # db0 의 모든 데이터 가져옴
    def get_queue(self, key):
        # 리스트의 모든 요소를 가져옴
        return [data.decode() for data in self.redis_client_db0.lrange(key, 0, -1)]
    
    # db1 에서 key(Unix timestamp) 에 해당하는 데이터 가져옴
    def get_imudata(self, key):
        # Redis에서 데이터를 가져오고 바이트를 문자열로 디코드
        data_str = self.redis_client_db1.get(key)
        if data_str:
            # JSON 문자열을 파싱하여 Python 딕셔너리로 변환
            return json.loads(data_str.decode())
        return None
    
    def get_imu_data_range(self, start_time, end_time):
        # ZRANGEBYSCORE를 사용하여 주어진 시간 범위에 해당하는 키들을 검색
        keys = self.redis_client_db1.zrangebyscore('imu_data', start_time, end_time)
        if not keys:
            return []

        pipeline = self.redis_client_db1.pipeline()
        for key in keys:
            pipeline.get(key)
        
        results = pipeline.execute()
        imu_data_list = [json.loads(data) for data in results if data]
        return imu_data_list


url = "ws://www.sewio-uwb.svc.ops.openark/sensmapserver/api"
config_path = '/home/netai/Omniverse/dt_server/UWB_EKF/config.json'
client = SewioWebSocketClient(url, config_path)


