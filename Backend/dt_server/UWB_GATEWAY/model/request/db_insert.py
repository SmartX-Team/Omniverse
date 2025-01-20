"""

DB 에 데이터 삽입을 위한 데이터 모델 정의
--- 최초 작성일 :2024.05.12 송인용 ---

DB 에 데이터 삽입을 위한 데이터 모델 정의

"""

class InsertMovementsByDashboard:
    def __init__(self, tag_id:int, start_timestamp:float, end_timestamp:float, x_position_start:float, y_position_start:float, x_position_end:float, y_position_end:float, line_id:int):
        self.tag_id:int = tag_id
        self.start_timestamp:float = start_timestamp
        self.end_timestamp:float = end_timestamp
        self.x_position_start:float = x_position_start
        self.y_position_start:float = y_position_start
        self.x_position_end:float = x_position_end
        self.y_position_end:float = y_position_end
        self.line_id:int = line_id