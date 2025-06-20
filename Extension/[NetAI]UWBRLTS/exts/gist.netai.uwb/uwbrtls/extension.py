import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, Gf
import asyncio
from typing import Dict, Any

from .config_manager import get_config_manager
from .db_manager import get_db_manager
from .coordinate_transformer import get_coordinate_transformer
from .kafka_consumer import get_kafka_processor

class NetAIUWBTrackingExtension(omni.ext.IExt):
    """NetAI UWB 추적 Extension 메인 클래스"""
    
    def __init__(self):
        super().__init__()
        
        # 모듈 인스턴스들
        self.config_manager = get_config_manager()
        self.db_manager = get_db_manager()
        self.coordinate_transformer = get_coordinate_transformer()
        self.kafka_processor = get_kafka_processor()
        
        # UI 및 상태 관리
        self._window = None
        self._status_label = None
        self._info_label = None
        
        # Omniverse 관련
        self.prim_map = {}
        self._map_update_task = None
        
        print("NetAI UWB Tracking Extension initialized")
    
    def on_startup(self, ext_id):
        """Extension 시작 시 호출"""
        print(f"[gist.netai.uwb] startup - Extension ID: {ext_id}")
        
        # UI 생성
        self._create_ui()
        
        # 초기화 태스크 시작
        asyncio.ensure_future(self._initialize_extension())
    
    def on_shutdown(self):
        """Extension 종료 시 호출"""
        print("[gist.netai.uwb] Extension shutdown initiated")
        
        # Kafka 소비 중지
        if self.kafka_processor:
            asyncio.ensure_future(self.kafka_processor.stop_consuming())
        
        # 주기적 업데이트 태스크 취소
        if self._map_update_task:
            self._map_update_task.cancel()
        
        # DB 연결 종료
        if self.db_manager:
            self.db_manager.close()
        
        # UI 정리
        if self._window:
            self._window.destroy()
            self._window = None
        
        print("NetAI UWB Tracking Extension shutdown completed")
    
    def _create_ui(self):
        """UI 생성"""
        self._window = ui.Window("NetAI UWB Tracking", width=600, height=400)
        
        with self._window.frame:
            with ui.VStack(spacing=10):
                # 제목
                ui.Label("NetAI UWB Real-time Tracking System", 
                        style={"font_size": 18, "color": 0xFF00AAFF})
                
                ui.Separator()
                
                # 상태 표시
                with ui.HStack():
                    ui.Label("Status: ", width=80)
                    self._status_label = ui.Label("Initializing...", 
                                                 style={"color": 0xFFFFAA00})
                
                # 정보 표시
                with ui.VStack():
                    ui.Label("System Information:", style={"font_size": 14})
                    self._info_label = ui.Label("Loading...", 
                                              style={"font_size": 12, "color": 0xFFAAAAAA})
                
                ui.Separator()
                
                # 제어 버튼들
                with ui.HStack(spacing=10):
                    ui.Button("Start Tracking", 
                             clicked_fn=lambda: asyncio.ensure_future(self._start_tracking()),
                             width=120, height=40)
                    
                    ui.Button("Stop Tracking", 
                             clicked_fn=lambda: asyncio.ensure_future(self._stop_tracking()),
                             width=120, height=40)
                    
                    ui.Button("Refresh Data", 
                             clicked_fn=lambda: asyncio.ensure_future(self._refresh_data()),
                             width=120, height=40)
                
                ui.Separator()
                
                # 좌표계 정보
                with ui.VStack():
                    ui.Label("Coordinate System Info:", style={"font_size": 14})
                    with ui.HStack():
                        ui.Button("Reload Mappings", 
                                 clicked_fn=lambda: asyncio.ensure_future(self._reload_mappings()),
                                 width=150)
                        ui.Button("Show Transform Info", 
                                 clicked_fn=self._show_transform_info,
                                 width=150)
    
    async def _initialize_extension(self):
        """Extension 초기화"""
        try:
            self._update_status("Initializing system...")
            
            # Stage 데이터 로딩
            await self._load_stage_data()
            
            # Kafka 프로세서 초기화
            await self.kafka_processor.initialize()
            
            # 메시지 콜백 설정
            self.kafka_processor.set_message_callback(self._on_position_update)
            
            # 주기적 업데이트 시작
            self._map_update_task = asyncio.create_task(self._periodic_updates())
            
            # UI 정보 업데이트
            await self._update_info_display()
            
            self._update_status("Ready")
            print("Extension initialization completed successfully")
            
        except Exception as e:
            print(f"Error during extension initialization: {e}")
            self._update_status(f"Error: {e}")
    
    async def _load_stage_data(self):
        """Omniverse Stage 데이터 로드"""
        print("Loading Omniverse stage data...")
        stage = get_context().get_stage()
        
        # Prim 맵 구축
        self.prim_map = {}
        for prim in stage.Traverse():
            self.prim_map[prim.GetName()] = prim
        
        print(f"Loaded {len(self.prim_map)} prims from stage")
    
    async def _periodic_updates(self):
        """주기적 데이터 업데이트"""
        update_interval = self.config_manager.get('uwb.update_interval', 300)
        
        while True:
            try:
                await asyncio.sleep(update_interval)
                print("Performing periodic data update...")
                
                # 태그 매핑 업데이트
                await self.kafka_processor.update_tag_mappings()
                
                # UI 정보 업데이트
                await self._update_info_display()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic update: {e}")
    
    async def _start_tracking(self):
        """추적 시작"""
        try:
            self._update_status("Starting tracking...")
            await self.kafka_processor.start_consuming()
            self._update_status("Tracking active")
            print("UWB tracking started")
        except Exception as e:
            print(f"Error starting tracking: {e}")
            self._update_status(f"Error: {e}")
    
    async def _stop_tracking(self):
        """추적 중지"""
        try:
            self._update_status("Stopping tracking...")
            await self.kafka_processor.stop_consuming()
            self._update_status("Tracking stopped")
            print("UWB tracking stopped")
        except Exception as e:
            print(f"Error stopping tracking: {e}")
            self._update_status(f"Error: {e}")
    
    async def _refresh_data(self):
        """데이터 새로고침"""
        try:
            self._update_status("Refreshing data...")
            
            # Stage 데이터 다시 로드
            await self._load_stage_data()
            
            # 태그 매핑 업데이트
            await self.kafka_processor.update_tag_mappings()
            
            # 좌표 매핑 다시 로드
            await self.kafka_processor.reload_coordinate_mapping()
            
            # UI 정보 업데이트
            await self._update_info_display()
            
            self._update_status("Data refreshed")
            print("Data refresh completed")
            
        except Exception as e:
            print(f"Error refreshing data: {e}")
            self._update_status(f"Error: {e}")
    
    async def _reload_mappings(self):
        """매핑 정보 다시 로드"""
        try:
            await self.kafka_processor.reload_coordinate_mapping()
            await self._update_info_display()
            print("Coordinate mappings reloaded")
        except Exception as e:
            print(f"Error reloading mappings: {e}")
    
    def _show_transform_info(self):
        """좌표 변환 정보 표시"""
        transform_info = self.coordinate_transformer.get_transform_info()
        
        info_text = "Coordinate Transform Information:\n"
        info_text += f"Space ID: {transform_info.get('space_id', 'N/A')}\n"
        info_text += f"Mapping: {transform_info.get('mapping_name', 'N/A')}\n"
        
        bounds = transform_info.get('uwb_bounds', {})
        info_text += f"UWB Bounds: ({bounds.get('min_x')}, {bounds.get('min_y')}) to ({bounds.get('max_x')}, {bounds.get('max_y')})\n"
        
        params = transform_info.get('transform_params', {})
        info_text += f"Scale: ({params.get('scale_x')}, {params.get('scale_y')})\n"
        info_text += f"Translation: ({params.get('translate_x')}, {params.get('translate_y')}, {params.get('translate_z')})\n"
        info_text += f"Rotation Z: {params.get('rotation_z')} radians\n"
        
        info_text += f"Calibration Points: {transform_info.get('calibration_points_count', 0)}\n"
        info_text += f"GPS Reference Points: {transform_info.get('gps_reference_points_count', 0)}"
        
        print(info_text)
    
    async def _update_info_display(self):
        """정보 표시 업데이트"""
        try:
            status = self.kafka_processor.get_status()
            tag_mappings = self.kafka_processor.get_tag_mappings()
            
            info_text = f"Prims loaded: {len(self.prim_map)}\n"
            info_text += f"Tag mappings: {len(tag_mappings)}\n"
            info_text += f"Kafka connected: {'Yes' if status['consumer_connected'] else 'No'}\n"
            info_text += f"Is consuming: {'Yes' if status['is_consuming'] else 'No'}\n"
            
            transform_info = status.get('coordinate_transform_info', {})
            info_text += f"Coordinate mapping: {transform_info.get('mapping_name', 'None')}"
            
            if self._info_label:
                self._info_label.text = info_text
                
        except Exception as e:
            print(f"Error updating info display: {e}")
    
    def _update_status(self, status: str):
        """상태 레이블 업데이트"""
        if self._status_label:
            self._status_label.text = status
        print(f"Status: {status}")
    
    async def _on_position_update(self, object_name: str, tag_id: str, position: tuple, 
                                 uwb_coords: tuple, raw_timestamp: str):
        """위치 업데이트 콜백 - Omniverse 오브젝트 이동"""
        try:
            if object_name not in self.prim_map:
                print(f"Warning: Object '{object_name}' not found in stage")
                return
            
            prim = self.prim_map[object_name]
            xformAPI = UsdGeom.XformCommonAPI(prim)
            
            # 위치 설정
            omni_x, omni_y, omni_z = position
            xformAPI.SetTranslate(Gf.Vec3d(omni_x, omni_y, omni_z))
            
            print(f"Moved {object_name} (tag {tag_id}) to position {position}")
            
        except Exception as e:
            print(f"Error moving object {object_name}: {e}")