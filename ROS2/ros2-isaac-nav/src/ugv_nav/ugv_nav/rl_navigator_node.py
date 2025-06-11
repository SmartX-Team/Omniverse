import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, Vector3
import numpy as np
import math
import os # 환경변수 사용을 위해 추가

def get_quaternion_to_euler(q):
    """쿼터니언을 오일러 각도로 변환합니다."""
    siny_cosp = 2 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return yaw

class RlNavigatorNode(Node):
    def __init__(self):
        super().__init__('rl_navigator_node')
        
        # --- 환경변수에서 토픽 이름 읽어오기 ---
        cmd_vel_topic = os.getenv('CMD_VEL_TOPIC', '/cmd_vel')
        scan_topic = os.getenv('SCAN_TOPIC', '/scan')
        odom_topic = os.getenv('ODOM_TOPIC', '/odom')
        
        self.get_logger().info(f"CMD_VEL_TOPIC: {cmd_vel_topic}")
        self.get_logger().info(f"SCAN_TOPIC: {scan_topic}")
        self.get_logger().info(f"ODOM_TOPIC: {odom_topic}")

        # ROS 2 퍼블리셔와 서브스크라이버 설정
        self.publisher_ = self.create_publisher(Twist, cmd_vel_topic, 10)
        self.scan_subscription = self.create_subscription(
            LaserScan,
            scan_topic,
            self.scan_callback,
            10)
        self.odom_subscription = self.create_subscription(
            Odometry,
            odom_topic,
            self.odom_callback,
            10)
        
        # 행동을 결정하고 실행하는 주기적인 타이머 (10Hz)
        self.timer = self.create_timer(0.1, self.decision_loop)

        # --- 목표 지점 설정 ---
        self.goal_position = np.array([5.0, 0.0]) # 목표: (x=5, y=0)
        
        # --- Q-Learning 파라미터 ---
        self.q_table = {}
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.epsilon = 0.9
        self.epsilon_decay = 0.995
        self.min_epsilon = 0.05

        # --- 행동 정의 ---
        self.actions = {
            0: ('직진', Twist(linear=Vector3(x=0.5, y=0.0, z=0.0), angular=Vector3(x=0.0, y=0.0, z=0.0))),
            1: ('좌회전', Twist(linear=Vector3(x=0.25, y=0.0, z=0.0), angular=Vector3(x=0.0, y=0.0, z=0.3))),
            2: ('우회전', Twist(linear=Vector3(x=0.25, y=0.0, z=0.0), angular=Vector3(x=0.0, y=0.0, z=-0.3))),
        }
        
        # 상태 저장을 위한 변수
        self.current_scan_state = None
        self.current_odom_state = None
        self.last_distance_to_goal = None
        self.last_state = None
        self.last_action_index = None
        
        self.get_logger().info("강화학습 네비게이터 노드가 시작되었습니다.")

    def scan_callback(self, msg):
        """Lidar 데이터를 이산적인 상태로 변환합니다."""
        num_sections = 3
        section_len = len(msg.ranges) // num_sections
        sections = {
            'right': min(msg.ranges[0:section_len]),
            'front': min(msg.ranges[section_len:2*section_len]),
            'left': min(msg.ranges[2*section_len:]),
        }
        state = []
        for direction in ['right', 'front', 'left']:
            distance = sections[direction]
            if distance < 0.5: state.append(0)
            elif distance < 1.0: state.append(1)
            else: state.append(2)
        self.current_scan_state = tuple(state)

    def odom_callback(self, msg):
        """Odom 데이터를 이산적인 상태로 변환하고 목표 도달 여부를 확인합니다."""
        current_pos = msg.pose.pose.position
        robot_position = np.array([current_pos.x, current_pos.y])
        
        distance_to_goal = np.linalg.norm(robot_position - self.goal_position)
        
        # 목표 도달 시 성공 메시지 출력 후 노드 종료 (또는 다음 목표 설정)
        if distance_to_goal < 0.3:
            self.get_logger().info("***** 목표 지점 도달! *****")
            self.publisher_.publish(Twist()) # 정지
            self.destroy_node()
            rclpy.shutdown()
            return
        
        robot_yaw = get_quaternion_to_euler(msg.pose.pose.orientation)
        angle_to_goal = math.atan2(self.goal_position[1] - robot_position[1], self.goal_position[0] - robot_position[0])
        angle_diff = angle_to_goal - robot_yaw
        # 각도 차이를 -pi ~ pi 범위로 정규화
        angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi

        # 거리와 각도를 이산적인 상태로 변환
        dist_state = 0 if distance_to_goal < 1.5 else (1 if distance_to_goal < 3.0 else 2)
        angle_state = 0 if angle_diff < -math.pi/4 else (1 if angle_diff < math.pi/4 else 2) # 왼쪽, 정면, 오른쪽
        
        self.current_odom_state = (dist_state, angle_state)
        self.last_distance_to_goal = distance_to_goal
        
    def calculate_reward(self, scan_state, odom_state, last_dist):
        """상태를 기반으로 보상을 계산합니다."""
        if scan_state is None or odom_state is None: return 0
        
        # 1. 충돌 페널티
        if scan_state[1] == 0: return -100
        
        # 2. 목표 도달 보상 (odom_callback에서 처리)
        
        # 3. 목표에 가까워지는 것에 대한 보상
        reward = 0
        current_dist = self.last_distance_to_goal
        if last_dist is not None and current_dist < last_dist:
            reward += 10 # 목표에 가까워짐
        else:
            reward -= 5 # 목표에서 멀어지거나 정체
            
        # 4. 목표 방향 정렬 보상
        if odom_state[1] == 1: # 로봇이 목표를 정면으로 바라볼 때
            reward += 5
            
        return reward

    def decision_loop(self):
        if self.current_scan_state is None or self.current_odom_state is None:
            self.get_logger().warn("Scan 또는 Odom 데이터 수신 대기 중...", throttle_duration_sec=5)
            return

        # Lidar 상태와 Odom 상태를 합쳐 최종 상태 정의
        current_state = self.current_scan_state + self.current_odom_state

        # Epsilon-Greedy 행동 선택
        if current_state not in self.q_table: self.q_table[current_state] = np.zeros(len(self.actions))
            
        if np.random.random() < self.epsilon:
            action_index = np.random.choice(list(self.actions.keys()))
        else:
            action_index = np.argmax(self.q_table[current_state])
        
        # Q-Table 업데이트
        if self.last_state is not None:
            reward = self.calculate_reward(self.current_scan_state, self.current_odom_state, self.last_distance_to_goal)
            next_max_q = np.max(self.q_table[current_state])
            old_q_value = self.q_table[self.last_state][self.last_action_index]
            new_q_value = old_q_value + self.learning_rate * (reward + self.discount_factor * next_max_q - old_q_value)
            self.q_table[self.last_state][self.last_action_index] = new_q_value
        
        # 행동 실행
        action_name, twist_msg = self.actions[action_index]
        self.publisher_.publish(twist_msg)
        
        # 다음 루프를 위한 상태 저장
        self.last_state = current_state
        self.last_action_index = action_index

        if self.epsilon > self.min_epsilon: self.epsilon *= self.epsilon_decay


def main(args=None):
    rclpy.init(args=args)
    node = RlNavigatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("학습이 중단되었습니다.")
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()

if __name__ == '__main__':
    main()