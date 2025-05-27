"""

--- 작성일 :2024.05.03 송인용 ---

도커 컨테이너가 보니까 죽어 있다.
로그상으로는 별 문제가 없던데 일단 적어도 컨테이너가 돌아가는동안은 수집은 문제 없으니 사용하다가 언제 메모리 이슈라도 발생하는건지 체크해봐야한다.
기존 OpenARK 연동한 footprint도 시간 지나면 죽길래 이번 프젝에서 별도로 만들어서 사용했던것도 있는데, 어쩌면 갑자기 죽는 이유 분석하다보면 기존 footprint 돌연사 문제도 해결 가능할거 같다.

--- 작성일 :2024.04.30 송인용 ---

해당 코드는 24.04.30 부터 움직이는 UWB tag 정보를 계속 수집하기 위해 Docker Container로 돌아가도록 함

--- 작성일 :2024.04.29 송인용 ---

웹소켓 이벤트 처리기:
on_message: 서버로부터 메시지를 받으면 JSON 형태로 파싱하고, 태그 ID 및 위치 데이터(X, Y 좌표)를 추출하여 처리한다
on_error: 웹소켓 에러 발생 시 에러 메시지를 출력한다.
on_close: 웹소켓 연결이 종료되면 자동으로 재연결을 시도한다.
on_open: 웹소켓 연결이 성공하면 서버에 데이터 구독 요청을 인증키랑 함께 보낸다.

스케줄링 및 재연결 관리:
ensure_scheduler_running: 스케줄러가 활성 상태인지 확인하고 필요하면 시작합니다.
start_scheduler: 일정 시간 간격으로 평균을 계산하는 타이머를 설정합니다.
reconnect 및 run_forever: 웹소켓 연결이 끊기거나 에러가 발생했을 때 자동으로 재연결을 시도합니다.

데이터 관리 및 평균 계산:

평균 필터 테스트로 calculate_average 메서드를 호출하여 저장된 데이터의 평균을 계산하고, 평균에서 벗어나는 이상치를 제거하고 이때 numpy를 사용하여 평균과 표준편차를 계산하는 작업을 같이 구현해서 사용해봤다.
근데 그렇게 유의미한거 같지도 않고 빠르게 EKF 작업으로 넘어갈려고 그 이상 개발은 진행하지 않았다.

"""

import websocket
import time
import json
from collections import defaultdict # 일반 dict 가 달리 키가 없으면 자동 생성
import threading
import numpy as np
import os
import signal
import sys # sys.exit()를 위해 추가

