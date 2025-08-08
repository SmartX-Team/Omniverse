#!/usr/bin/env python3
"""
자동으로 로봇의 현재 위치를 초기 위치로 설정
SLAM과 Nav2가 어떤 위치에서도 시작할 수 있도록 함
Fixed: use_sim_time parameter already declared issue
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
import time

class AutoInitPose(Node):
    def __init__(self):
        super().__init__('auto_init_pose')
        
        # use_sim_time은 이미 선언되어 있으므로 declare하지 않음
        # self.declare_parameter('use_sim_time', True) # REMOVED
        
        # Publishers
        self.init_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, 
            '/initialpose', 
            10)
        
        # Subscribers
        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10)
        
        self.first_odom_received = False
        self.init_sent = False
        
        self.get_logger().info('Auto Initial Pose setter started')
        
    def odom_callback(self, msg):
        """첫 odometry를 받으면 초기 위치 설정"""
        if not self.first_odom_received:
            self.first_odom_received = True
            time.sleep(2.0)  # Nav2가 시작되기를 기다림
            
            # 초기 위치 메시지 생성
            init_pose = PoseWithCovarianceStamped()
            init_pose.header.frame_id = 'map'
            init_pose.header.stamp = self.get_clock().now().to_msg()
            
            # 현재 odometry 위치를 초기 위치로 설정
            init_pose.pose.pose = msg.pose.pose
            
            # 공분산 설정 (작은 불확실성)
            init_pose.pose.covariance = [
                0.25, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.25, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.06853892326654787
            ]
            
            # 발행
            self.init_pose_pub.publish(init_pose)
            self.get_logger().info(f'Initial pose set at: x={msg.pose.pose.position.x:.2f}, y={msg.pose.pose.position.y:.2f}')
            
            # 한 번만 발행 후 종료
            time.sleep(1.0)
            self.destroy_node()
            rclpy.shutdown()

def main():
    rclpy.init()
    node = AutoInitPose()
    rclpy.spin(node)

if __name__ == '__main__':
    main()