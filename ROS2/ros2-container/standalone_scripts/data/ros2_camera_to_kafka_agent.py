#!/usr/bin/env python3
"""
ROS2 Camera to Kafka Agent

This script creates a ROS2 node that bridges camera data from ROS2 topics to Kafka.
It subscribes to ROS2 image topics (either compressed or raw images), processes the 
image data, and publishes it to a Kafka topic for downstream consumption.

Key Features:
- Supports both CompressedImage and raw Image message types from ROS2
- Converts raw images to JPEG format with configurable quality
- Rate-limited transmission to Kafka (configurable FPS)
- Registers with a visibility server for monitoring and management
- Periodic status updates to the visibility server
- Dynamic transmission control via ROS2 parameters

Environment Variables:
- ROS2_IMAGE_TOPIC: Source ROS2 topic (default: /camera/color/image_raw)
- ROS2_IMAGE_MESSAGE_TYPE: 'image' or 'compressedimage' (default: image)
- KAFKA_BROKER_ADDRESS: Kafka bootstrap servers (default: 10.79.1.1:9094)
- KAFKA_TOPIC_NAME: Target Kafka topic (default: isaacsim-husky-camera-01)
- KAFKA_SEND_INTERVAL_SEC: Transmission rate in seconds (default: 1.0)
- JPEG_QUALITY: JPEG compression quality 1-100 (default: 80)
- VISIBILITY_SERVER_URL: Server for registration and status updates

Usage:
    python3 ros2_camera_to_kafka_agent.py
    
    # Enable/disable transmission via ROS2 parameter:
    ros2 param set /ros2_camera_to_kafka_agent_node enable_kafka_transmission true

this comment written by Claude4, yeah InYong Song
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy
from sensor_msgs.msg import CompressedImage, Image  # Import both message types
from cv_bridge import CvBridge  # Convert Image messages to OpenCV format (compression needed for actual image data)
import cv2  # Required for JPEG compression

from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import base64
import os
import requests
import time
import uuid
from datetime import datetime
import threading

# --- Load Environment Variables ---
print("DEBUG: Python script started. Loading environment variables...")
VISIBILITY_SERVER_URL = os.environ.get('VISIBILITY_SERVER_URL', 'http://10.79.1.7:5111')
AGENT_NAME = os.environ.get('AGENT_NAME', f"ros2_kafka_cam_agent_{uuid.uuid4().hex[:6]}")
AGENT_API_PORT = int(os.environ.get('AGENT_PORT', 0))

CAMERA_ID_OVERRIDE = os.environ.get('CAMERA_ID_OVERRIDE')
CAMERA_NAME = os.environ.get('CAMERA_NAME', 'IsaacSim Husky Camera')
CAMERA_TYPE = os.environ.get('CAMERA_TYPE', 'rgb')
CAMERA_ENVIRONMENT = os.environ.get('CAMERA_ENVIRONMENT', 'virtual')
CAMERA_RESOLUTION = os.environ.get('CAMERA_RESOLUTION', '1280x720')
CAMERA_FPS_STR = os.environ.get('CAMERA_FPS', '30')
CAMERA_LOCATION = os.environ.get('CAMERA_LOCATION', 'Husky Robot Front')
CAMERA_HOST_PC_NAME = os.environ.get('HOSTNAME', AGENT_NAME)

ROS2_IMAGE_MESSAGE_TYPE = os.environ.get('ROS2_IMAGE_MESSAGE_TYPE', 'image').lower()
ROS2_IMAGE_TOPIC = os.environ.get('ROS2_IMAGE_TOPIC', '/camera/color/image_raw')
KAFKA_BROKER_ADDRESS = os.environ.get('KAFKA_BROKER_ADDRESS', '10.79.1.1:9094')
KAFKA_TOPIC_NAME = os.environ.get('KAFKA_TOPIC_NAME', 'isaacsim-husky-camera-01')
JPEG_QUALITY = int(os.environ.get('JPEG_QUALITY', 80))

STATUS_UPDATE_INTERVAL_SEC = int(os.environ.get('STATUS_UPDATE_INTERVAL_SEC', 10))
ENABLE_TRANSMISSION_PARAM_NAME = "enable_kafka_transmission"

# Kafka transmission interval (in seconds, e.g., 1.0 = 1 frame per second, 0.1 = 10 frames per second)
KAFKA_SEND_INTERVAL_SEC = float(os.environ.get('KAFKA_SEND_INTERVAL_SEC', 1.0))

print(f"DEBUG: VISIBILITY_SERVER_URL: {VISIBILITY_SERVER_URL}")
print(f"DEBUG: AGENT_NAME: {AGENT_NAME}")
print(f"DEBUG: ROS2_IMAGE_MESSAGE_TYPE: {ROS2_IMAGE_MESSAGE_TYPE}")
print(f"DEBUG: ROS2_IMAGE_TOPIC: {ROS2_IMAGE_TOPIC}")
print(f"DEBUG: KAFKA_BROKER_ADDRESS: {KAFKA_BROKER_ADDRESS}")
print(f"DEBUG: KAFKA_TOPIC_NAME: {KAFKA_TOPIC_NAME}")
print(f"DEBUG: JPEG_QUALITY: {JPEG_QUALITY}") 
print(f"DEBUG: KAFKA_SEND_INTERVAL_SEC: {KAFKA_SEND_INTERVAL_SEC}")

class ROS2CameraToKafkaAgent(Node):
    def __init__(self):
        print("DEBUG: ROS2CameraToKafkaAgent __init__ started")
        super().__init__('ros2_camera_to_kafka_agent_node')
        print(f"DEBUG: Node '{self.get_name()}' initialized.")
        self.agent_id_from_server = None
        self.camera_id = CAMERA_ID_OVERRIDE or str(uuid.uuid4())
        self.is_registered_with_server = False
        self.is_actively_transmitting = False

        self.log_prefix = f"Agent [{AGENT_NAME}({self.agent_id_from_server or 'Unreg'}) CamId({self.camera_id[:8]})]: "
        self.get_logger().info(f"{self.log_prefix}Initializing node...")
        print(f"DEBUG: {self.log_prefix}Logger initialized.")

        self.declare_parameter(ENABLE_TRANSMISSION_PARAM_NAME, True)
        self.get_logger().info(f"{self.log_prefix}Declared ROS2 parameter '{ENABLE_TRANSMISSION_PARAM_NAME}' with default False.")
        print(f"DEBUG: ROS2 parameter '{ENABLE_TRANSMISSION_PARAM_NAME}' declared.")

        self.producer = None
        self._initialize_kafka_producer()

        self.image_subscription = None
        self.cv_bridge = None

        # Variables for Kafka transmission rate control
        self.last_kafka_send_time = 0.0
        self.desired_kafka_send_interval = KAFKA_SEND_INTERVAL_SEC
        self.get_logger().info(f"{self.log_prefix}Kafka send interval set to {self.desired_kafka_send_interval} seconds.")

        if self.producer:
            print("DEBUG: Kafka producer initialized successfully. Setting up ROS2 subscription.")
            
            msg_type = None
            if ROS2_IMAGE_MESSAGE_TYPE == "compressedimage":
                msg_type = CompressedImage
                self.get_logger().info(f"{self.log_prefix}Using CompressedImage message type for subscription.")
            elif ROS2_IMAGE_MESSAGE_TYPE == "image":
                msg_type = Image
                self.get_logger().info(f"{self.log_prefix}Using Image message type for subscription.")
                if not self.cv_bridge:  # CvBridge initialization not needed when not using compression
                    try:
                        self.cv_bridge = CvBridge()
                        self.get_logger().info(f"{self.log_prefix}CvBridge initialized for Image type.")
                        print("DEBUG: CvBridge initialized.")
                    except Exception as e:
                        self.get_logger().error(f"{self.log_prefix}Failed to initialize CvBridge: {e}. Image messages may not be processed.", exc_info=True)
                        print(f"DEBUG: Failed to initialize CvBridge: {e}")
                        return 
            else:
                self.get_logger().error(f"{self.log_prefix}Unsupported ROS2_IMAGE_MESSAGE_TYPE: {ROS2_IMAGE_MESSAGE_TYPE}. Aborting subscription.")
                print(f"DEBUG: Unsupported ROS2_IMAGE_MESSAGE_TYPE: {ROS2_IMAGE_MESSAGE_TYPE}")
                return

            qos_profile_subscriber = QoSProfile(
                reliability=QoSReliabilityPolicy.RELIABLE,
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=5,
                durability=QoSDurabilityPolicy.VOLATILE 
            )
            try:
                self.image_subscription = self.create_subscription(
                    msg_type,
                    ROS2_IMAGE_TOPIC,
                    self.image_callback,
                    qos_profile=qos_profile_subscriber
                )
                self.get_logger().info(f"{self.log_prefix}Successfully subscribed to ROS2 topic '{ROS2_IMAGE_TOPIC}' with type '{msg_type.__name__}'. Waiting for messages...")
                print(f"DEBUG: Subscribed to ROS2 topic: {ROS2_IMAGE_TOPIC} with type {msg_type.__name__}")
            except Exception as e:
                self.get_logger().error(f"{self.log_prefix}Failed to create subscription for topic '{ROS2_IMAGE_TOPIC}': {e}", exc_info=True)
                print(f"DEBUG: Failed to create subscription: {e}")
                return
        else:
            self.get_logger().error(f"{self.log_prefix}Kafka producer failed to initialize. ROS2 subscription cannot be created.")
            print(f"DEBUG: Kafka producer FAILED. ROS2 subscription NOT created.")
            return

        self._register_agent_with_server()

        self.status_update_timer = None
        if self.is_registered_with_server:
            self.status_update_timer = self.create_timer(
                STATUS_UPDATE_INTERVAL_SEC,
                self.periodic_status_update
            )
            self.get_logger().info(f"{self.log_prefix}Periodic status update timer started.")
            print("DEBUG: Periodic status update timer started.")
        
        print("DEBUG: ROS2CameraToKafkaAgent __init__ finished successfully.")

    def _initialize_kafka_producer(self):
        print(f"DEBUG: Attempting to initialize KafkaProducer with brokers: {KAFKA_BROKER_ADDRESS}")
        try:
            producer_max_request_size = int(os.environ.get('KAFKA_PRODUCER_MAX_REQUEST_SIZE', 5 * 1024 * 1024))  # 5MB default
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER_ADDRESS.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                max_request_size=producer_max_request_size
            )
            self.get_logger().info(f"{self.log_prefix}KafkaProducer connected to {KAFKA_BROKER_ADDRESS} with max_request_size={producer_max_request_size}.")
            print(f"DEBUG: KafkaProducer connection SUCCESS to {KAFKA_BROKER_ADDRESS}")
        except KafkaError as e:
            self.get_logger().error(f"{self.log_prefix}KafkaProducer connection FAILED (KafkaError): {e}")
            print(f"DEBUG: KafkaProducer connection FAILED (KafkaError): {e}")
            self.producer = None
        except Exception as e:
            self.get_logger().error(f"{self.log_prefix}KafkaProducer initialization FAILED (Exception): {e}", exc_info=True)
            print(f"DEBUG: KafkaProducer initialization FAILED (Exception): {e}")
            self.producer = None

    def _get_current_transmission_state_from_param(self):
        try:
            param_value = self.get_parameter(ENABLE_TRANSMISSION_PARAM_NAME).get_parameter_value().bool_value
            self.get_logger().debug(f"{self.log_prefix}Read param '{ENABLE_TRANSMISSION_PARAM_NAME}' = {param_value}")
            return param_value
        except rclpy.exceptions.ParameterNotDeclaredException:
             self.get_logger().warn(f"{self.log_prefix}Parameter '{ENABLE_TRANSMISSION_PARAM_NAME}' not declared yet or node not fully initialized. Defaulting to False.")
             return False
        except Exception as e:
            self.get_logger().warn(f"{self.log_prefix}Could not read ROS2 parameter '{ENABLE_TRANSMISSION_PARAM_NAME}': {e}. Defaulting to False.")
            return False

    def image_callback(self, msg):
        self.get_logger().debug(f"{self.log_prefix}Image callback triggered for frame_id: {msg.header.frame_id}, type: {type(msg).__name__}")
        self.is_actively_transmitting = self._get_current_transmission_state_from_param()

        if not self.is_actively_transmitting:
            self.get_logger().debug(f"{self.log_prefix}Transmission is disabled by parameter. Skipping Kafka send.")
            return

        if not self.producer:
            self.get_logger().warn(f"{self.log_prefix}Kafka Producer not available. Cannot send message.")
            return

        # Kafka transmission rate control logic
        current_time = time.time()
        if (current_time - self.last_kafka_send_time) < self.desired_kafka_send_interval:
            self.get_logger().debug(f"{self.log_prefix}Skipping frame due to Kafka send interval. Last sent: {self.last_kafka_send_time:.2f}, Current: {current_time:.2f}, Interval: {self.desired_kafka_send_interval}")
            return
        
        # Start Kafka transmission when all conditions are met
        try:
            kafka_payload = {}
            image_data_b64 = None
            image_format = "unknown"

            if isinstance(msg, CompressedImage):
                self.get_logger().debug(f"{self.log_prefix}Processing CompressedImage (format: {msg.format}).")
                image_data_b64 = base64.b64encode(msg.data).decode('utf-8')
                image_format = msg.format
                
                kafka_payload = {
                    'timestamp_sec': msg.header.stamp.sec,
                    'timestamp_nanosec': msg.header.stamp.nanosec,
                    'frame_id': msg.header.frame_id,
                    'format': image_format,
                    'data_b64': image_data_b64
                }

            elif isinstance(msg, Image):
                self.get_logger().info(f"{self.log_prefix}Processing Image (encoding: {msg.encoding}). Attempting JPEG compression.")
                if not self.cv_bridge:
                    self.get_logger().error(f"{self.log_prefix}CvBridge not initialized. Cannot process raw Image message.")
                    return
                try:
                    # Convert ROS Image message to OpenCV image
                    # Isaac Sim's /camera/color/image_raw is usually 'rgb8' or 'bgr8'
                    cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
                    
                    # Compress OpenCV image to JPEG format
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
                    result, encoded_image_buffer = cv2.imencode('.jpg', cv_image, encode_param)
                    
                    if not result:
                        self.get_logger().error(f"{self.log_prefix}Failed to encode image to JPEG.")
                        return
                    
                    image_data_b64 = base64.b64encode(encoded_image_buffer).decode('utf-8')
                    image_format = "jpeg"  # Set format to jpeg since we compressed it
                    original_data_size = len(encoded_image_buffer)  # Size after compression
                    self.get_logger().debug(f"{self.log_prefix}Image successfully compressed to JPEG (quality: {JPEG_QUALITY}) and Base64 encoded.")

                    kafka_payload = {
                        'timestamp_sec': msg.header.stamp.sec,
                        'timestamp_nanosec': msg.header.stamp.nanosec,
                        'frame_id': msg.header.frame_id,
                        'format': image_format,  # "jpeg"
                        'original_encoding': msg.encoding,  # Add original encoding info
                        'height': msg.height,
                        'width': msg.width,
                        'data_b64': image_data_b64
                    }
                except Exception as e_cv:
                    self.get_logger().error(f"{self.log_prefix}Error during Image processing with CvBridge/OpenCV: {e_cv}", exc_info=True)
                    return
            else:
                self.get_logger().warn(f"{self.log_prefix}Received message of unknown or unhandled type: {type(msg)}. Cannot process.")
                return

            future = self.producer.send(KAFKA_TOPIC_NAME, value=kafka_payload)
            self.get_logger().info(f"{self.log_prefix}Image (frame: {msg.header.frame_id}, format: {image_format}, data_size: {len(msg.data)} bytes) SENT to Kafka topic '{KAFKA_TOPIC_NAME}'.")
            self.last_kafka_send_time = current_time

        except KafkaError as e:
            self.get_logger().error(f"{self.log_prefix}Failed to send image to Kafka: {e}")
        except Exception as e:
            self.get_logger().error(f"{self.log_prefix}Error processing or sending image: {e}", exc_info=True)

    def _construct_camera_payload(self):
        current_transmission_state = self._get_current_transmission_state_from_param()
        try:
            fps_int = int(CAMERA_FPS_STR)
        except ValueError:
            self.get_logger().warn(f"Invalid CAMERA_FPS: {CAMERA_FPS_STR}. Defaulting to 0.")
            fps_int = 0

        camera_data = {
            "camera_id": self.camera_id,
            "camera_name": CAMERA_NAME,
            "status": "streaming_to_kafka" if current_transmission_state else "idle_ready_to_stream",
            "type": CAMERA_TYPE,
            "environment": CAMERA_ENVIRONMENT,
            "stream_protocol": "KAFKA",
            "stream_details": {
                "kafka_topic": KAFKA_TOPIC_NAME,
                "kafka_bootstrap_servers": KAFKA_BROKER_ADDRESS,
                "ros2_source_topic": ROS2_IMAGE_TOPIC,
                "ros2_message_type": ROS2_IMAGE_MESSAGE_TYPE,
                "kafka_send_interval_sec": self.desired_kafka_send_interval 
            },
            "resolution": CAMERA_RESOLUTION,
            "fps": fps_int,
            "location": CAMERA_LOCATION,
            "host_pc_name": CAMERA_HOST_PC_NAME,
            "frame_transmission_enabled": current_transmission_state,
            "last_update": datetime.utcnow().isoformat()
        }
        return camera_data

    def _register_agent_with_server(self):
        if not VISIBILITY_SERVER_URL or VISIBILITY_SERVER_URL == 'http://10.79.1.7:5111':
             self.get_logger().warning(f"{self.log_prefix}VISIBILITY_SERVER_URL is default or potentially incorrect ('{VISIBILITY_SERVER_URL}').")

        payload = {
            "agent_name": AGENT_NAME,
            "agent_port": AGENT_API_PORT,
            "agent_type": "ROS2_KAFKA",
            "cameras": [self._construct_camera_payload()]
        }
        self.get_logger().info(f"{self.log_prefix}Attempting registration. Payload: {json.dumps(payload, indent=1)}")
        try:
            response = requests.post(f"{VISIBILITY_SERVER_URL}/agent_register", json=payload, timeout=10)
            if response.status_code == 201:
                data = response.json()
                self.agent_id_from_server = data.get("agent_id")
                self.is_registered_with_server = True
                self.log_prefix = f"Agent [{AGENT_NAME}({self.agent_id_from_server[:8]}) CamId({self.camera_id[:8]})]: "
                self.get_logger().info(f"{self.log_prefix}Successfully registered. Assigned Agent ID: {self.agent_id_from_server}")
            else:
                self.get_logger().error(f"{self.log_prefix}Failed to register. Status: {response.status_code}, Body: {response.text}")
        except requests.exceptions.RequestException as e:
            self.get_logger().error(f"{self.log_prefix}Error during registration request: {e}")
        except Exception as e:
            self.get_logger().error(f"{self.log_prefix}Unexpected error during registration: {e}", exc_info=True)

    def periodic_status_update(self):
        if not self.is_registered_with_server or not self.agent_id_from_server:
            return
        self.is_actively_transmitting = self._get_current_transmission_state_from_param()
        payload = {
            "agent_id": self.agent_id_from_server,
            "cameras": [self._construct_camera_payload()]
        }
        self.get_logger().debug(f"{self.log_prefix}Sending periodic status update.")
        try:
            response = requests.post(f"{VISIBILITY_SERVER_URL}/agent_update_status", json=payload, timeout=5)
            if response.status_code == 200:
                self.get_logger().info(f"{self.log_prefix}Status successfully updated.")
            elif response.status_code == 404:
                 self.get_logger().warning(f"{self.log_prefix}Agent ID not found on server (404). Re-registering.")
                 self.is_registered_with_server = False
                 self._register_agent_with_server()
            else:
                self.get_logger().error(f"{self.log_prefix}Failed to update status. Status: {response.status_code}, Body: {response.text}")
        except requests.exceptions.RequestException as e:
            self.get_logger().error(f"{self.log_prefix}Error during status update request: {e}")
        except Exception as e:
            self.get_logger().error(f"{self.log_prefix}Unexpected error during status update: {e}", exc_info=True)

    def destroy_node(self):
        print("DEBUG: ROS2CameraToKafkaAgent destroy_node called")
        self.get_logger().info(f"{self.log_prefix}Shutting down node...")
        if self.status_update_timer:
            self.status_update_timer.cancel()
            self.get_logger().info(f"{self.log_prefix}Status update timer cancelled.")
        if self.producer:
            self.get_logger().info(f"{self.log_prefix}Flushing and closing Kafka producer...")
            try:
                self.producer.flush(timeout=3.0)
            except Exception as e:
                self.get_logger().error(f"{self.log_prefix}Error flushing Kafka producer: {e}")
            finally:
                self.producer.close(timeout=3.0)
            self.get_logger().info(f"{self.log_prefix}Kafka producer closed.")
        super().destroy_node()
        self.get_logger().info(f"{self.log_prefix}Node base class destroyed.")
        print("DEBUG: Node destroyed.")

def main(args=None):
    print("DEBUG: ros2_camera_to_kafka_agent.py - main() started")
    rclpy.init(args=args)
    print("DEBUG: rclpy.init() called")
    node = None
    try:
        print("DEBUG: Attempting to create ROS2CameraToKafkaAgent node object.")
        node = ROS2CameraToKafkaAgent()
        print("DEBUG: ROS2CameraToKafkaAgent object created.")
        if node.producer and node.image_subscription:
            print("DEBUG: Kafka producer and ROS2 subscription initialized successfully. Spinning node...")
            rclpy.spin(node)
            print("DEBUG: rclpy.spin() finished.")
        else:
            print("DEBUG: Kafka producer or ROS2 subscription FAILED to initialize. Node will not spin. Exiting.")
            if node:
                node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
            return
    except KeyboardInterrupt:
        print("DEBUG: Keyboard interrupt received in main. Shutting down.")
        if node:
            node.get_logger().info("Keyboard interrupt. Shutting down node.")
    except Exception as e:
        print(f"DEBUG: Unhandled exception in main: {e}")
        if node and hasattr(node, 'get_logger') and node.get_logger():
            node.get_logger().fatal(f"Unhandled exception in main: {e}", exc_info=True)
        else:
            import traceback
            traceback.print_exc()
    finally:
        print("DEBUG: main() - finally block executing.")
        if node:
            node.destroy_node()
        if rclpy.ok():
            print("DEBUG: Shutting down rclpy.")
            rclpy.shutdown()
        print("DEBUG: ros2_camera_to_kafka_agent.py - main() finished.")

if __name__ == '__main__':
    print("DEBUG: Script execution started (__name__ == '__main__')")
    main()