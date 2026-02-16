"""
X_AI Studio 범위 내부에서 이동하는 궤적 데이터를 생성하는 모듈
- 객체 수, 데이터 길이, 간격, 속도 범위 등을 설정하여 궤적 데이터를 생성할 수 있음

사용 방법은 최하단 예시 코드 확인
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

class TrajectoryGenerator:
    def __init__(self, 
                 num_objects=2,
                 duration_minutes=1,
                 interval_seconds=1.0,
                 x_range=(206, 1554),
                 y_range=(89.5, 200),
                 z_range=(-2879, -1258),
                 min_speed=50,
                 max_speed=200):
        """
        궤적 데이터 생성기
        
        Parameters:
        -----------
        num_objects : int
            생성할 객체 수
        duration_minutes : float
            데이터 길이 (분)
        interval_seconds : float
            데이터 간격 (초)
        x_range : tuple
            X축 범위 (min, max)
        y_range : tuple
            Y축 범위 (min, max) - 높이
        z_range : tuple
            Z축 범위 (min, max)
        min_speed : float
            최소 이동 속도 (units/second)
        max_speed : float
            최대 이동 속도 (units/second)
        """
        self.num_objects = num_objects
        self.duration_minutes = duration_minutes
        self.interval_seconds = interval_seconds
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
        self.min_speed = min_speed
        self.max_speed = max_speed
        
        # 총 타임스텝 계산
        self.total_steps = int((duration_minutes * 60) / interval_seconds) + 1
        
        # 객체별 상태 초기화
        self.objects = []
        for i in range(num_objects):
            obj = {
                'id': f'obj{str(i+1).zfill(3)}',
                'position': np.array([
                    random.uniform(*x_range),
                    random.uniform(*y_range),
                    random.uniform(*z_range)
                ]),
                'velocity': self._random_velocity(),
                'speed': random.uniform(min_speed, max_speed),
                'direction_change_counter': 0,
                'direction_change_interval': random.randint(20, 100)
            }
            self.objects.append(obj)
    
    def _random_velocity(self):
        """랜덤한 방향의 단위 벡터 생성"""
        theta = random.uniform(0, 2 * np.pi)  # XZ 평면 각도
        phi = random.uniform(-np.pi/6, np.pi/6)  # Y축 각도 (±30도)
        
        velocity = np.array([
            np.cos(theta) * np.cos(phi),
            np.sin(phi),
            np.sin(theta) * np.cos(phi)
        ])
        return velocity / np.linalg.norm(velocity)
    
    def _check_boundary_collision(self, position):
        """경계 충돌 체크"""
        collisions = []
        if position[0] <= self.x_range[0] or position[0] >= self.x_range[1]:
            collisions.append('x')
        if position[1] <= self.y_range[0] or position[1] >= self.y_range[1]:
            collisions.append('y')
        if position[2] <= self.z_range[0] or position[2] >= self.z_range[1]:
            collisions.append('z')
        return collisions
    
    def _reflect_velocity(self, velocity, collisions):
        """경계에서 속도 벡터 반사"""
        new_velocity = velocity.copy()
        if 'x' in collisions:
            new_velocity[0] *= -1
        if 'y' in collisions:
            new_velocity[1] *= -1
        if 'z' in collisions:
            new_velocity[2] *= -1
        return new_velocity
    
    def _smooth_direction_change(self, current_velocity, target_velocity, smoothness=0.1):
        """부드러운 방향 전환"""
        return (1 - smoothness) * current_velocity + smoothness * target_velocity
    
    def generate(self):
        """궤적 데이터 생성"""
        data = []
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        
        for step in range(self.total_steps):
            timestamp = start_time + timedelta(seconds=step * self.interval_seconds)
            
            for obj in self.objects:
                # 현재 위치 기록
                data.append({
                    'timestamp': timestamp,
                    'objid': obj['id'],
                    'x': round(obj['position'][0], 1),
                    'y': round(obj['position'][1], 1),
                    'z': round(obj['position'][2], 1)
                })
                
                # 다음 위치 계산
                if step < self.total_steps - 1:
                    # 주기적으로 방향 변경
                    obj['direction_change_counter'] += 1
                    if obj['direction_change_counter'] >= obj['direction_change_interval']:
                        target_velocity = self._random_velocity()
                        obj['velocity'] = self._smooth_direction_change(
                            obj['velocity'], target_velocity, smoothness=0.2
                        )
                        obj['direction_change_counter'] = 0
                        obj['direction_change_interval'] = random.randint(20, 100)
                        obj['speed'] = random.uniform(self.min_speed, self.max_speed)
                    
                    # 위치 업데이트
                    displacement = obj['velocity'] * obj['speed'] * self.interval_seconds
                    new_position = obj['position'] + displacement
                    
                    # 경계 체크 및 반사
                    collisions = self._check_boundary_collision(new_position)
                    if collisions:
                        obj['velocity'] = self._reflect_velocity(obj['velocity'], collisions)
                        # 경계 내부로 위치 조정
                        new_position = np.clip(new_position, 
                                               [self.x_range[0], self.y_range[0], self.z_range[0]],
                                               [self.x_range[1], self.y_range[1], self.z_range[1]])
                    
                    # 속도에 약간의 노이즈 추가 (더 자연스러운 움직임)
                    noise = np.random.normal(0, 0.02, 3)
                    obj['velocity'] = obj['velocity'] + noise
                    obj['velocity'] = obj['velocity'] / np.linalg.norm(obj['velocity'])
                    
                    obj['position'] = new_position
        
        # DataFrame 생성
        df = pd.DataFrame(data)
        return df


# 사용 예시
if __name__ == "__main__":
    """
    num_objects: 객체 수 설정
    duration_minutes: 데이터 길이 (timespan) 설정
    interval_seconds: 데이터 업데이트 간격 설정
    min_speed: 객체의 최소 속도 설정 
    max_speed: 객체의 최대 속도 설정
    (120 units/second 가 평균 사람 걷는 속도)

    """
    print("예시 2: 4개 객체, 1분, 0.2초 간격")
    generator = TrajectoryGenerator(
        num_objects=4, 
        duration_minutes=1,
        interval_seconds=0.2, 
        min_speed=150, 
        max_speed=200  
    )
    df2 = generator.generate()
    df2.to_csv('../data/living_trajectory_1min_0.2s.csv', index=False) # 데이터 저장
    print(f"생성된 데이터: {len(df2)} rows")
    print(df2.head(10))
    print("\n" + "="*50 + "\n")
    
    
    # # 통계 정보 출력
    # print("\n" + "="*50)
    # print("데이터 통계:")
    # print(f"객체별 데이터 포인트 수:")
    # print(df3.groupby('objid').size())