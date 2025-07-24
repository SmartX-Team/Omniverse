import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from ..core.config_manager import get_config_manager
from ..core.db_manager import get_db_manager
from ..core.coordinate_transformer import get_coordinate_transformer
from .kafka_producer import get_kafka_producer
from .object_monitor import get_object_monitor

class PublishingManager:
    """Publishing 기능 통합 관리 클래스"""
    
    def __init__(self):
        self.config_manager = get_config_manager()
        self.db_manager = get_db_manager()
        self.coordinate_transformer = get_coordinate_transformer()
        self.kafka_producer = get_kafka_producer()
        try:
            from .object_monitor import get_object_monitor
            self.object_monitor = get_object_monitor()
            print("Object Monitor initialized successfully")
        except ImportError:
            print("Warning: Object Monitor not available")
            self.object_monitor = None
        
        # 상태 관리
        self._is_publishing = False
        self._space_id = self.config_manager.get('uwb.default_space_id', 1)
        
        # 통계
        self._total_published = 0
        self._publish_errors = 0
        self._start_time = None
        
        print(f"Publishing Manager initialized for space_id: {self._space_id}")
    
    async def initialize(self):
        """Publishing Manager 초기화"""
        print("Initializing Publishing Manager...")
        
        # Coordinate Transformer 초기화
        await self.coordinate_transformer.initialize(self._space_id)
        
        # Object Monitor 콜백 설정
        self.object_monitor.set_position_callback(self._on_position_change)
        
        # DB에서 발행 오브젝트 목록 로드
        await self._load_publishing_objects()
        
        print("Publishing Manager initialization completed")
    
    async def start_publishing(self) -> bool:
        """Publishing 시작"""
        if self._is_publishing:
            print("Publishing is already active")
            return True
        
        try:
            # Kafka Producer 시작
            if not await self.kafka_producer.start():
                print("Failed to start Kafka producer")
                return False
            
            # Object Monitor 시작
            await self.object_monitor.start_monitoring()
            
            self._is_publishing = True
            self._start_time = datetime.now()
            
            print("Publishing started successfully")
            return True
            
        except Exception as e:
            print(f"Error starting publishing: {e}")
            return False
    
    async def stop_publishing(self):
        """Publishing 중지"""
        if not self._is_publishing:
            return
        
        try:
            # Object Monitor 중지
            await self.object_monitor.stop_monitoring()
            
            # Kafka Producer 중지
            await self.kafka_producer.stop()
            
            self._is_publishing = False
            
            print("Publishing stopped")
            
        except Exception as e:
            print(f"Error stopping publishing: {e}")
    
    async def add_object(self, object_path: str, object_name: str = None, 
                        virtual_tag_id: str = None, publish_rate: float = 10.0) -> bool:
        """발행 대상 오브젝트 추가"""
        try:
            # DB에 오브젝트 추가
            success = await self.db_manager.add_publishing_object(
                space_id=self._space_id,
                object_path=object_path,
                object_name=object_name,
                virtual_tag_id=virtual_tag_id,
                publish_rate_hz=publish_rate
            )
            
            if not success:
                print(f"Failed to add object to database: {object_path}")
                return False
            
            # DB에서 실제 저장된 정보 다시 로드
            objects = await self.db_manager.fetch_publishing_objects(self._space_id)
            added_object = None
            
            for obj in objects:
                if obj['object_path'] == object_path:
                    added_object = obj
                    break
            
            if not added_object:
                print(f"Object not found after adding: {object_path}")
                return False
            
            # Object Monitor에 추가
            self.object_monitor.add_object(
                object_path=object_path,
                virtual_tag_id=added_object['virtual_tag_id'],
                publish_rate=added_object['publish_rate_hz']
            )
            
            print(f"Successfully added object: {object_path} (tag: {added_object['virtual_tag_id']})")
            return True
            
        except Exception as e:
            print(f"Error adding object: {e}")
            return False
    
    async def remove_object(self, object_path: str) -> bool:
        """발행 대상 오브젝트 제거"""
        try:
            # DB에서 오브젝트 ID 찾기
            objects = await self.db_manager.fetch_publishing_objects(self._space_id)
            object_id = None
            
            for obj in objects:
                if obj['object_path'] == object_path:
                    object_id = obj['id']
                    break
            
            if object_id is None:
                print(f"Object not found in database: {object_path}")
                return False
            
            # DB에서 제거
            success = await self.db_manager.remove_publishing_object(object_id)
            if not success:
                print(f"Failed to remove object from database: {object_path}")
                return False
            
            # Object Monitor에서 제거
            self.object_monitor.remove_object(object_path)
            
            print(f"Successfully removed object: {object_path}")
            return True
            
        except Exception as e:
            print(f"Error removing object: {e}")
            return False
    
    async def update_object_rate(self, object_path: str, publish_rate: float) -> bool:
        """오브젝트 발행 주기 업데이트"""
        try:
            # DB에서 오브젝트 ID 찾기
            objects = await self.db_manager.fetch_publishing_objects(self._space_id)
            object_id = None
            
            for obj in objects:
                if obj['object_path'] == object_path:
                    object_id = obj['id']
                    break
            
            if object_id is None:
                print(f"Object not found: {object_path}")
                return False
            
            # DB 업데이트
            success = await self.db_manager.update_publishing_object(
                object_id, publish_rate_hz=publish_rate
            )
            
            if not success:
                return False
            
            # Object Monitor 업데이트
            self.object_monitor.update_object_rate(object_path, publish_rate)
            
            print(f"Updated publish rate for {object_path}: {publish_rate} Hz")
            return True
            
        except Exception as e:
            print(f"Error updating object rate: {e}")
            return False
    
    async def _load_publishing_objects(self):
        """DB에서 발행 오브젝트 목록 로드"""
        try:
            objects = await self.db_manager.fetch_publishing_objects(self._space_id)
            
            for obj in objects:
                self.object_monitor.add_object(
                    object_path=obj['object_path'],
                    virtual_tag_id=obj['virtual_tag_id'],
                    publish_rate=obj['publish_rate_hz']
                )
            
            print(f"Loaded {len(objects)} publishing objects from database")
            
        except Exception as e:
            print(f"Error loading publishing objects: {e}")
    
    async def _on_position_change(self, object_path: str, virtual_tag_id: str, 
                                position: tuple, timestamp: datetime):
        """위치 변화 콜백 - 좌표 변환 및 발행"""
        try:
            omni_x, omni_y, omni_z = position
            
            # Omniverse → UWB 좌표 변환
            uwb_x, uwb_y = self.coordinate_transformer.transform_omniverse_to_uwb(
                omni_x, omni_y, omni_z
            )
            
            # Kafka로 UWB 좌표 발행
            success = await self.kafka_producer.publish_uwb_coordinate(
                virtual_tag_id=virtual_tag_id,
                uwb_x=uwb_x,
                uwb_y=uwb_y,
                object_path=object_path,
                metadata={
                    'omniverse_position': {'x': omni_x, 'y': omni_y, 'z': omni_z},
                    'space_id': self._space_id,
                    'timestamp': timestamp.isoformat()
                }
            )
            
            if success:
                self._total_published += 1
            else:
                self._publish_errors += 1
            
        except Exception as e:
            print(f"Error processing position change for {object_path}: {e}")
            self._publish_errors += 1
    
    def get_publishing_objects(self) -> List[Dict[str, Any]]:
        """현재 발행 중인 오브젝트 목록 반환"""
        return self.object_monitor.get_monitored_objects()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Publishing 통계 반환"""
        # 기본 통계
        stats = {
            'is_publishing': self._is_publishing,
            'space_id': self._space_id,
            'total_published': self._total_published,
            'publish_errors': self._publish_errors,
            'start_time': self._start_time.isoformat() if self._start_time else None
        }
        
        # Object Monitor 통계 추가
        monitor_stats = self.object_monitor.get_statistics()
        stats.update({
            'monitored_objects': monitor_stats,
            'objects_count': monitor_stats.get('monitored_objects_count', 0),
            'enabled_objects_count': monitor_stats.get('enabled_objects_count', 0)
        })
        
        # Kafka Producer 통계 추가
        producer_stats = self.kafka_producer.get_statistics()
        stats.update({
            'kafka_producer': producer_stats,
            'kafka_connected': producer_stats.get('is_connected', False),
            'messages_sent': producer_stats.get('messages_sent', 0)
        })

# 전역 Publishing Manager 인스턴스
_publishing_manager = None

def get_publishing_manager() -> PublishingManager:
    """전역 Publishing Manager 인스턴스 반환"""
    global _publishing_manager
    if _publishing_manager is None:
        _publishing_manager = PublishingManager()
    return _publishing_manager