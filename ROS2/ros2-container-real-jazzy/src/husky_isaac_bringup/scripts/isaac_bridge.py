#!/usr/bin/env python3
# odom_to_tf.py
"""
Improved TF Bridge for Isaac Sim to Nav2
Converts world-based TF structure to Nav2 compatible map->odom->base_link structure.

----------------------------------------------------------------------------------------------------
[EN] As of 250808, this script implements a critical workaround for a timestamp synchronization
issue with the Isaac Sim Lidar.
- Problem: The Isaac Sim Lidar publisher (`ROS2RtxLidarHelper`) does not correctly use
  simulation time, instead publishing LaserScan messages with system (wall-clock) time. This
  causes a mismatch with all other ROS data (TF, Odometry) that use simulation time,
  leading to "TF lookup" errors in nodes like SLAM Toolbox and Nav2.
- Solution: This bridge node subscribes to the original `/scan` topic from Isaac Sim. It then
  re-stamps each message using the timestamp from the most recently received `/odom` message,
  which is known to be reliable. The corrected message is then re-published on the
  `/scan_stamped` topic, ensuring perfect synchronization for all downstream nodes.

[KR] 250808 기준, 이 스크립트는 Isaac Sim Lidar의 타임스탬프 동기화 문제에 대한
핵심적인 해결 방법을 구현합니다.
- 문제점: Isaac Sim의 Lidar 퍼블리셔(`ROS2RtxLidarHelper`)는 Isaac-sim 시뮬레이션 시간을
  올바르게 사용하지 않고, 메시지를 발행하여 다른 모든 ROS 데이터(TF, Odometry)와의 시간 불일치를
  유발하여, SLAM Toolbox나 Nav2 같은 노드에서 "TF 조회" 오류를 발생시켜 정상적인 동작이 안됨

- 해결책: 따라서 브리지 노드는 Isaac Sim의 원본 `/scan` 토픽을 구독하면서 그 후, 신뢰할 수
  있는 가장 최신의 `/odom` 메시지로부터 타임스탬프를 가져와 각 스캔 메시지의
  타임스탬프를 교체함. 이렇게 수정된 메시지는 `/scan_stamped` 토픽으로 다시
  발행되어, 정상적으로 모든 노드들이 Simulation time 기반 동기화가 이루어지도록 함
----------------------------------------------------------------------------------------------------

by InYong
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster, Buffer, TransformListener
from nav_msgs.msg import Odometry
# from rosgraph_msgs.msg import Clock # 더 이상 필요하지 않음
from sensor_msgs.msg import LaserScan
from tf2_ros import TransformException
import numpy as np

class ImprovedTfBridge(Node):
    def __init__(self):
        super().__init__('improved_tf_bridge')
        
        # Parameters
        self.declare_parameter('robot_frame', 'Ni_KI_Husky')
        self.declare_parameter('publish_rate', 100.0)
        
        self.use_sim_time = self.get_parameter('use_sim_time').value
        self.robot_frame = self.get_parameter('robot_frame').value
        self.publish_rate = self.get_parameter('publish_rate').value
        
        # TF
        self.br = TransformBroadcaster(self)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        

        # 구독: odom과 원본 /scan 토픽
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_cb, 10)
        
        # 발행: 타임스탬프를 보정한 /scan_stamped 토픽
        self.scan_stamped_pub = self.create_publisher(LaserScan, '/scan_stamped', 10)

        
        self.get_logger().info('Improved TF Bridge started with Odometry-based time synchronization')

        # 메인 타이머 - TF 발행
        self.timer = self.create_timer(1.0/self.publish_rate, self.publish_transforms)
        
        # 상태 변수
        self.latest_odom = None
        
        # 초기 map->odom 변환
        self.map_to_odom_offset = TransformStamped()
        self.map_to_odom_offset.header.frame_id = 'map'
        self.map_to_odom_offset.child_frame_id = 'odom'
        self.map_to_odom_offset.transform.rotation.w = 1.0
        
        self.get_logger().info(f'Monitoring robot frame: {self.robot_frame}')
        
    def odom_cb(self, msg):
        """Odometry 메시지를 저장하고, odom->base_link 변환을 발행합니다."""

        self.latest_odom = msg
        
        t = TransformStamped()
        t.header = msg.header  # odom 메시지의 타임스탬프를 그대로 사용
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = msg.pose.pose.position.x
        t.transform.translation.y = msg.pose.pose.position.y
        t.transform.translation.z = msg.pose.pose.position.z
        t.transform.rotation = msg.pose.pose.orientation
        self.br.sendTransform(t)

    def scan_cb(self, msg):
        """/scan 메시지를 받아 Odometry 시간으로 재발행합니다."""
        if self.latest_odom is None:
            # 아직 odom 메시지를 받지 못했다면 아무것도 하지 않음
            self.get_logger().warn("No odometry received yet, dropping scan.", throttle_duration_sec=2)
            return
        # 받은 메시지의 타임스탬프를 가장 최근 odom의 타임스탬프로 교체
        msg.header.stamp = self.latest_odom.header.stamp
        self.scan_stamped_pub.publish(msg)

    def publish_transforms(self):
        """
        [EN] Publishes essential TF transforms, customized for our specific USD structure.
        Note: The hard-coded transform values (e.g., sensor offsets) within this function
        are specific to our current robot model. These may need to be adjusted for
        different environments or robot configurations.

        [KR] 필수 TF 변환을 발행하며, 현재 우리 환경의 Husky USD 구조에 맞게 커스터마이즈되었습니다.
        주의: 이 함수 내의 하드코딩된 변환 값들(예: 센서 오프셋)은 현재 로봇 모델에
        특화되어 있습니다. 다른 환경이나 로봇 USD 로봇 모델 사용할때는 해당 값들 수정이 필요합니다.
        """
        if self.latest_odom is None:
            return  # odom 정보 없으면 발행 안함
        
        stamp = self.latest_odom.header.stamp # 모든 TF 발행의 기준 시간은 odom 시간
        
        # 1. map -> odom
        self.map_to_odom_offset.header.stamp = stamp
        self.br.sendTransform(self.map_to_odom_offset)
        
        # 2. base_link -> 센서 링크들
        # 단순화를 위해 이 부분은 하드코딩된 값으로 유지합니다.
        # base_link -> lidar_link
        t_lidar = TransformStamped()
        t_lidar.header.stamp = stamp
        t_lidar.header.frame_id = 'base_link'
        t_lidar.child_frame_id = 'lidar_link'
        t_lidar.transform.translation.z = 0.275
        t_lidar.transform.rotation.w = 1.0
        self.br.sendTransform(t_lidar)
        
        # base_link -> imu_link
        t_imu = TransformStamped()
        t_imu.header.stamp = stamp
        t_imu.header.frame_id = 'base_link'
        t_imu.child_frame_id = 'imu_link'
        t_imu.transform.rotation.w = 1.0
        self.br.sendTransform(t_imu)
        
        # ... (다른 정적 TF 발행 로직은 그대로 유지) ...
        # base_link -> front_bumper_link
        t_bumper = TransformStamped()
        t_bumper.header.stamp = stamp
        t_bumper.header.frame_id = 'base_link'
        t_bumper.child_frame_id = 'front_bumper_link'
        t_bumper.transform.translation.x = 0.44
        t_bumper.transform.translation.y = 0.0
        t_bumper.transform.translation.z = 0.083
        t_bumper.transform.rotation.w = 1.0
        self.br.sendTransform(t_bumper)

        # base_link -> base_footprint
        t_footprint = TransformStamped()
        t_footprint.header.stamp = stamp
        t_footprint.header.frame_id = 'base_link'
        t_footprint.child_frame_id = 'base_footprint'
        t_footprint.transform.translation.z = -0.121
        t_footprint.transform.rotation.w = 1.0
        self.br.sendTransform(t_footprint)

    # get_transform_from_world 와 update_map_to_odom 함수는 기존과 동일하게 유지
    def get_transform_from_world(self, target_frame, time_stamp):
        try:
            trans = self.tf_buffer.lookup_transform('world', target_frame, rclpy.time.Time(), timeout=rclpy.duration.Duration(seconds=0.1))
            return trans
        except TransformException:
            return None

    def update_map_to_odom(self, offset_x=0.0, offset_y=0.0, offset_yaw=0.0):
        self.map_to_odom_offset.transform.translation.x = offset_x
        self.map_to_odom_offset.transform.translation.y = offset_y
        cy = np.cos(offset_yaw * 0.5)
        sy = np.sin(offset_yaw * 0.5)
        self.map_to_odom_offset.transform.rotation.z = sy
        self.map_to_odom_offset.transform.rotation.w = cy
        self.get_logger().info(f'Updated map->odom offset: x={offset_x}, y={offset_y}, yaw={offset_yaw}')

def main():
    rclpy.init()
    import time
    print("Waiting for Isaac Sim TFs to stabilize...")
    time.sleep(2.0)
    
    node = ImprovedTfBridge()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down Improved TF Bridge...')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()