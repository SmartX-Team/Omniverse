# 파일명: pointcloud_to_kafka.py 
# 아이작심에서 생성되는 Lidar 데이터 카프카 기반으로 전송하는 코드
# 데이터 크기가 기본적으로 크기때문에, 필요할때만 활성화시켜서 실행하도록
# ROS2 통신 방법 참고용 코드로 남겨둠
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy

from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import base64
import os # 환경 변수 사용을 위해 추가

# Kafka 설정: 환경 변수에서 읽거나 기본값 사용
KAFKA_BROKER_ADDRESS = os.environ.get('KAFKA_BROKER', '10.79.1.1:9094')
KAFKA_TOPIC_NAME = os.environ.get('KAFKA_TOPIC', 'omni-lidar')

class PointCloudToKafkaNode(Node):
    def __init__(self):
        super().__init__('pointcloud_to_kafka_node')

        self.get_logger().info(f"Attempting to connect to Kafka broker: {KAFKA_BROKER_ADDRESS}, topic: {KAFKA_TOPIC_NAME}")

        try:
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER_ADDRESS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            self.get_logger().info(f"KafkaProducer_test_report_kafka.pdf 연결 성공.")
        except KafkaError as e:
            self.get_logger().error(f"KafkaProducer_test_report_kafka.pdf 연결 실패: {e}")
            self.producer = None
            rclpy.shutdown()
            return

        qos_profile_subscriber = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            durability=QoSDurabilityPolicy.VOLATILE
        )
        
        self.get_logger().info(f"Subscribing to /pointcloud with QoS: "
                               f"Reliability: {qos_profile_subscriber.reliability.name}, "
                               f"History: {qos_profile_subscriber.history.name}, "
                               f"Depth: {qos_profile_subscriber.depth}, "
                               f"Durability: {qos_profile_subscriber.durability.name}")

        self.subscription = self.create_subscription(
            PointCloud2,
            '/pointcloud',
            self.pointcloud_callback,
            qos_profile=qos_profile_subscriber
        )
        self.get_logger().info(f"'/pointcloud' 토픽 구독 시작. Kafka 토픽 '{KAFKA_TOPIC_NAME}'으로 메시지 전송 대기 중...")

    def pointcloud_to_dict(self, msg: PointCloud2) -> dict:
        fields_list = []
        for field in msg.fields:
            fields_list.append({
                'name': field.name,
                'offset': field.offset,
                'datatype': field.datatype,
                'count': field.count
            })
        return {
            'header': {
                'stamp': {
                    'sec': msg.header.stamp.sec,
                    'nanosec': msg.header.stamp.nanosec
                },
                'frame_id': msg.header.frame_id
            },
            'height': msg.height,
            'width': msg.width,
            'fields': fields_list,
            'is_bigendian': msg.is_bigendian,
            'point_step': msg.point_step,
            'row_step': msg.row_step,
            'data': base64.b64encode(msg.data).decode('utf-8'),
            'is_dense': msg.is_dense
        }

    def pointcloud_callback(self, msg: PointCloud2):
        if not self.producer:
            self.get_logger().warn("Kafka Producer가 초기화되지 않아 메시지를 전송할 수 없습니다.")
            return
        try:
            msg_dict = self.pointcloud_to_dict(msg)
            future = self.producer.send(KAFKA_TOPIC_NAME, value=msg_dict)
            self.get_logger().info(f"PointCloud 메시지 (프레임: {msg.header.frame_id}, 타임스탬프: {msg.header.stamp.sec}.{msg.header.stamp.nanosec:09d})를 Kafka 토픽 '{KAFKA_TOPIC_NAME}'으로 전송 요청함.")
        except KafkaError as e:
            self.get_logger().error(f"Kafka 메시지 전송 중 오류 발생: {e}")
        except Exception as e:
            self.get_logger().error(f"PointCloud 메시지 처리 또는 Kafka 전송 중 예외 발생: {e}")

    def destroy_node(self):
        if self.producer:
            self.get_logger().info("Kafka Producer_test_report_kafka.pdf 종료 중...")
            self.producer.flush()
            self.producer.close()
            self.get_logger().info("Kafka Producer_test_report_kafka.pdf 종료 완료.")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = PointCloudToKafkaNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("사용자 요청으로 노드 종료 중...")
    except Exception as e:
        node.get_logger().error(f"Spin 중 예외 발생: {e}")
    finally:
        if node and rclpy.ok():
             node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()