class SewioWebSocketClient_v2:
    def __init__(self, url, data_callback=None): # config_path 제거
        self.url = url
        self.api_key = os.getenv('SEWIO_API_KEY')
        # SEWIO_RECONNECT_DELAY를 int로 변환, 없으면 기본값 5초
        try:
            self.reconnect_delay = int(os.getenv('SEWIO_RECONNECT_DELAY', '5'))
        except ValueError:
            print("Warning: Invalid SEWIO_RECONNECT_DELAY value. Using default 5 seconds.")
            self.reconnect_delay = 5

        if not self.api_key:
            print("ERROR: SEWIO_API_KEY environment variable not set.")
            # Sewio 클라이언트가 API 키 없이 제대로 동작하지 않을 수 있으므로, 여기서 종료하거나 예외 발생
            sys.exit(1) 

        # self.lock = threading.Lock() # 현재 코드에서는 직접 사용되지 않음
        self.data_callback = data_callback
        self.running = True
        self.ws = None # ws 객체 초기화

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        print(f"SewioWebSocketClient_v2 initialized. URL: {self.url}, ReconnectDelay: {self.reconnect_delay}s")


    def signal_handler(self, sig, frame):
        print(f'Signal {sig} received. Stopping client...')
        self.stop()

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            tag_id = data["body"]["id"]
            posX = float(data["body"]["datastreams"][0]["current_value"].replace('%', ''))
            posY = float(data["body"]["datastreams"][1]["current_value"].replace('%', ''))
            timestamp = data["body"]["datastreams"][0]["at"]
            
            if "extended_tag_position" in data["body"]:
                anchor_info = json.dumps(data["body"]["extended_tag_position"])
            else:
                anchor_info = json.dumps({})

            if self.data_callback:
                self.data_callback(tag_id, posX, posY, timestamp, anchor_info)
        except Exception as e:
            print(f"Error processing message: {e}\nMessage: {message}")


    def on_error(self, ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        # close_status_code와 close_msg가 None으로 올 수 있음
        status_msg = f"Status: {close_status_code}, Msg: {close_msg}" if close_status_code is not None else "Connection closed."
        print(f"### WebSocket closed. {status_msg} ###")
        # self.running 플래그에 따라 재연결 로직은 run_forever 루프에서 처리

    def on_open(self, ws):
        print("WebSocket connection opened.")
        subscribe_message = f'{{"headers": {{"X-ApiKey": "{self.api_key}"}}, "method": "subscribe", "resource": "/feeds/"}}'
        try:
            ws.send(subscribe_message)
            print("Subscription message sent.")
        except Exception as e:
            print(f"Failed to send subscription message: {e}")


    def stop(self):
        print("Stopping WebSocket client...")
        self.running = False
        if self.ws:
            try:
                self.ws.close() # WebSocketApp의 close 호출
            except Exception as e:
                print(f"Error closing WebSocket: {e}")
        print("WebSocket client has been signaled to stop.")


    def run_forever(self):
        while self.running:
            print(f"Attempting to connect to WebSocket: {self.url}")
            try:
                self.ws = websocket.WebSocketApp(self.url,
                                                on_open=self.on_open,
                                                on_message=self.on_message,
                                                on_error=self.on_error,
                                                on_close=self.on_close)
                self.ws.run_forever(ping_interval=60, ping_timeout=10) # Keepalive 추가
            except Exception as e: # WebSocketApp 생성 또는 run_forever 내부의 예외
                print(f"WebSocketApp run_forever error: {e}")
            
            if self.running: # stop()이 호출되지 않은 경우에만 재연결 시도
                print(f"Disconnected. Attempting to reconnect in {self.reconnect_delay} seconds...")
                # time.sleep() 중 SIGINT/SIGTERM을 받을 수 있도록 루프 사용
                for _ in range(self.reconnect_delay):
                    if not self.running:
                        break
                    time.sleep(1)
            if not self.running:
                print("Exiting run_forever loop as client is stopped.")
                break
        print("WebSocket client run_forever loop finished.")

"""
WebSocket 기반 Raw Data
calc_avg = True  # 평균값 계산후 전송 기능을 활성화
store_db = True  # 데이터베이스에 저장용 데이터 전송을 활성화

""" 
class SewioWebSocketClient:

    def __init__(self, url, calc_avg=False, store_db=False, data_callback=None):
        config_path = os.getenv('CONFIG_PATH', '/home/netai/Omniverse/dt_server/UWB_EKF/config.json')
        with open(config_path, 'r') as file:
            self.config = json.load(file)

        # 처리 할 것인지 정의
        self.calc_avg = calc_avg
        self.store_db = store_db

        self.url = url
        self.reconnect_delay = self.config['reconnect_delay']  # 재연결 시도 간격(초)
        self.avg_time = self.config['avg_time'] # 평균 내는 구간 간격
        self.data_map = defaultdict(list)
        self.lock = threading.Lock()
        self.tag_averages = {}  # 각 태그의 평균값을 저장할 딕셔너리
        self.data_callback = data_callback # DB 저장용 콜백함수

        # Kafka
        self.bootstrap_servers = self.config['kafka_server']
        self.topic_name = self.config['topic_name']
        self.producer = None

    def on_message(self, ws, message):
        #print("Received:", message)
        data = json.loads(message)
        tag_id = data["body"]["id"]
        posX = float(data["body"]["datastreams"][0]["current_value"].replace('%', ''))
        posY = float(data["body"]["datastreams"][1]["current_value"].replace('%', ''))
        timestamp = data["body"]["datastreams"][0]["at"]

        # DB 저장용으로 받는다는 설정 키면 call_back 함수로 처리
        if self.store_db and self.data_callback:
            self.data_callback(tag_id, posX, posY, timestamp)

        #print(f"Average for tag {tag_id}: posX={posX}, posY={posY}")
        with self.lock:
            self.data_map[tag_id].append((posX, posY))

    def on_error(self, ws, error):
        print("Error:", error)

    def on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")
        self.reconnect()

    def on_open(self, ws):
        print("Opened connection")
        subscribe_message = f'{{"headers": {{"X-ApiKey": "{self.config["X-ApiKey"]}"}}, "method": "subscribe", "resource": "/feeds/"}}'
        ws.send(subscribe_message)
        self.ensure_scheduler_running()

    def ensure_scheduler_running(self):
    # 타이머가 이미 실행 중인지 확인하고, 실행 중이지 않으면 시작 calc_avg False면 평균값 계산 처리 안함
        if self.calc_avg and (not hasattr(self, 'timer') or not self.timer.is_alive()):
            self.start_scheduler()

    def run_forever(self):
        while True:
            self.ws = websocket.WebSocketApp(self.url,
                                             on_open=self.on_open,
                                             on_message=self.on_message,
                                             on_error=self.on_error,
                                             on_close=self.on_close)
            self.ws.run_forever()
            time.sleep(self.reconnect_delay)  # 재연결 전 딜레이
            self.ensure_scheduler_running()

    def reconnect(self):
        print("Attempting to reconnect in {} seconds...".format(self.reconnect_delay))
        time.sleep(self.reconnect_delay)  # 재연결 전 딜레이
        self.run_forever()  # 재연결 시도


    def start_scheduler(self):
        self.timer = threading.Timer(self.avg_time, self.calculate_average)
        self.timer.start()

    def calculate_average(self):
            with self.lock:
                for tag_id, positions in self.data_map.items():
                    if positions:
                        
                        data = np.array(positions)
                        mean = np.mean(data, axis=0)
                        std = np.std(data, axis=0)
                        
                        # 이상치 필터링: 평균 ± 2 * 표준편차 범위를 벗어나는 값은 제거
                        filtered_data = data[(data[:, 0] >= mean[0] - 2 * std[0]) & (data[:, 0] <= mean[0] + 2 * std[0]) & 
                                            (data[:, 1] >= mean[1] - 2 * std[1]) & (data[:, 1] <= mean[1] + 2 * std[1])]
                        
                        if filtered_data.size > 0:
                            avg_posX = np.mean(filtered_data[:, 0])
                            avg_posY = np.mean(filtered_data[:, 1])
                            avg_posX_formatted = "{:.2f}".format(avg_posX)
                            avg_posY_formatted = "{:.2f}".format(avg_posY)
                            print(f"Filtered Average for tag {tag_id}: posX={avg_posX_formatted}, posY={avg_posY_formatted}")

                        self.data_map[tag_id] = []  # Reset the list after calculating the average

            self.start_scheduler()  # Reschedule the timer        
    
    def calculate_average_filter(self):
        with self.lock:
            for tag_id, positions in self.data_map.items():
                if positions:

                    data = np.array(positions)

                    # 태그별 이전 평균을 계산하거나 초기화
                    if tag_id in self.tag_averages:
                        old_avg = self.tag_averages[tag_id]
                    else:
                        # 처음 데이터를 받았을 때 초기 평균을 설정
                        old_avg = np.mean(data, axis=0)
                        self.tag_averages[tag_id] = old_avg

                    # 새로운 평균 계산
                    current_avg = np.mean(data, axis=0)
                    # 이상치 검사를 위한 임계값 계산 (예: 이전 평균의 ±10%)
                    if np.all(np.abs(current_avg - old_avg) <= np.abs(0.1 * old_avg)):
                        self.tag_averages[tag_id] = current_avg  # 평균 업데이트
                        avg_posX, avg_posY = current_avg
                        avg_posX_formatted = "{:.2f}".format(avg_posX)
                        avg_posY_formatted = "{:.2f}".format(avg_posY)
                        print(f"Filtered Average for tag {tag_id}: posX={avg_posX_formatted}, posY={avg_posY_formatted}")
                    else:
                        print(f"Outlier detected for tag {tag_id}, using previous average.")
                        avg_posX, avg_posY = old_avg
                        avg_posX_formatted = "{:.2f}".format(avg_posX)
                        avg_posY_formatted = "{:.2f}".format(avg_posY)
                        print(f"Using old average for tag {tag_id}: posX={avg_posX_formatted}, posY={avg_posY_formatted}")

                    self.data_map[tag_id] = []  # Reset the list after calculating the average

        self.start_scheduler()