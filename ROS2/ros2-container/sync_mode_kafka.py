#!/usr/bin/env python3
"""
    A ROS 2 node that acts as a bridge to  velocity commands from a Kafka
    topic to a ROS 2 topic.

    This node subscribes to a specified Kafka topic, consumes JSON messages
    representing velocity commands, and publishes them as geometry_msgs/msg/Twist
    messages to a designated ROS 2 topic. 
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from geometry_msgs.msg import Twist
import os
import uuid
import json
import threading
import time

# --- Import Kafka-Python Library ---
# pip install kafka-python
try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError
except ImportError:
    print("ERROR: kafka-python library not found.")
    print("Please install it using: pip install kafka-python")
    exit(1)


# --- Load Environment Variables ---
KAFKA_BROKER_ADDRESS = os.environ.get('KAFKA_BROKER_ADDRESS', '10.79.1.1:9094')
KAFKA_CONSUMER_TOPIC = os.environ.get('KAFKA_CONSUMER_TOPIC', 'inyong-joystick')
# Use unique group ID to prevent multiple consumers from receiving same message
KAFKA_GROUP_ID = os.environ.get('KAFKA_GROUP_ID', f"ros2_consumer_{uuid.uuid4().hex[:6]}")
OUTPUT_CMD_VEL_TOPIC = os.environ.get('OUTPUT_CMD_VEL_TOPIC', '/cmd_vel')

print("--- Kafka to ROS2 Forwarder Configuration ---")
print(f"KAFKA_BROKER_ADDRESS: {KAFKA_BROKER_ADDRESS}")
print(f"KAFKA_CONSUMER_TOPIC: {KAFKA_CONSUMER_TOPIC}")
print(f"KAFKA_GROUP_ID: {KAFKA_GROUP_ID}")
print(f"OUTPUT_CMD_VEL_TOPIC: {OUTPUT_CMD_VEL_TOPIC}")
print("---------------------------------------------")


class KafkaToROS2CmdVel(Node):
    """
    Node that receives messages from Kafka and publishes them as ROS2 Twist messages.
    """
    def __init__(self):
        node_name = f"kafka_to_ros2_cmdvel_{uuid.uuid4().hex[:6]}"
        super().__init__(node_name)
        self.get_logger().info(f"Node '{node_name}' initializing...")

        # ROS 2 Publisher Configuration
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.publisher = self.create_publisher(Twist, OUTPUT_CMD_VEL_TOPIC, qos_profile)
        self.get_logger().info(f"ROS 2 Publisher created for topic '{OUTPUT_CMD_VEL_TOPIC}'")
        print(f"DEBUG: Publisher created for topic: {OUTPUT_CMD_VEL_TOPIC}")

        # Kafka Consumer Configuration and Thread Start
        self.consumer = None
        self.is_running = True
        self.kafka_thread = threading.Thread(target=self._kafka_consumer_thread)
        self.kafka_thread.daemon = True  # Auto-terminate when main thread exits
        self.kafka_thread.start()

        self.get_logger().info("Initialization complete. Kafka consumer thread started.")

    def _kafka_consumer_thread(self):
        """
        Background thread for Kafka consumer to avoid blocking ROS2 main thread.
        """
        self.get_logger().info(f"Kafka consumer thread started. Attempting to connect...")
        print("DEBUG: Kafka consumer thread started.")
        
        try:
            self.consumer = KafkaConsumer(
                KAFKA_CONSUMER_TOPIC,
                bootstrap_servers=KAFKA_BROKER_ADDRESS.split(','),
                group_id=KAFKA_GROUP_ID,
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                auto_offset_reset='latest',  # Start from latest messages
                consumer_timeout_ms=1000  # Add timeout to allow thread termination
            )
            self.get_logger().info(f"Kafka consumer connected to topic '{KAFKA_CONSUMER_TOPIC}'")
            print(f"DEBUG: Kafka consumer connected successfully.")
            
        except KafkaError as e:
            self.get_logger().fatal(f"Kafka connection failed: {e}")
            print(f"DEBUG: Kafka connection failed: {e}")
            self.is_running = False
            return
        except Exception as e:
            self.get_logger().fatal(f"An unexpected error occurred during Kafka consumer initialization: {e}", exc_info=True)
            print(f"DEBUG: Unexpected error in Kafka initialization: {e}")
            self.is_running = False
            return

        # Main consumer loop
        while self.is_running:
            try:
                message_pack = self.consumer.poll(timeout_ms=1000)
                if message_pack:
                    for topic_partition, messages in message_pack.items():
                        for message in messages:
                            if not self.is_running:
                                break
                            
                            self.get_logger().debug(f"Received message from Kafka: {message.value}")
                            print(f"DEBUG: Processing Kafka message: {message.value}")
                            self.process_kafka_message(message.value)
                            
            except Exception as e:
                if self.is_running:  # Only log error if not shutting down
                    self.get_logger().error(f"Error in Kafka consumer loop: {e}. Reconnecting in 5 seconds...")
                    print(f"DEBUG: Error in consumer loop: {e}")
                    time.sleep(5)
        
        self.get_logger().info("Kafka consumer thread shutting down.")
        print("DEBUG: Kafka consumer thread shutting down.")
        if self.consumer:
            self.consumer.close()

    def process_kafka_message(self, data):
        """
        Process received Kafka message and publish as ROS2 Twist message.
        """
        try:
            # Extract linear and angular values from received JSON data
            linear_x = float(data.get('linear', {}).get('x', 0.0))
            linear_y = float(data.get('linear', {}).get('y', 0.0))
            linear_z = float(data.get('linear', {}).get('z', 0.0))
            angular_x = float(data.get('angular', {}).get('x', 0.0))
            angular_y = float(data.get('angular', {}).get('y', 0.0))
            angular_z = float(data.get('angular', {}).get('z', 0.0))

            # Create ROS 2 Twist message
            twist_msg = Twist()
            twist_msg.linear.x = linear_x
            twist_msg.linear.y = linear_y
            twist_msg.linear.z = linear_z
            twist_msg.angular.x = angular_x
            twist_msg.angular.y = angular_y
            twist_msg.angular.z = angular_z

            # Publish to ROS 2 topic
            self.publisher.publish(twist_msg)
            self.get_logger().info(f"Published to '{OUTPUT_CMD_VEL_TOPIC}': linear=[{linear_x:.3f}, {linear_y:.3f}, {linear_z:.3f}], angular=[{angular_x:.3f}, {angular_y:.3f}, {angular_z:.3f}]")

        except (TypeError, ValueError, KeyError) as e:
            self.get_logger().error(f"Failed to parse Kafka message or create Twist message. Data: {data}, Error: {e}")
            print(f"DEBUG: Message parsing error: {e}")
        except Exception as e:
            self.get_logger().error(f"An unexpected error occurred while processing message: {e}", exc_info=True)
            print(f"DEBUG: Unexpected error in message processing: {e}")
            
    def destroy_node(self):
        """
        Clean shutdown of the node and background thread.
        """
        self.get_logger().info("Shutting down node...")
        print("DEBUG: Node shutdown initiated.")
        
        self.is_running = False  # Signal background thread to terminate
        
        if self.kafka_thread and self.kafka_thread.is_alive():
            self.get_logger().info("Waiting for Kafka thread to terminate...")
            print("DEBUG: Waiting for Kafka thread to join...")
            self.kafka_thread.join(timeout=5.0)  # Wait up to 5 seconds for thread termination
            
        super().destroy_node()
        print("DEBUG: Node destroyed successfully.")


def main(args=None):
    print("DEBUG: kafka_to_ros2_cmdvel.py - main() started")
    rclpy.init(args=args)
    print("DEBUG: rclpy.init() called")
    
    node = None
    try:
        node = KafkaToROS2CmdVel()
        print("DEBUG: KafkaToROS2CmdVel object created.")
        
        rclpy.spin(node)
        print("DEBUG: rclpy.spin() finished.")
        
    except KeyboardInterrupt:
        print("DEBUG: Keyboard interrupt received. Shutting down.")
    except Exception as e:
        print(f"DEBUG: Unhandled exception in main: {e}")
        if node:
            node.get_logger().fatal(f"Unhandled exception: {e}", exc_info=True)
    finally:
        print("DEBUG: main() - finally block executing.")
        if node:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        print("DEBUG: kafka_to_ros2_cmdvel.py - main() finished.")


if __name__ == '__main__':
    main()