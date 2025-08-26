from aiokafka import AIOKafkaProducer
import json
import asyncio
from datetime import datetime
import base64
from typing import Optional, Tuple, Dict, Any

class KafkaHandler:
    """Handle Kafka connections and image streaming"""
    
    def __init__(self):
        """Initialize Kafka handler"""
        self.producer = None
        self.is_connected = False
        self.broker = None
    
    async def connect(self, broker: str) -> Tuple[bool, str]:
        """
        Connect to Kafka broker
        
        Args:
            broker: Kafka broker address (host:port)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            print(f"[KafkaHandler] Connecting to broker: {broker}")
            
            # value_serializer를 제거하여 중복 직렬화 방지
            # 대신 각 send 메서드에서 필요시 직접 직렬화
            self.producer = AIOKafkaProducer(
                bootstrap_servers=broker,
                # value_serializer 제거 - 수동으로 처리
                compression_type='gzip',  # 압축 사용
                max_request_size=10485760,  # 10MB max
                request_timeout_ms=30000,
                metadata_max_age_ms=300000,
            )
            
            await self.producer.start()
            self.is_connected = True
            self.broker = broker
            
            print(f"[KafkaHandler] Successfully connected to {broker}")
            return True, "Connected successfully"
            
        except Exception as e:
            error_msg = f"Connection failed: {str(e)}"
            print(f"[KafkaHandler] {error_msg}")
            self.is_connected = False
            return False, error_msg
    
    async def send_image(self, topic: str, camera_id: int, image_bytes: bytes) -> bool:
        """
        Send image data to Kafka topic (simple version without metadata)
        
        Args:
            topic: Kafka topic name
            camera_id: Camera identifier
            image_bytes: Image data as bytes (JPEG compressed)
            
        Returns:
            Success status
        """
        if not self.is_connected or not self.producer:
            print("[KafkaHandler] Not connected to Kafka broker")
            return False
        
        try:
            # Create message with basic metadata
            message = {
                "camera_id": camera_id,
                "timestamp": datetime.now().isoformat(),
                "timestamp_ms": int(datetime.now().timestamp() * 1000),
                "image_size": len(image_bytes),
                "image_format": "jpeg",
                "image": base64.b64encode(image_bytes).decode('utf-8')
            }
            
            # 수동으로 JSON 직렬화
            message_bytes = json.dumps(message).encode('utf-8')
            
            # Send to Kafka
            await self.producer.send_and_wait(
                topic,
                value=message_bytes,  # 이미 직렬화된 bytes 전송
                key=f"camera_{camera_id}".encode('utf-8')  # Partition key
            )
            
            print(f"[KafkaHandler] Sent image to topic '{topic}' - Camera {camera_id}, Size: {len(image_bytes)} bytes")
            return True
            
        except Exception as e:
            print(f"[KafkaHandler] Failed to send image: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def send_raw_image(self, topic: str, camera_id: int, image_bytes: bytes,
                           width: int, height: int, channels: int = 3) -> bool:
        """
        Send raw (uncompressed) image data to Kafka
        
        Args:
            topic: Kafka topic name
            camera_id: Camera identifier
            image_bytes: Raw image data
            width: Image width
            height: Image height
            channels: Number of color channels
            
        Returns:
            Success status
        """
        if not self.is_connected or not self.producer:
            print("[KafkaHandler] Not connected to Kafka broker")
            return False
        
        try:
            # Create message with raw image metadata
            message = {
                "camera_id": camera_id,
                "timestamp": datetime.now().isoformat(),
                "timestamp_ms": int(datetime.now().timestamp() * 1000),
                "image_size": len(image_bytes),
                "image_format": "raw",
                "width": width,
                "height": height,
                "channels": channels,
                "image": base64.b64encode(image_bytes).decode('utf-8')
            }
            
            # 수동으로 JSON 직렬화
            message_bytes = json.dumps(message).encode('utf-8')
            
            # Send to Kafka
            await self.producer.send_and_wait(
                topic,
                value=message_bytes,  # 이미 직렬화된 bytes 전송
                key=f"camera_{camera_id}".encode('utf-8')
            )
            
            print(f"[KafkaHandler] Sent raw image to topic '{topic}' - Camera {camera_id}, "
                  f"Size: {len(image_bytes)} bytes, Resolution: {width}x{height}")
            return True
            
        except Exception as e:
            print(f"[KafkaHandler] Failed to send raw image: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def send_image_with_metadata(self, topic: str, camera_id: int, 
                                    image_bytes: bytes, metadata: dict) -> bool:
        """
        Send image with full camera metadata for AI inference
        
        Args:
            topic: Kafka topic name
            camera_id: Camera identifier  
            image_bytes: JPEG compressed image
            metadata: Camera intrinsic/extrinsic parameters
        """
        if not self.is_connected or not self.producer:
            return False
        
        try:
            # Comprehensive message for MVS/depth estimation
            message = {
                # Frame identification
                "frame_id": f"frame_{int(datetime.now().timestamp() * 1000)}",
                "camera_id": camera_id,
                "camera_name": f"cam{camera_id}",
                "camera_path": metadata.get("camera_path", ""),
                "timestamp": datetime.now().isoformat(),
                "timestamp_ms": int(datetime.now().timestamp() * 1000),
                
                # Camera calibration
                "intrinsics": {
                    "K": metadata.get("K"),  # 3x3 matrix as list
                    "distortion": metadata.get("distortion", [0,0,0,0,0]),  # distortion coefficients
                    "image_size": metadata.get("image_size"),  # [width, height]
                    "focal_length": metadata.get("focal_length"),
                    "sensor_size": metadata.get("sensor_size")
                },
                
                # Camera pose
                "extrinsics": {
                    "R": metadata.get("R"),  # 3x3 rotation matrix
                    "t": metadata.get("t"),  # 3x1 translation vector
                    "T_world_cam": metadata.get("T_world_cam")  # Full 4x4 transform
                },
                
                # Image data
                "image": {
                    "format": "jpeg",
                    "quality": 85,
                    "size": len(image_bytes),
                    "width": metadata["image_size"][0],
                    "height": metadata["image_size"][1],
                    "data": base64.b64encode(image_bytes).decode('utf-8')
                }
            }
            
            # 수동으로 JSON 직렬화
            message_bytes = json.dumps(message).encode('utf-8')
            
            # Send with camera-specific partition key for ordering
            await self.producer.send_and_wait(
                topic,
                value=message_bytes,  # 이미 직렬화된 bytes 전송
                key=f"cam{camera_id}".encode('utf-8')
            )
            
            print(f"[KafkaHandler] Sent frame with metadata to '{topic}' - Camera {camera_id}")
            return True
            
        except Exception as e:
            print(f"[KafkaHandler] Failed to send with metadata: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def send_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        """
        Send generic message to Kafka (direct message passing)
        
        Args:
            topic: Kafka topic name
            message: Dictionary to send as JSON
            key: Optional partition key
            
        Returns:
            Success status
        """
        if not self.is_connected or not self.producer:
            print("[KafkaHandler] Not connected to Kafka broker")
            return False
        
        try:
            # Key encoding
            key_bytes = None
            if key:
                key_bytes = key.encode('utf-8') if isinstance(key, str) else key
            
            # 메시지 타입 확인 후 적절히 처리
            if isinstance(message, dict):
                # 딕셔너리인 경우 JSON 직렬화
                message_bytes = json.dumps(message).encode('utf-8')
            elif isinstance(message, bytes):
                # 이미 bytes인 경우 그대로 사용
                message_bytes = message
            elif isinstance(message, str):
                # 문자열인 경우 UTF-8 인코딩
                message_bytes = message.encode('utf-8')
            else:
                # 기타 타입은 JSON 직렬화 시도
                message_bytes = json.dumps(message).encode('utf-8')
            
            # Send message
            await self.producer.send_and_wait(
                topic,
                value=message_bytes,  # 직렬화된 bytes 전송
                key=key_bytes
            )
            
            return True
            
        except Exception as e:
            print(f"[KafkaHandler] Failed to send message: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def send_sync_frame_set(self, sync_topic: str, frame_set: list) -> bool:
        """
        Send synchronized multi-camera frame set for MVS processing
        
        Args:
            sync_topic: Topic for synchronized frames (e.g., "sync_frames")
            frame_set: List of camera frames with metadata
        """
        if not self.is_connected:
            return False
        
        try:
            sync_message = {
                "sync_id": f"sync_{int(datetime.now().timestamp() * 1000)}",
                "timestamp": datetime.now().isoformat(),
                "timestamp_ms": int(datetime.now().timestamp() * 1000),
                "frame_count": len(frame_set),
                "frames": frame_set
            }
            
            # 수동으로 JSON 직렬화
            message_bytes = json.dumps(sync_message).encode('utf-8')
            
            await self.producer.send_and_wait(
                sync_topic,
                value=message_bytes,  # 이미 직렬화된 bytes 전송
                key="sync_frames".encode('utf-8')
            )
            
            print(f"[KafkaHandler] Sent synchronized frame set with {len(frame_set)} cameras")
            return True
            
        except Exception as e:
            print(f"[KafkaHandler] Failed to send sync frame: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_connection(self) -> bool:
        """
        Test if connection is alive
        
        Returns:
            Connection status
        """
        if not self.is_connected or not self.producer:
            return False
        
        try:
            # Try to get metadata - AIOKafkaProducer에서 _metadata 접근 방식 수정
            # metadata 업데이트는 내부적으로 처리됨
            # 간단한 연결 상태 확인
            if self.producer._closed:
                self.is_connected = False
                return False
            return True
        except Exception as e:
            print(f"[KafkaHandler] Connection test failed: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Kafka broker"""
        if self.producer:
            try:
                await self.producer.stop()
                print(f"[KafkaHandler] Disconnected from {self.broker}")
            except Exception as e:
                print(f"[KafkaHandler] Error during disconnect: {e}")
            finally:
                self.producer = None
                self.is_connected = False
                self.broker = None
    
    async def flush(self):
        """Flush any pending messages"""
        if self.producer:
            await self.producer.flush()
    
    def __del__(self):
        """Cleanup on deletion"""
        if self.producer and self.is_connected:
            # Note: This is sync cleanup, async cleanup should be done properly before deletion
            try:
                asyncio.create_task(self.disconnect())
            except:
                pass