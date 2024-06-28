"""

실제 처리에 필요한 데이터 모델들을 정의하는 파일

--- 최초 작성일 :2024.05.12 송인용 ---

requeqst 랑 모호한 간격이 있을 수 있는데 나중에 리팩토링 부탁

"""



from enum import Enum
from datetime import datetime

import json

# 데이터 타입을 정의하는 Enum
# 기본적으로 평균 필터 적용할지, 로봇처럼 IMU 센서 달려있으면 최대한 빠르게 Real time 으로 처리할지등 규칙 정의용
class DataType(str, Enum):
    Average = "Average"
    Imu = "Imu"
    Raw = "UWBRaw"

# EKF 연산을 위해 필요한 UWB 와 IMU 센서의 데이터 모델(IMU 센서는 UWB 간격사이에 평균값으로 처리)
class FusionUWBandIMUavg:
    def __init__(self, avg_yaw:float, uwb_x:float, uwb_y:float, stamp:float, avg_ax:float, avg_ay:float):
        self.avg_yaw:float = avg_yaw # IMU 센서의 yaw 값
        self.uwb_x:float = uwb_x # UWB 센서의 x 좌표
        self.uwb_y:float = uwb_y # UWB 센서의 y 좌표
        self.stamp:float = stamp # UWB 데이터가 생성된 Unix 타임 스탬프
        self.avg_ax:float = avg_ax # IMU 센서의 x 축 가속도
        self.avg_ay:float = avg_ay # IMU 센서의 y 축 가속도

# UWb Tag 정보를 저장하는 데이터 모델 
class Tag:
    def __init__(self, tag_id:int, kube_id:str, nuc_id:str) :
        self.tag_id:int = tag_id
        self.kube_id:str = kube_id
        self.nuc_id:str = nuc_id

# 공간 내의 좌표 정보를 저장하는 데이터 모델
class Space_bounds:
    def __init__(self, x_position_min:float, x_position_max:float, y_position_min:float, y_position_max:float) :
        self.x_position_min:float = x_position_min
        self.x_position_max:float = x_position_max
        self.y_position_min:float = y_position_min
        self.y_position_max:float = y_position_max
   
# 실제 로봇을 움직이는 경로
class Mea_line:
    def __init__(self, line_id:int, x_position_start:float, x_position_end:float, y_position_start:float, y_position_end:float) :
        self.line_id:int = line_id
        self.x_position_start:float = x_position_start
        self.x_position_end:float = x_position_end
        self.y_position_start:float = y_position_start
        self.y_position_end:float = y_position_end

# tag 속성을 불러오는 데이터 모델
class Tag_attribue:
    def __init__(self, tag_id:int, kube_id:str, nuc_id:str, data_type:DataType) :

        self.tag_id:int = tag_id
        self.kube_id:str = kube_id
        self.nuc_id:str = nuc_id
        self.data_type:DataType = data_type

# 기본 연산에 필요한 UWB 데이터 모델 계산은 편하게할려고 Unix 타임으로 받아옴
class Uwb_data:
    def __init__(self, tag_id:int, x_position:float, y_position:float, stamp:float) :
        self.tag_id:int = tag_id
        self.x_position:float = x_position
        self.y_position:float = y_position
        self.stamp:float = stamp

# Omniverse에 전송하기 위한 KAFKA 에 보내는 데이터 모델
class Omniverse_uwb_data:
    def __init__(self, tag_id:int, x_position:float, y_position:float, nuc_id:str) :
        self.tag_id:int = tag_id
        self.x_position:float = x_position
        self.y_position:float = y_position
        self.nuc_id:str = nuc_id 


    def to_json(self):
        """인스턴스를 JSON 문자열로 변환."""
        # 객체의 속성을 딕셔너리로 변환
        data = {
            "tag_id": self.tag_id,
            "x_position": self.x_position,
            "y_position": self.y_position,
            "nuc_id": self.nuc_id
        }
        # 딕셔너리를 JSON 문자열로 변환
        return json.dumps(data)
