"""

웹소켓에서 데이터 넘어올때 어떻게 처리할지 로직 정하는 data_handle 함수
Kafka 로 데이터 전송하는 로직 추가됨

--- 작성일 :2024.05.12 송인용 ---

Controller 와 Api의 관계가 조금 모호한데, 우선 패키지는 Rest api 만 구분한 api 만 만들고 Controller 라고 볼 수 있는 처리 로직이나 계산 로직들을 core 패키지에 삽입하게됨
해당 코드는 나중에 코드 컨벤션이 확실해지면 다른 패키지로 이전할 수도 있을거 같음



"""
import asyncio

import json
import os
from repository.UWB_repository import UWBRepository




class UWBProcess:
    def __init__(self):
        self.repository = UWBRepository()
        self.tag_store = Tag_attribue_Singleton()

    async def fetch_tag_info(self, tag_id):
        # 메모리에 저장된 정보를 먼저 확인
        tag_info = await self.tag_store.get_data(tag_id)
        if not tag_info:
            # 메모리에 없는 경우 DB에서 가져옴
            tag_info = await self.repository.get_tag_info(tag_id)
            # 가져온 정보를 메모리에 저장
            if tag_info:
                await self.tag_store.update_data(tag_info[0], tag_info[1], tag_info[2])

"""
    async def update_tag_info(self, tag_id, info):
        # DB 업데이트
        await self.repository.update_tag_info(tag_id, info)
        # 메모리 업데이트
        await self.tag_store.update_data(tag_id, info)
"""


"웹소켓 콜백함수용"
class DataHandleCallback:
    from model.data.uwb import Tag_attribue, Uwb_data
    def __init__(self):
        self.UWBProcess = UWBProcess()


    async def receive_message(self, uwb_data:Uwb_data):
        tag_attribue = await self.UWBProcess.tag_store.get_data(uwb_data.tag_id)
        #
        if tag_attribue is None:
            self.UWBProcess.fetch_tag_info(uwb_data.tag_id)
        self.to_kafka_data(uwb_data, tag_attribue)
        #print('data_process')
        #print(self.data)

    async def to_kafka_data(self, uwb_data:Uwb_data, tag_attribue:Tag_attribue):
        from model.data.uwb import Omniverse_uwb_data
        return Omniverse_uwb_data(uwb_data.tag_id, uwb_data.x_position, uwb_data.y_position, tag_attribue.nuc_id)

    def data_save(self):
        pass
        #print('data_save')
        #print(self.data)

    def data_send(self):
        pass
        #print('data_send')
        #print(self.data)


"""카프카 전송을 위한 데이터 모델로 변환"""
class ConvertKafkaDataModel:
    from model.data.uwb import Tag_attribue, Uwb_data
    def __init__(self, uwb_data:Uwb_data, tag_attribue:Tag_attribue):
        self.uwb_data = uwb_data
        self.tag_attribue = tag_attribue

    def to_kafka_data(self):
        from model.data.uwb import Omniverse_uwb_data
        return Omniverse_uwb_data(self.uwb_data.tag_id, self.uwb_data.x_position, self.uwb_data.y_position, self.tag_attribue.nuc_id)

"""Tag id 나 매칭정보들을 관리하는 클래스"""
class Tag_attribue_Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.data_store = {}

        return cls._instance

    async def update_data(self, tag_id, kube_id=None, nuc_id=None):
        from model.data.uwb import Tag_attribue
        """데이터를 비동기적으로 업데이트한다."""
        self.data_store[tag_id] = Tag_attribue(tag_id, kube_id, nuc_id)
        print(f"Data updated: {tag_id} = {self.data_store[tag_id]}")

    async def get_data(self, key):
        
        return self.data_store.get(key, None)
