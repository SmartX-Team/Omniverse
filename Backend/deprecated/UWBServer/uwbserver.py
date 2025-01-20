"""
UWB Info를 실시간으로 받아오면서 Redis 서버에 저장하는 서버
Docker Container로 실행

2023 년도 처음 Omniverse 사용하면서 Redis로 UWB 데이터 전달하는 서버 코드이다.
현재는 deprecated 되었다.

"""

import requests
import threading
import time
from queue import Queue
import redis
import json
import os

# Redis 서버 접속 정보가 환경 변수로 존재한다면 가져온다.
redis_host = os.getenv('REDIS_HOST', '10.32.187.108')
MAP_DATA =(
    "cafd5a3e-19ba-3a14-df21-1c697ad50493,24",
    "18e1df49-96e8-8e0b-edb6-1c697ad506b6,40",
    "13011dc2-7ced-e6c1-150b-1c697ad507a6,39",
    "efdb1771-5f9f-a027-d863-1c697ad5013e,37",
    "653fbdde-3267-14f1-360e-1c697ad502d0,36",
    "0adbb676-cb42-0882-ce12-1c697ad506cb,31",
    "37dd943b-4abb-a777-224b-1c697ad50558,49",
    "784a8a47-0153-1f8a-ffd3-1c697ad50485,25",
    "90a0fd91-ade8-69bc-f4a1-1c697ad5079b,44",
    "b80cc5d8-e1be-f6b8-a03e-1c697ad5015f,23",
    "fc1258ba-b25c-2724-d6d7-1c697ad99de0,20",
    "fe47eb1b-cf4c-f3fb-5057-1c697ad99f56,22",
    "02ca34fa-a216-9a2b-2a0a-1c697ad8c177,46",
    "9bc3697d-072e-dc48-29fb-1c697ad99e51,19",
    "9bcc45d1-c926-ab80-b3c0-1c697ad99d94,45",
    "92404821-7051-5c93-90bd-1c697ad8c045,29",
    "9f351faf-d85c-e39e-1e64-1c697ad8c10d,18",
    "5c85978f-e920-9ebf-9334-1c697ad8c107,33",
    "da454806-2e36-f088-f10e-1c697ad8c03f,43",
    "3adacb41-faad-9484-7477-1c697ad8c17d,26",
    "99effe4d-6ea9-56a4-c5c8-1c697ad99dc1,48",
    "a9fa482b-1e0a-e75e-2236-1c697ad99f5f,41",
    "11b95e87-0f9f-391b-2357-1c697ad8bfea,21",
    "ffb521e3-8dea-0d79-65fb-1c697ad8c124,35",
    "e4020aba-4b62-55fa-1362-1c697ad99df2,47",
    "cb47d8b7-008b-d945-c9e1-1c697ad8c0b9,38",
    "1e35b5a9-ca19-33f3-94b3-1c697ad99f0c,9",
    "5f0e2f32-c2f8-e3a8-a6f9-1c697ad8c015,34",
    "895927f7-5f36-b840-731e-1c697ad99eb0,32",
    "c2136df7-8483-22eb-3210-1c697ad99e00,42"
)
# API endpoint 및 headers 정보
BASE_URL = "http://www.sewio-uwb.svc.ops.openark/sensmapserver/api/tags/{}"
headers = {
    'X-Apikey': '17254faec6a60f58458308763'
}

# Redis 서버에 연결
r = redis.StrictRedis(host=redis_host, port=6379, db=0)

data_queue = Queue()

saved_map = dict()

# 첫 번째 스레드: 주기적으로 rest api를 통해 데이터를 가져온다.
def fetch_data():

    while True:
        ids = [item.split(",")[1] for item in MAP_DATA]
        for id_ in ids:
            url = BASE_URL.format(id_)
            response = requests.get(url, headers=headers)
            response_data = response.json()
            
            temp_data_object = {
                "id": response_data["id"],
                "alias": response_data["alias"]
            }
            for datastream in response_data['datastreams']:
                if datastream['id'] == 'posX':
                    temp_data_object["posX"] = float(datastream['current_value'].strip())
                elif datastream['id'] == 'posY':
                    temp_data_object["posY"] = float(datastream['current_value'].strip())

            data_queue.put(temp_data_object)

        time.sleep(1)

# 두 번째 스레드에서 수행할 작업 : 움직인 uwb 장치의 정보를 redis 서버에 저장한다.
def send_to_omniverse():
    while True:
        data = data_queue.get()  # 큐에서 데이터 추출
        key = data['alias']

        if key in saved_map:
            value = saved_map[key]
            if value['posX'] != data['posX'] or value['posX'] != data['posX'] :
                saved_map[key] = data
                serialized_data = json.dumps(saved_map[key]) 
                r.lpush('uwb_queue', serialized_data)
                r.ltrim('uwb_queue', 0, 100)
                print(saved_map[key])

        else:
            saved_map[data['alias']] = data

thread1 = threading.Thread(target=fetch_data)
thread2 = threading.Thread(target=send_to_omniverse)

thread1.start()
thread2.start()

thread1.join()
thread2.join()