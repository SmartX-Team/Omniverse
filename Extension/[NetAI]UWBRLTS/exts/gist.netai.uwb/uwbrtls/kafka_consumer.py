import asyncio
import json
from typing import Dict, Callable, Optional, Any
from aiokafka import AIOKafkaConsumer
from .config_manager import get_config_manager
from .db_manager import get_db_manager
from .coordinate_transformer import get_coordinate_transformer

class KafkaMessageProcessor:
    """Kafka 메시지 처리 클래스 v2 - DB 쿼리 중앙화"""
    
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
        self._message_callback = None
        
        # 매핑 캐시 (DB에서 로드된 정보를 메모리에 캐시)
        self._tag_mappings = {}      # uwb_tag 테이블: {tag_id: device_name}
        self._prim_mappings = {}     # uwb_prim_mappings 테이블: {tag_id: prim_path}
        
        # 좌표 매핑 설정 로드
        self._load_field_mapping()
        
        print(f"Kafka processor v2 initialized - Server: {self.bootstrap_servers}, Topic: {self.topic_name}")
        print(f"Using coordinate format: {self.config_manager.get('coordinate_mapping.input_format', 'uwb')}")
    
    def _load_field_mapping(self):
        """설정에서 필드 매핑 정보 로드"""
        input_format = self.config_manager.get("coordinate_mapping.input_format", "uwb")
        
        if input_format in self.config_manager.get("coordinate_mapping.alternative_formats", {}):
            self.field_mapping = self.config_manager.get(f"coordinate_mapping.alternative_formats.{input_format}")
        else:
            self.field_mapping = self.config_manager.get("coordinate_mapping.field_mapping", {
                "tag_id_field": "id",
                "x_field": "latitude", 
                "y_field": "longitude",
                "timestamp_field": "raw_timestamp",
                "height_field": None
            })
        
        print(f"Field mapping loaded: {self.field_mapping}")
    
    def set_message_callback(self, callback: Callable):
        """메시지 처리 완료 시 호출될 콜백 함수 설정"""
        self._message_callback = callback
    
    async def initialize(self):
        """초기화 - 모든 매핑 정보를 DB에서 캐시로 로드"""
        print("Initializing Kafka message processor v2...")
        
        # 기본 태그 매핑 로드 (uwb_tag 테이블에서)
        self._tag_mappings = await self.db_manager.fetch_tag_mappings()
        print(f"Loaded {len(self._tag_mappings)} tag mappings from uwb_tag table")
        
        # Prim 매핑 로드 (uwb_prim_mappings 테이블에서)
        space_id = self.config_manager.get("transformation.space_id", 1)
        self._prim_mappings = await self.db_manager.fetch_prim_mappings(space_id)
        print(f"Loaded {len(self._prim_mappings)} prim mappings from uwb_prim_mappings table")
        
        # 좌표 변환기 초기화
        await self.coordinate_transformer.initialize()
        
        print("Kafka message processor v2 initialization completed")
    
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
    
    def _extract_coordinates_from_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """메시지에서 설정된 필드 매핑에 따라 좌표 정보 추출"""
        try:
            # 필수 필드 추출
            tag_id = message_data.get(self.field_mapping["tag_id_field"])
            x_value = message_data.get(self.field_mapping["x_field"])
            y_value = message_data.get(self.field_mapping["y_field"])
            timestamp = message_data.get(self.field_mapping["timestamp_field"])
            
            # 선택적 필드
            height = message_data.get(self.field_mapping.get("height_field")) if self.field_mapping.get("height_field") else None
            
            # 필수 필드 검증
            if tag_id is None or x_value is None or y_value is None:
                missing_fields = []
                if tag_id is None: missing_fields.append(self.field_mapping["tag_id_field"])
                if x_value is None: missing_fields.append(self.field_mapping["x_field"])
                if y_value is None: missing_fields.append(self.field_mapping["y_field"])
                print(f"Missing required fields: {missing_fields}")
                return None
            
            # 좌표 범위 검증
            if not self._validate_coordinates(x_value, y_value):
                return None
            
            return {
                "tag_id": str(tag_id),
                "x": float(x_value),
                "y": float(y_value),
                "timestamp": timestamp,
                "height": float(height) if height is not None else None
            }
            
        except (KeyError, ValueError, TypeError) as e:
            print(f"Error extracting coordinates: {e}")
            return None
    
    def _validate_coordinates(self, x: float, y: float) -> bool:
        """좌표 유효성 검증"""
        try:
            coordinate_type = self.config_manager.get("coordinate_mapping.input_format", "uwb")
            bounds = self.config_manager.get("validation.coordinate_bounds", {})
            
            if coordinate_type == "gps":
                # GPS 좌표 검증 (위도/경도)
                lat_bounds = bounds.get("latitude", {"min": -90.0, "max": 90.0})
                lon_bounds = bounds.get("longitude", {"min": -180.0, "max": 180.0})
                
                if not (lat_bounds["min"] <= y <= lat_bounds["max"]):
                    print(f"Invalid latitude: {y}")
                    return False
                if not (lon_bounds["min"] <= x <= lon_bounds["max"]):
                    print(f"Invalid longitude: {x}")
                    return False
            
            elif coordinate_type == "uwb":
                # UWB 좌표 검증
                x_bounds = bounds.get("uwb_x", {"min": -100.0, "max": 100.0})
                y_bounds = bounds.get("uwb_y", {"min": -100.0, "max": 100.0})
                
                if not (x_bounds["min"] <= x <= x_bounds["max"]):
                    print(f"Invalid UWB X coordinate: {x}")
                    return False
                if not (y_bounds["min"] <= y <= y_bounds["max"]):
                    print(f"Invalid UWB Y coordinate: {y}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Coordinate validation error: {e}")
            return False
    
    def _get_object_name_for_tag(self, tag_id: str) -> Optional[str]:
        """태그 ID에 따른 오브젝트 이름 - 캐시에서만 조회 (DB 쿼리 없음)"""
        try:
            # 1단계: Prim 매핑 테이블에서 조회 (우선순위 - 전체 경로)
            if tag_id in self._prim_mappings:
                prim_path = self._prim_mappings[tag_id]
                print(f"Found prim mapping for tag {tag_id}: {prim_path}")
                return prim_path
            
            # 2단계: 기본 태그 매핑에서 조회 (디바이스 이름)
            if tag_id in self._tag_mappings:
                device_name = self._tag_mappings[tag_id]
                print(f"Found device mapping for tag {tag_id}: {device_name}")
                return device_name
            
            # 3단계: 기본 경로 반환
            default_path = f"/World/Objects/Tag{tag_id}"
            print(f"Using default path for tag {tag_id}: {default_path}")
            return default_path
            
        except Exception as e:
            print(f"Error getting object name for tag {tag_id}: {e}")
            return f"/World/Objects/Tag{tag_id}"
    
    async def _process_single_message(self, decoded_message: str):
        """단일 메시지 처리 - 캐시된 매핑만 사용"""
        try:
            # JSON 디시리얼라이즈
            message_data = json.loads(decoded_message)
            
            # 좌표 정보 추출 (설정된 필드 매핑 사용)
            coord_data = self._extract_coordinates_from_message(message_data)
            if not coord_data:
                return
            
            tag_id = coord_data["tag_id"]
            x = coord_data["x"]
            y = coord_data["y"]
            timestamp = coord_data["timestamp"]
            height = coord_data["height"]
            
            # 태그 매핑 확인 (캐시에서만 조회!)
            object_name = self._get_object_name_for_tag(tag_id)
            if object_name is None:
                print(f"Warning: No mapping found for tag ID {tag_id}")
                return
            
            coordinate_type = self.config_manager.get("coordinate_mapping.input_format", "uwb")
            print(f"Processing {coordinate_type} message for tag {tag_id} -> object {object_name}: ({x}, {y})")
            
            # 좌표 변환 및 저장 (coordinate_transformer가 GPS/UWB 자동 판별)
            omni_x, omni_y, omni_z = await self.coordinate_transformer.transform_and_save(
                tag_id=tag_id,
                input_x=x,
                input_y=y,
                space_id=self.config_manager.get("transformation.space_id", 1),
                raw_timestamp=timestamp or "unknown",
                input_height=height
            )
            
            print(f"Transformed coordinates for {object_name}: Omniverse({omni_x}, {omni_y}, {omni_z})")
            
            # 콜백 호출 (Omniverse 오브젝트 이동용)
            if self._message_callback:
                await self._message_callback(
                    object_name=object_name,
                    tag_id=tag_id,
                    position=(omni_x, omni_y, omni_z),
                    uwb_coords=(x, y),  # 원본 좌표 전달
                    raw_timestamp=timestamp
                )
                
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON message: {e}")
        except ValueError as e:
            print(f"Error converting coordinates to float: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")
    
    async def update_tag_mappings(self):
        """매핑 정보 업데이트 - DB에서 다시 로드"""
        print("Updating all tag mappings from database...")
        
        # 기본 태그 매핑 업데이트 (uwb_tag 테이블)
        self._tag_mappings = await self.db_manager.fetch_tag_mappings()
        
        # Prim 매핑 업데이트 (uwb_prim_mappings 테이블)
        space_id = self.config_manager.get("transformation.space_id", 1)
        self._prim_mappings = await self.db_manager.fetch_prim_mappings(space_id)
        
        print(f"Updated mappings: {len(self._tag_mappings)} tag mappings, {len(self._prim_mappings)} prim mappings")
    
    async def reload_coordinate_mapping(self, space_id: Optional[int] = None):
        """좌표 매핑 정보 다시 로드"""
        print("Reloading coordinate mapping...")
        await self.coordinate_transformer.reload_mapping_data(space_id)
        print("Coordinate mapping reloaded")
    
    def update_field_mapping(self, new_format: str):
        """런타임에 필드 매핑 변경"""
        self.config_manager.set("coordinate_mapping.input_format", new_format)
        self._load_field_mapping()
        print(f"Field mapping updated to: {new_format}")
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 정보 반환"""
        return {
            'is_consuming': self._consuming_task is not None and not self._consuming_task.done(),
            'consumer_connected': self._consumer is not None,
            'tag_mappings_count': len(self._tag_mappings),
            'prim_mappings_count': len(self._prim_mappings),
            'coordinate_format': self.config_manager.get("coordinate_mapping.input_format", "uwb"),
            'field_mapping': self.field_mapping,
            'kafka_config': {
                'bootstrap_servers': self.bootstrap_servers,
                'topic_name': self.topic_name,
                'group_id': self.group_id
            },
            'coordinate_transform_info': self.coordinate_transformer.get_transform_info()
        }
    
    def get_tag_mappings(self) -> Dict[str, str]:
        """현재 로드된 기본 태그 매핑 반환 (uwb_tag 테이블)"""
        return self._tag_mappings.copy()
    
    def get_prim_mappings(self) -> Dict[str, str]:
        """현재 로드된 Prim 매핑 반환 (uwb_prim_mappings 테이블)"""
        return self._prim_mappings.copy()
    
    def get_all_mappings(self) -> Dict[str, Dict[str, str]]:
        """모든 매핑 정보 반환"""
        return {
            'tag_mappings': self._tag_mappings.copy(),
            'prim_mappings': self._prim_mappings.copy()
        }

# 전역 Kafka 메시지 프로세서 인스턴스
_kafka_processor = None

def get_kafka_processor() -> KafkaMessageProcessor:
    """전역 Kafka 메시지 프로세서 인스턴스 반환"""
    global _kafka_processor
    if _kafka_processor is None:
        _kafka_processor = KafkaMessageProcessor()
    return _kafka_processor