"""

별도 IMU와 같은 추가적인 센서가 없을때 UWB 센서 데이터를 처리하는 Filter 함수이다.

구현하다보니 Filter에서 카프카 송신같은 로직도 같이 구현하게 되었는데 가능하면 기능 분리 부탁

--- 작성일 :2024.05.12 송인용 ---

별도 추가 센서 데이터가 없을떄 UWB 센서 데이터를 처리하는 Filter 함수이다.
tag id 별로 데이터를 처리하고

"""

from collections import defaultdict # 일반 dict 가 달리 키가 없으면 자동 생성
import numpy as np
import json
import asyncio
from abc import ABC, abstractmethod



class Filter:
    from model.data.uwb import Uwb_data, Space_bounds
    def __init__(self):
        self.data_map = defaultdict(list)
        self.lock = asyncio.Lock()
        self.task = None
        

    async def add_data(self, uwb_data:Uwb_data):
        """특정 tag_id에 대한 좌표 데이터를 추가합니다."""
        async with self.lock:
            self.data_map[uwb_data.tag_id].append((uwb_data))


    # 이동경로 벗어난 데이터 필터링
    async def check_space_bound_out(self, tag_id, space_bound:Space_bounds):
        """
        Remove movements that are outside the space bounds.
        :param movements: List of tuples, each containing (orientation_z, uwb_x, uwb_y, timestamp)
        :param space_bound: Dictionary with 'x_min', 'x_max', 'y_min', 'y_max'
        :return: Filtered movements and removed movements
        """
        filtered = []
        removed = []
        data = self.data_map[tag_id]
        for movement in data:
            # 올바른 인덱스를 사용하여 x, y 값을 추출합니다.
            x = movement.x_position
            y = movement.y_position

            if space_bound['x_min'] <= x <= space_bound['x_max'] and space_bound['y_min'] <= y <= space_bound['y_max']:
                filtered.append(movement)
            else:
                removed.append(movement)


        #print(f"Removed {len(removed)} movements outside the space bounds.")
        return filtered, removed
    
    @abstractmethod
    async def calculate_filter(self):
        """서브클래스에서 구현해야하는 filter를 통한 계산 메서드."""
        pass

class AverageFilter(Filter) :

    def __init__(self, avg_time:float):
        from model.data.uwb import Space_bounds
        super().__init__()
        self.avg_time = avg_time
        self.avg_data = defaultdict(list)
        self.tag_averages = {}
        self.space_bound = Space_bounds(0, 28, -27, 0) # DB 에도 저장한 Dream-AI 전체 상대좌표값이다. 당장은 변경 로직이 필요없어서 우선 고정해둠

    async def calculate_average(self):
            with self.lock:
                for tag_id, uwb_data in self.data_map.items():
                    if uwb_data:
                        
                        filtered_data = self.check_space_bound_out(tag_id, self.space_bound)
                        
                        if filtered_data.size > 0:
                            avg_posX = np.mean(filtered_data[:, 0])
                            avg_posY = np.mean(filtered_data[:, 1])
                            avg_posX_formatted = "{:.2f}".format(avg_posX)
                            avg_posY_formatted = "{:.2f}".format(avg_posY)
                            print(f"Filtered Average for tag {tag_id}: posX={avg_posX_formatted}, posY={avg_posY_formatted}")

                        self.data[tag_id] = []  # Reset the list after calculating the average      
    

    async def calculate_filter(self):
        """각 tag_id에 저장된 데이터의 평균을 계산하고 리셋합니다."""
        averages = {}
        with self.lock:
            for tag_id, uwb_data in self.data_map.items():
                if uwb_data:
                    filtered_data = self.check_space_bound_out(tag_id, self.space_bound)
                    data = np.array(filtered_data)
                    current_avg = np.mean(data, axis=0)  # x, y 축에 대한 평균 계산
                    averages[tag_id] = current_avg
                    self.data_map[tag_id] = []  # 평균 계산 후 데이터 리셋
        return averages
    

    async def start_periodic_average_calculation(self):
        """주기적으로 평균을 계산하는 비동기 태스크를 시작"""
        while True:
            await self.calculate_average()
            await asyncio.sleep(self.avg_time)


    def update_avg_time(self, new_avg_time):
        """avg_time 값을 업데이트하고 주기적인 평균 계산을 재시작"""
        self.avg_time = new_avg_time
        if self.task:
            self.task.cancel()  # 현재 실행 중인 태스크를 취소
        self.task = asyncio.create_task(self.start_periodic_average_calculation())


    