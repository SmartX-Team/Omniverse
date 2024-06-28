"""

--- 작성일 :2024.05.12 송인용 ---

기존 로컬에서 Collection으로 작성하던 코드인데 UWB_GATEWAY 라는 서비스 만들면서 같이 통합했다.
여기서 기존에 reconnect 에서 재귀호출로 인해 스택 오버플로우 문제가 발생된다고 추정되어서 해당 부분 같이 수정해둠
또한 평균값 필터같은 부분도 별도로 분리해둠

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

from utils import TimeUtil

"""
WebSocket 기반 Raw Data
calc_avg = True  # 평균값 계산후 전송 기능을 활성화
store_db = True  # 데이터베이스에 저장용 데이터 전송을 활성화

""" 
class SewioWebSocketClient_v2:
    
    def __init__(self, url, data_callback=None):
        config_path = os.getenv('CONFIG_PATH', '/home/netai/Omniverse/dt_server/UWB_EKF/config.json')
        with open(config_path, 'r') as file:
            self.config = json.load(file)
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

        self.time_util = TimeUtil()

    async def on_message(self, ws, message):
        from model.data.uwb import Uwb_data
        #print("Received:", message)
        data = json.loads(message)
        tag_id = data["body"]["id"]
        posX = float(data["body"]["datastreams"][0]["current_value"].replace('%', ''))
        posY = float(data["body"]["datastreams"][1]["current_value"].replace('%', ''))
        timestamp = self.time_util.convert_to_unix_time(data["body"]["datastreams"][0]["at"])

        await self.data_callback.receive_message(Uwb_data(tag_id, posX, posY, timestamp))

    def on_error(self, ws, error):
        print("Error:", error)

    def on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")

    def on_open(self, ws):
        print("Opened connection")
        subscribe_message = f'{{"headers": {{"X-ApiKey": "{self.config["X-ApiKey"]}"}}, "method": "subscribe", "resource": "/feeds/"}}'
        ws.send(subscribe_message)

    def run_forever(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(self.url,
                                                on_open=self.on_open,
                                                on_message=self.on_message,
                                                on_error=self.on_error,
                                                on_close=self.on_close)
                self.ws.run_forever()
            except Exception as e:
                print(f"Error: {e}")
            print("Attempting to reconnect in {} seconds...".format(self.reconnect_delay))
            time.sleep(self.reconnect_delay)  # 재연결 전 딜레이
