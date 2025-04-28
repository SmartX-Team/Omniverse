# United we stand, divided we fall - Aseop

# Simple project for reconstructing the sensor data from Kafka into ROS2 Topics

# TODO: This projects does not combine the data that was previously split
# Additonaly there are no ways to fix empty data spots
# Otherwise the program lacks a feature to playback recoded data, which would be tremoundsly helpful

import rclpy
import json
from sensor_msgs.msg import PointCloud2
from kafka import KafkaConsumer
import time
import threading
# from kafka import KafkaProducer  # <- Would be needed if it actually was a bridge and not a one-way-gate

class lidar_ros2_kafka_bridge():

    def __init__(self, args=None) -> None:
        
        rclpy.init(args=args)

        self.node = rclpy.create_node('lidar_ros2_kafka_bridge_topic')

        self.pub = self.node.create_publisher(PointCloud2, '/point_cloud_hydra', 10)

        self.consumer = KafkaConsumer('lidar-topic',
                                  bootstrap_servers='10.80.0.3:9094',
                                  value_deserializer=lambda m: json.loads(m.decode('ascii')),
                                  auto_offset_reset='earliest',
                                  consumer_timeout_ms=2000)

        self.reader()

        try:
            while True:
                pass
        except KeyboardInterrupt:
            pass
    
    def reader(self):
        def reader_callback_local():
            while True:
                for message in self.consumer:
                    self.kafka_callback(message.value)
        t1 = threading.Thread(target=reader_callback_local)
        t1.daemon = True
        t1.start()

    def kafka_callback(self, topic_data):
        msg = PointCloud2()
        msg.data = topic_data["data"]
        self.pub.publish(msg)

if __name__ == '__main__':
    lidar_ros2_kafka_bridge()
 