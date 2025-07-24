import asyncio
from typing import Dict, List, Callable, Optional, Tuple, Any
from datetime import datetime
from omni.usd import get_context
from pxr import Usd, UsdGeom, Gf
from ..core.config_manager import get_config_manager

class OmniverseObjectMonitor:
    """Omniverse Stage에서 오브젝트 위치를 모니터링 - 플래그 기반 주기적/변화량 발행"""
    
    def __init__(self):
        self.config_manager = get_config_manager()
        self.publishing_config = self.config_manager.get_publishing_config()
        
        # 모니터링 설정
        self.monitor_rate = self.publishing_config.get('default_publish_rate', 10.0)  # Hz
        
        # 발행 모드 설정 - 기본값: 주기적 발행
        self.always_publish = self.publishing_config.get('always_publish', True)
        self.position_threshold = self.publishing_config.get('position_change_threshold', 0.01)
        self.enable_smoothing = self.publishing_config.get('enable_position_smoothing', False)
        
        # 모니터링 상태
        self._is_monitoring = False
        self._monitor_task = None
        self._position_callback = None
        
        # 추적 대상 오브젝트들
        self._monitored_objects = {}  # {object_path: object_info}
        self._last_positions = {}     # {object_path: (x, y, z, timestamp)}
        
        # 통계
        self._position_updates = 0
        self._last_update_time = None
        
        print(f"Object Monitor initialized")
        print(f"  Rate: {self.monitor_rate} Hz")
        print(f"  Always Publish: {self.always_publish}")
        if not self.always_publish:
            print(f"  Position Threshold: {self.position_threshold}")
    
    def set_position_callback(self, callback: Callable):
        """위치 변화 콜백 함수 설정"""
        self._position_callback = callback
    
    def add_object(self, object_path: str, virtual_tag_id: str, publish_rate: float = None):
        """모니터링 대상 오브젝트 추가"""
        if publish_rate is None:
            publish_rate = self.monitor_rate
        
        self._monitored_objects[object_path] = {
            'virtual_tag_id': virtual_tag_id,
            'publish_rate': publish_rate,
            'last_publish_time': None,
            'enabled': True
        }
        
        print(f"Added object to monitor: {object_path} (tag: {virtual_tag_id}, rate: {publish_rate} Hz)")
    
    def remove_object(self, object_path: str):
        """모니터링 대상에서 오브젝트 제거"""
        if object_path in self._monitored_objects:
            del self._monitored_objects[object_path]
            if object_path in self._last_positions:
                del self._last_positions[object_path]
            print(f"Removed object from monitor: {object_path}")
    
    def update_object_rate(self, object_path: str, publish_rate: float):
        """오브젝트 발행 주기 업데이트"""
        if object_path in self._monitored_objects:
            self._monitored_objects[object_path]['publish_rate'] = publish_rate
            print(f"Updated publish rate for {object_path}: {publish_rate} Hz")
    
    def enable_object(self, object_path: str, enabled: bool):
        """오브젝트 모니터링 활성화/비활성화"""
        if object_path in self._monitored_objects:
            self._monitored_objects[object_path]['enabled'] = enabled
            status = "enabled" if enabled else "disabled"
            print(f"Object {object_path} monitoring {status}")
    
    def set_publish_mode(self, always_publish: bool):
        """발행 모드 변경"""
        self.always_publish = always_publish
        mode = "Always Publish" if always_publish else "Change Detection"
        print(f"Publishing mode changed to: {mode}")
    
    async def start_monitoring(self):
        """오브젝트 모니터링 시작"""
        if self._is_monitoring:
            print("Object monitoring is already running")
            return
        
        if not self._monitored_objects:
            print("No objects to monitor")
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        mode = "Always Publish" if self.always_publish else "Change Detection"
        print(f"Started monitoring {len(self._monitored_objects)} objects in {mode} mode")
    
    async def stop_monitoring(self):
        """오브젝트 모니터링 중지"""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        print("Stopped object monitoring")
    
    async def _monitor_loop(self):
        """메인 모니터링 루프 - 플래그 기반 발행"""
        while self._is_monitoring:
            try:
                # 각 오브젝트의 위치 체크
                for object_path, object_info in self._monitored_objects.items():
                    if not object_info['enabled']:
                        continue
                    
                    # 발행 주기 체크
                    if not self._should_publish(object_path, object_info):
                        continue
                    
                    # 현재 위치 가져오기
                    current_position = self._get_object_position(object_path)
                    if current_position is None:
                        continue
                    
                    # 발행 조건 체크
                    should_publish = False
                    
                    if self.always_publish:
                        # 항상 발행 모드: 주기만 맞으면 발행
                        should_publish = True
                        print(f"Publishing {object_path} (always_publish mode)")
                    else:
                        # 변화량 기반 발행 모드: 위치가 변했을 때만 발행
                        if self._has_position_changed(object_path, current_position):
                            should_publish = True
                            print(f"Publishing {object_path} (position changed)")
                    
                    if should_publish:
                        await self._handle_position_update(object_path, object_info, current_position)
                
                # 모니터링 주기 대기 (최고 주파수 기준)
                max_rate = max((obj['publish_rate'] for obj in self._monitored_objects.values()), default=self.monitor_rate)
                sleep_time = 1.0 / max_rate
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(0.1)  # 에러 시 잠시 대기
    
    def _should_publish(self, object_path: str, object_info: Dict[str, Any]) -> bool:
        """발행 주기에 따라 발행할지 결정"""
        publish_rate = object_info['publish_rate']
        last_publish_time = object_info['last_publish_time']
        
        if last_publish_time is None:
            return True
        
        time_since_last = (datetime.now() - last_publish_time).total_seconds()
        min_interval = 1.0 / publish_rate
        
        return time_since_last >= min_interval
    
    def _get_object_position(self, object_path: str) -> Optional[Tuple[float, float, float]]:
        """오브젝트의 현재 위치 가져오기 - 실시간 좌표 지원"""
        try:
            stage = get_context().get_stage()
            if not stage:
                return None
            
            prim = stage.GetPrimAtPath(object_path)
            if not prim or not prim.IsValid():
                return None
            
            # 실시간 타임코드 사용
            current_time = Usd.TimeCode.Default()
            
            # 월드 변환 행렬에서 위치 추출
            xformable = UsdGeom.Xformable(prim)
            world_transform = xformable.ComputeLocalToWorldTransform(current_time)
            translation = world_transform.ExtractTranslation()
            
            return (float(translation[0]), float(translation[1]), float(translation[2]))
            
        except Exception as e:
            print(f"Error getting position for {object_path}: {e}")
            return None
    
    def _has_position_changed(self, object_path: str, current_position: Tuple[float, float, float]) -> bool:
        """위치가 변경되었는지 확인 (always_publish=False일 때만 사용)"""
        if object_path not in self._last_positions:
            return True
        
        last_pos = self._last_positions[object_path][:3]  # x, y, z만 비교
        
        # 변화량 계산
        distance = sum((a - b) ** 2 for a, b in zip(current_position, last_pos)) ** 0.5
        
        return distance >= self.position_threshold
    
    async def _handle_position_update(self, object_path: str, object_info: Dict[str, Any], 
                                    current_position: Tuple[float, float, float]):
        """위치 업데이트 처리 (이름 변경: 항상 발행 가능)"""
        try:
            # 위치 정보 업데이트
            current_time = datetime.now()
            self._last_positions[object_path] = (*current_position, current_time)
            object_info['last_publish_time'] = current_time
            
            # 통계 업데이트
            self._position_updates += 1
            self._last_update_time = current_time
            
            # 콜백 호출
            if self._position_callback:
                await self._position_callback(
                    object_path=object_path,
                    virtual_tag_id=object_info['virtual_tag_id'],
                    position=current_position,
                    timestamp=current_time
                )
            
        except Exception as e:
            print(f"Error handling position update for {object_path}: {e}")
    
    def get_monitored_objects(self) -> List[Dict[str, Any]]:
        """모니터링 중인 오브젝트 목록 반환"""
        objects = []
        for object_path, object_info in self._monitored_objects.items():
            last_position = self._last_positions.get(object_path)
            
            obj_data = {
                'object_path': object_path,
                'virtual_tag_id': object_info['virtual_tag_id'],
                'publish_rate': object_info['publish_rate'],
                'enabled': object_info['enabled'],
                'last_publish_time': object_info['last_publish_time'],
                'last_position': last_position[:3] if last_position else None,
                'last_position_time': last_position[3] if last_position else None
            }
            objects.append(obj_data)
        
        return objects
    
    def get_statistics(self) -> Dict[str, Any]:
        """모니터링 통계 반환"""
        return {
            'is_monitoring': self._is_monitoring,
            'monitored_objects_count': len(self._monitored_objects),
            'enabled_objects_count': sum(1 for obj in self._monitored_objects.values() if obj['enabled']),
            'position_updates': self._position_updates,
            'last_update_time': self._last_update_time.isoformat() if self._last_update_time else None,
            'monitor_rate': self.monitor_rate,
            'always_publish': self.always_publish,
            'position_threshold': self.position_threshold
        }
    
    def reset_statistics(self):
        """통계 초기화"""
        self._position_updates = 0
        self._last_update_time = None
        print("Object monitor statistics reset")

# 전역 Object Monitor 인스턴스
_object_monitor = None

def get_object_monitor() -> OmniverseObjectMonitor:
    """전역 Object Monitor 인스턴스 반환"""
    global _object_monitor
    if _object_monitor is None:
        _object_monitor = OmniverseObjectMonitor()
    return _object_monitor