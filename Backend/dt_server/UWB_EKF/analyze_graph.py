"""

--- 작성일 :2024.04.30 송인용 ---

측정한 movements 데이터들을 실제 움직인 경로 path 에 맞춰 그래프로 그려주는 코드 모음
해당 코드는 지속적으로 확장하면서 논문에 사용할 그래프 만드는 코드로 사용 계획


"""


import json
import matplotlib.pyplot as plt
from time_util import TimeUtil
from db_stat import DBStatManager

class DrawGraph:
    def __init__(self, config_path):
        self.config_path = config_path
        self.load_config()
        self.db_stat_manager = DBStatManager(self.config_path)  # DBStatManager 인스턴스 생성

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = json.load(file)

    def draw_movement_path(self, tag_id, start=None, end=None):
        # 데이터 가져오기
        movements = self.db_stat_manager.get_tag_movements(tag_id, start, end)

        # x, y 좌표 리스트 준비
        x_coords = [float(movement[0]) for movement in movements]
        y_coords = [float(movement[1]) for movement in movements]

        # 그래프 그리기
        plt.figure(figsize=(10, 5))
        plt.plot(x_coords, y_coords, marker='o', linestyle='-', color='b')  # 선과 점으로 경로 그리기
        if movements:
            # 마지막 점에 화살표 추가
            plt.annotate('End', 
                         (x_coords[-1], y_coords[-1]),
                         textcoords="offset points", 
                         xytext=(0,10), 
                         ha='center', 
                         arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=.5', color='r'))


        x_min = self.config['space_bounds']['x_min']
        x_max = self.config['space_bounds']['x_max']
        y_min = self.config['space_bounds']['y_min']
        y_max = self.config['space_bounds']['y_max']

        # 좌표 축 설정
        plt.xlim(x_min, x_max)
        plt.ylim(y_max, y_min)  # y 축 반전
        
        plt.title(f'Movement Path for Tag {tag_id}')
        plt.xlabel('X Coordinate')
        plt.ylabel('Y Coordinate')
        plt.grid(True)
        plt.savefig('/home/netai/dt_server/UWB_EKF/test.jpg')
        plt.close()  # 현재 그래프 닫기 (리소스 해제)

if __name__ == "__main__":
    draw_graph = DrawGraph('/home/netai/Omniverse/dt_server/UWB_EKF/config.json')
    timeutil = TimeUtil(timezone_offset='9')

    start, end = timeutil.calculate_time_bounds( end='2024-04-30T12:45:30.500')



    draw_graph.draw_movement_path('11', start, end)  # 그래프 그리기

         