import asyncio
import json
from typing import Dict, Callable, Optional, Any
from aiokafka import AIOKafkaConsumer
from .config_manager import get_config_manager
from .db_manager import get_db_manager
from .coordinate_transformer import get_coordinate_transformer

class KafkaMessageProcessor:
    """Kafka 메시지 처리 클래스"""
    
    def __init__(self):
        self.config_manager = get_config_manager()
        self.db_manager = get_db_manager()
        self.coordinate_transformer = get_coordinate_transformer()
        
        # Kafka 설정
        kafka_config = self.config_manager.get_kafka_config()
        self.bootstrap_servers = kafka_config.get('bootstrap_servers', '210.125.85.62:9094')
        self.topic_name = kafka_config.get('topic_name', 'omniverse-uwb')
        self.group_id = kafka_config.get('group_id', 'netai-uwb-group')
        
        # 상태 관리
        self._consumer = None
        self._consuming_task = None
        self._tag_mappings = {}
        self._message_callback = None
        
        print(f"Kafka processor initialized - Server: {self.bootstrap_servers}, Topic: {self.topic_name}")
    
    def set_message_callback(self, callback: Callable):
        """메시지 처리 완료 시 호출될 콜백 함수 설정"""
        self._message_callback = callback
    
    async def initialize(self):
        """초기화 - 태그 매핑 및 좌표 변환기 설정"""
        print("Initializing Kafka message processor...")
        
        # 태그 매핑 로드
        self._tag_mappings = await self.db_manager.fetch_tag_mappings()
        print(f"Loaded {len(self._tag_mappings)} tag mappings")
        
        # 좌표 변환기 초기화
        await self.coordinate_transformer.initialize()
        
        print("Kafka message processor initialization completed")
    
    async def start_consuming(self):
        """메시지 소비 시작"""
        if self._consuming_task is None or self._consuming_task.done():
            self._consuming_task = asyncio.create_task(self._consume_messages())
            print("Started Kafka message consumption")
        else:
            print("Kafka consumer is already running")
    
    async def stop_consuming(self):
        """메시지 소비 중지"""
        if self._consuming_task and not self._consuming_task.done():
            self._consuming_task.cancel()
            try:
                await self._consuming_task
            except asyncio.CancelledError:
                pass
        
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
            
        print("Stopped Kafka message consumption")
    
    async def _consume_messages(self):
        """메시지 소비 메인 루프"""
        print("Initializing Kafka consumer...")
        
        self._consumer = AIOKafkaConsumer(
            self.topic_name,
            bootstrap_servers=self.bootstrap_servers,
            auto_offset_reset="earliest",
            group_id=self.group_id
        )
        
        try:
            await self._consumer.start()
            print(f"Kafka consumer started successfully - Topic: {self.topic_name}")
            
            async for msg in self._consumer:
                try:
                    decoded_message = msg.value.decode('utf-8')
                    # 메시지 처리를 별도 태스크로 실행하여 consumer 블로킹 방지
                    asyncio.create_task(self._process_single_message(decoded_message))
                except Exception as e:
                    print(f"Error decoding Kafka message: {e}")
                    
        except Exception as e:
            print(f"Error in Kafka consumer: {e}")
        finally:
            if self._consumer:
                await self._consumer.stop()
                self._consumer = None
            print("Kafka consumer stopped")
    
    async def _process_single_message(self, decoded_message: str):
        """단일 메시지 처리"""
        try:
            # JSON 디시리얼라이즈
            message_data = json.loads(decoded_message)
            
            # 필수 필드 검증
            required_fields = ['id', 'latitude', 'longitude']
            for field in required_fields:
                if field not in message_data:
                    print(f"Warning: Missing required field '{field}' in message")
                    return
            
            # 태그 ID 및 매핑 정보 조회
            tag_id = str(message_data['id'])
            raw_timestamp = message_data.get('raw_timestamp')
            uwb_x = float(message_data['latitude'])  # UWB에서는 latitude가 실제로 X 좌표
            uwb_y = float(message_data['longitude']) # UWB에서는 longitude가 실제로 Y 좌표
            
            # 태그 매핑 확인
            object_name = self._tag_mappings.get(tag_id)
            if object_name is None:
                print(f"Warning: No mapping found for tag ID {tag_id}")
                return
            
            print(f"Processing message for tag {tag_id} -> object {object_name}: UWB({uwb_x}, {uwb_y})")
            
            # 좌표 변환 및 저장
            omni_x, omni_y, omni_z = await self.coordinate_transformer.transform_and_save(
                tag_id=tag_id,
                uwb_x=uwb_x,
                uwb_y=uwb_y,
                raw_timestamp=raw_timestamp or "unknown"
            )
            
            print(f"Transformed coordinates for {object_name}: Omniverse({omni_x}, {omni_y}, {omni_z})")
            
            # 타임스탬프 기록
            if raw_timestamp:
                await self.db_manager.record_timestamp(tag_id, raw_timestamp)
            
            # 콜백 호출 (Omniverse 오브젝트 이동용)
            if self._message_callback:
                await self._message_callback(
                    object_name=object_name,
                    tag_id=tag_id,
                    position=(omni_x, omni_y, omni_z),
                    uwb_coords=(uwb_x, uwb_y),
                    raw_timestamp=raw_timestamp
                )
                
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON message: {e}")
        except ValueError as e:
            print(f"Error converting coordinates to float: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")
    
    async def update_tag_mappings(self):
        """태그 매핑 정보 업데이트"""
        print("Updating tag mappings from database...")
        self._tag_mappings = await self.db_manager.fetch_tag_mappings()
        print(f"Updated tag mappings: {len(self._tag_mappings)} mappings loaded")
    
    async def reload_coordinate_mapping(self, space_id: Optional[int] = None):
        """좌표 매핑 정보 다시 로드"""
        print("Reloading coordinate mapping...")
        await self.coordinate_transformer.reload_mapping_data(space_id)
        print("Coordinate mapping reloaded")
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 정보 반환"""
        return {
            'is_consuming': self._consuming_task is not None and not self._consuming_task.done(),
            'consumer_connected': self._consumer is not None,
            'tag_mappings_count': len(self._tag_mappings),
            'kafka_config': {
                'bootstrap_servers': self.bootstrap_servers,
                'topic_name': self.topic_name,
                'group_id': self.group_id
            },
            'coordinate_transform_info': self.coordinate_transformer.get_transform_info()
        }
    
    def get_tag_mappings(self) -> Dict[str, str]:
        """현재 로드된 태그 매핑 반환"""
        return self._tag_mappings.copy()

# 전역 Kafka 메시지 프로세서 인스턴스
_kafka_processor = None

def get_kafka_processor() -> KafkaMessageProcessor:
    """전역 Kafka 메시지 프로세서 인스턴스 반환"""
    global _kafka_processor
    if _kafka_processor is None:
        _kafka_processor = KafkaMessageProcessor()
    return _kafka_processor