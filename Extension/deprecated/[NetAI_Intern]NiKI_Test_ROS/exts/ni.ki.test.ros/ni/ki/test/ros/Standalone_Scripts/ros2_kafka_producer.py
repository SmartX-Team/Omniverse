# United we stand, divided we fall - Aseop

# Simple project for converting the sensor data into streams for Kafka by listening to the ROS2 Topics

import rclpy
import json
from sensor_msgs.msg import PointCloud2
from kafka import KafkaProducer
import time
# from kafka import KafkaConsumer  # <- Would be needed if it actually was a bridge and not a one-way-gate

class lidar_ros2_kafka_bridge():

    def __init__(self, args=None) -> None:
        
        rclpy.init(args=args)

        self.node = rclpy.create_node('lidar_ros2_kafka_bridge_topic')

        self.node.create_subscription(PointCloud2, '/point_cloud_hydra', self.ros2_callback, 10)

        self.producer = KafkaProducer(
            bootstrap_servers=['10.80.0.3:9094'],  # Kafka 브로커 주소
            value_serializer=lambda v: json.dumps(v).encode('utf-8')  # JSON으로 직렬화 및 UTF-8 인코딩
        )

        # Counters
        self.group_count = 0
        self.id_count = 1
        self.start_time = time.time()

        # Amount of sepertations of the point cloud data
        self.sepertations = 4  # 1 =< int(sep) < math.inf

        rclpy.spin(self.node)
        self.node.destroy_node()
        rclpy.shutdown()

    async def ros2_callback(self, point_cloud):
        # TODO: Optimise it - most of the data never arrives at Kafka...
        # await self.producer.connect()
        self.group_count += 1

        length_of_point_cloud = len(list(point_cloud.data))
        point_cloud_as_list = list(point_cloud.data)
        step_intervall = length_of_point_cloud//self.sepertations
        split_list = []

        for i in range(self.sepertations-2):
            split_list.append(point_cloud_as_list[i*step_intervall: (i+1)*step_intervall])
        split_list.append(point_cloud_as_list[(i+1)*step_intervall:])
        

        x = 1
        for sl in split_list:
            self.producer.send('lidar-topic', {
                "Starting Time": self.start_time,
                "Num_of_sep": self.sepertations,
                "Unique ID": self.id_count,
                "Group ID": self.group_count,
                "height" : point_cloud.height,
                "width": point_cloud.width,
                "is_bigendian": point_cloud.is_bigendian,
                "point_step":point_cloud.point_step,
                "row_steps":point_cloud.row_step,
                "is_dense":point_cloud.is_dense,
                f"data {x}": sl
            })
            x += 1
            self.id_count+=1
            time.sleep(0.1)
        
        # Show that the program is running
        print(len(list(point_cloud.data)))
        time.sleep(0.1)

if __name__ == "__main__":
    lidar_ros2_kafka_bridge()
