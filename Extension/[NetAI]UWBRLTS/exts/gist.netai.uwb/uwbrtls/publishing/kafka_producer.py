import asyncio
import json
import uuid
from typing import Dict, Optional, Any
from datetime import datetime
from aiokafka import AIOKafkaProducer
from ..core.config_manager import get_config_manager

class KafkaUWBProducer:
    """Kafka Producer for publishing Omniverse coordinates as UWB format"""
    
    def __init__(self):
        self.config_manager = get_config_manager()
        
        # Kafka Producer 설정
        kafka_producer_config = self.config_manager.get_kafka_producer_config()
        self.bootstrap_servers = kafka_producer_config.get('bootstrap_servers', 'localhost:9092')
        self.topic_name = kafka_producer_config.get('topic_name', 'uwb-omniverse')
        self.client_id = kafka_producer_config.get('client_id', 'netai-omniverse-producer')
        
        # Publishing 설정
        self.publishing_config = self.config_manager.get_publishing_config()
        
        # Producer 인스턴스
        self._producer = None
        self._is_connected = False
        
        # 통계
        self._messages_sent = 0
        self._last_message_time = None
        
        print(f"Kafka UWB Producer initialized")
        print(f"  Server: {self.bootstrap_servers}")
        print(f"  Topic: {self.topic_name}")
        print(f"  Client ID: {self.client_id}")
    
    async def start(self):
        """Kafka Producer 시작"""
        print("=== Starting Kafka Producer ===")
        
        if self._producer is not None:
            print("Kafka producer is already running")
            return True
        
        try:
            print(f"Creating AIOKafkaProducer with bootstrap_servers: {self.bootstrap_servers}")
            
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            
            print("Starting producer connection...")
            await self._producer.start()
            self._is_connected = True
            
            print(f"Kafka producer started successfully")
            print(f"  Topic: {self.topic_name}")
            print(f"  Bootstrap servers: {self.bootstrap_servers}")
            return True
            
        except Exception as e:
            print(f"Failed to start Kafka producer: {e}")
            import traceback
            traceback.print_exc()
            
            self._producer = None
            self._is_connected = False
            return False
    
    async def stop(self):
        """Kafka Producer 중지"""
        print("=== Stopping Kafka Producer ===")
        
        if self._producer:
            try:
                await self._producer.stop()
                print("Kafka producer stopped")
            except Exception as e:
                print(f"Error stopping Kafka producer: {e}")
        
        self._producer = None
        self._is_connected = False
        print("Kafka producer cleanup completed")
    
    async def publish_uwb_coordinate(self, virtual_tag_id: str, uwb_x: float, uwb_y: float,
                                   object_path: str = None, metadata: Dict[str, Any] = None) -> bool:
        """UWB 좌표 형식으로 메시지 발행"""
        print(f"=== Publishing Message ===")
        print(f"Tag ID: {virtual_tag_id}")
        print(f"Coordinates: ({uwb_x:.3f}, {uwb_y:.3f})")
        print(f"Object Path: {object_path}")
        print(f"Producer Connected: {self._is_connected}")
        print(f"Producer Object: {self._producer is not None}")
        
        if not self._is_connected or not self._producer:
            print("ERROR: Kafka producer is not connected")
            return False
        
        try:
            # UWB 메시지 포맷 생성
            message = self._create_uwb_message(virtual_tag_id, uwb_x, uwb_y, object_path, metadata)
            print(f"Message created: {json.dumps(message, indent=2)}")
            
            # Kafka로 전송
            print(f"Sending to Kafka topic: {self.topic_name}")
            result = await self._producer.send_and_wait(
                topic=self.topic_name,
                key=virtual_tag_id,
                value=message
            )
            
            print(f"Kafka send result: {result}")
            
            # 통계 업데이트
            self._messages_sent += 1
            self._last_message_time = datetime.now()
            
            print(f"Successfully published UWB coordinate for tag {virtual_tag_id}")
            print(f"Total messages sent: {self._messages_sent}")
            return True
            
        except Exception as e:
            print(f"Failed to publish UWB coordinate: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_uwb_message(self, virtual_tag_id: str, uwb_x: float, uwb_y: float,
                           object_path: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """UWB 형식의 메시지 생성"""
        
        # 기본 UWB 메시지 구조
        message = {
            "id": virtual_tag_id,
            "latitude": uwb_x,
            "longitude": uwb_y,
            "raw_timestamp": datetime.now().isoformat(),
            "message_id": str(uuid.uuid4()),
            "source": "omniverse",
            "type": "position_update"
        }
        
        # 추가 메타데이터
        if object_path:
            message["object_path"] = object_path
        
        if metadata:
            message["metadata"] = metadata
        
        # Publishing 설정에서 추가 필드
        try:
            publishing_config = self.publishing_config
            if publishing_config and publishing_config.get('include_precision'):
                precision = self.config_manager.get('uwb.coordinate_precision', 2)
                message["precision"] = precision
            
            if publishing_config and publishing_config.get('include_space_id'):
                space_id = self.config_manager.get('uwb.default_space_id', 1)
                message["space_id"] = space_id
        except Exception as e:
            print(f"Warning: Error adding publishing config fields: {e}")
        
        return message
    
    async def publish_batch_coordinates(self, coordinates: list) -> int:
        """여러 좌표를 일괄 발행"""
        print(f"=== Batch Publishing {len(coordinates)} coordinates ===")
        
        if not self._is_connected or not self._producer:
            print("ERROR: Kafka producer is not connected")
            return 0
        
        success_count = 0
        
        for i, coord_data in enumerate(coordinates):
            try:
                virtual_tag_id = coord_data.get('virtual_tag_id')
                uwb_x = coord_data.get('uwb_x')
                uwb_y = coord_data.get('uwb_y')
                object_path = coord_data.get('object_path')
                metadata = coord_data.get('metadata')
                
                print(f"Batch item {i+1}: {virtual_tag_id} at ({uwb_x}, {uwb_y})")
                
                if virtual_tag_id and uwb_x is not None and uwb_y is not None:
                    success = await self.publish_uwb_coordinate(
                        virtual_tag_id, uwb_x, uwb_y, object_path, metadata
                    )
                    if success:
                        success_count += 1
                else:
                    print(f"Invalid coordinate data: {coord_data}")
                        
            except Exception as e:
                print(f"Error publishing coordinate in batch: {e}")
                continue
        
        print(f"Batch publish completed: {success_count}/{len(coordinates)} successful")
        return success_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Producer 통계 정보 반환"""
        return {
            'is_connected': self._is_connected,
            'messages_sent': self._messages_sent,
            'last_message_time': self._last_message_time.isoformat() if self._last_message_time else None,
            'topic_name': self.topic_name,
            'bootstrap_servers': self.bootstrap_servers,
            'client_id': self.client_id,
            'producer_exists': self._producer is not None
        }
    
    def reset_statistics(self):
        """통계 초기화"""
        self._messages_sent = 0
        self._last_message_time = None
        print("Producer statistics reset")
    
    async def test_publish(self) -> bool:
        """테스트 메시지 발행"""
        print("=== Test Message Publish ===")
        
        return await self.publish_uwb_coordinate(
            virtual_tag_id='TEST_TAG_001',
            uwb_x=1.234,
            uwb_y=5.678,
            object_path='/World/TestObject',
            metadata={'test': True, 'timestamp': datetime.now().isoformat()}
        )

# 전역 Kafka Producer 인스턴스
_kafka_producer = None

def get_kafka_producer() -> KafkaUWBProducer:
    """전역 Kafka Producer 인스턴스 반환"""
    global _kafka_producer
    if _kafka_producer is None:
        _kafka_producer = KafkaUWBProducer()
    return _kafka_producer