# simple_subscriber.py
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy

class SimpleSubscriber(Node):
    def __init__(self):
        super().__init__('pointcloud_custom_subscriber')

        # 발행자 QoS (Reliability: RELIABLE, Durability: VOLATILE, History: UNKNOWN) 기반
        # 옵션 A: History는 KEEP_LAST, Depth는 10
        qos_profile_subscriber = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            durability=QoSDurabilityPolicy.VOLATILE
        )

        # 옵션 B: 옵션 A가 작동하지 않으면 History를 KEEP_ALL로 시도
        # qos_profile_subscriber = QoSProfile(
        #     reliability=QoSReliabilityPolicy.RELIABLE,
        #     history=QoSHistoryPolicy.KEEP_ALL,
        #     depth=100,
        #     durability=QoSDurabilityPolicy.VOLATILE
        # )

        self.get_logger().info(f"Attempting to subscribe to /pointcloud with QoS: "
                               f"Reliability: {qos_profile_subscriber.reliability.name}, "
                               f"History: {qos_profile_subscriber.history.name}, "
                               f"Depth: {qos_profile_subscriber.depth}, "
                               f"Durability: {qos_profile_subscriber.durability.name}")

        self.subscription = self.create_subscription(
            PointCloud2,
            '/pointcloud',
            self.listener_callback,
            qos_profile=qos_profile_subscriber)

        self.get_logger().info('PointCloud subscriber started, waiting for messages...')
        self.received_count = 0

    def listener_callback(self, msg):
        self.received_count += 1
        self.get_logger().info(f'Received message {self.received_count}: PointCloud2 with frame_id: {msg.header.frame_id}, height: {msg.height}, width: {msg.width}, data_size: {len(msg.data)}')

def main(args=None):
    rclpy.init(args=args)
    node = SimpleSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()