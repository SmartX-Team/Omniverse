#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env

def run_sb3_check():
    """Stable-Baselines3와 Gymnasium이 정상 설치되었는지 확인합니다."""
    print("\n" + "="*50)
    print("      Running Stable-Baselines3 & Gymnasium Health Check...")
    print("="*50)
    try:
        # 1. 간단한 Gym 환경 생성
        env = gym.make("CartPole-v1")
        print("✅ Gymnasium environment created successfully.")

        # 2. 환경 호환성 체크
        check_env(env)
        print("✅ Gymnasium environment check passed.")

        # 3. PPO 모델 생성 (GPU가 사용 가능하다면 자동으로 사용)
        model = PPO("MlpPolicy", env, verbose=0)
        print("✅ Stable-Baselines3 PPO model created successfully.")
        
        # 4. 짧은 학습 실행
        print("Running a short training loop (100 steps)...")
        model.learn(total_timesteps=100)
        print("✅ Stable-Baselines3 training finished without errors.")
        print("\n🎉 RL Environment Health Check: PASSED\n")

    except Exception as e:
        print("\n❌ RL Environment Health Check: FAILED")
        print(f"Error: {e}")
    finally:
        print("="*50 + "\n")


class Ros2HealthCheckNode(Node):
    """ROS 2 통신이 정상 동작하는지 확인합니다."""
    def __init__(self):
        super().__init__('ros2_health_check_node')
        self.publisher_ = self.create_publisher(String, 'health_check_topic', 10)
        self.subscription = self.create_subscription(
            String, 'health_check_topic', self.listener_callback, 10)
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.counter = 0
        print("ROS 2 Health Check Node is running...")
        print("Publishing and Subscribing to '/health_check_topic'")

    def timer_callback(self):
        msg = String()
        msg.data = f'ROS 2 is alive! Ping: {self.counter}'
        self.publisher_.publish(msg)
        self.counter += 1

    def listener_callback(self, msg):
        self.get_logger().info(f'I heard: "{msg.data}"')


def main(args=None):
    # 먼저 Stable-Baselines3 환경 체크 실행
    run_sb3_check()

    # 다음으로 ROS 2 노드 실행
    rclpy.init(args=args)
    node = Ros2HealthCheckNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()