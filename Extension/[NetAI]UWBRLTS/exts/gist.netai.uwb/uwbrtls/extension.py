import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, Gf
import asyncio
from typing import Dict, Any

from .core.config_manager import get_config_manager
from .core.db_manager import get_db_manager
from .core.coordinate_transformer import get_coordinate_transformer
from .tracking.kafka_consumer import get_kafka_processor
from .publishing.publishing_manager import get_publishing_manager
from .ui.main_window import MainWindow

class NetAIUWBTrackingExtension(omni.ext.IExt):
    """NetAI UWB Tracking Extension with tab-based UI and Publishing functionality"""
    
    def __init__(self):
        super().__init__()
        
        # Core modules
        self.config_manager = get_config_manager()
        self.db_manager = get_db_manager()
        self.coordinate_transformer = get_coordinate_transformer()
        self.kafka_processor = get_kafka_processor()
        
        # Publishing manager (new)
        self.publishing_manager = get_publishing_manager()
        
        # UI components - only MainWindow needed
        self._main_window = None
        
        # Omniverse related
        self.prim_map = {}
        self._map_update_task = None
        
        print("NetAI UWB Tracking Extension initialized with Publishing functionality")
    
    def on_startup(self, ext_id):
        """Extension startup with UI initialization"""
        print(f"[gist.netai.uwb] startup - Extension ID: {ext_id}")
        
        # Initialize UI components
        self._initialize_ui()
        
        # Start initialization task
        asyncio.ensure_future(self._initialize_extension())
    
    def on_shutdown(self):
        """Extension shutdown with proper cleanup"""
        print("[gist.netai.uwb] Extension shutdown initiated")
        
        # Stop publishing
        if self.publishing_manager:
            asyncio.ensure_future(self.publishing_manager.stop_publishing())
        
        # Stop Kafka consumption
        if self.kafka_processor:
            asyncio.ensure_future(self.kafka_processor.stop_consuming())
        
        # Cancel periodic tasks
        if self._map_update_task:
            self._map_update_task.cancel()
        
        # Close database connections
        if self.db_manager:
            self.db_manager.close()
        
        # Cleanup UI
        self._cleanup_ui()
        
        print("NetAI UWB Tracking Extension shutdown completed")
    
    def _initialize_ui(self):
        """Initialize UI components - MainWindow with all callbacks"""
        # Create main window with all callbacks including publishing
        self._main_window = MainWindow(
            on_start_tracking=self._start_tracking,
            on_stop_tracking=self._stop_tracking,
            on_refresh_data=self._refresh_data,
            on_reload_mappings=self._reload_mappings,
            on_show_transform_info=self._show_transform_info,
            # Publishing callbacks (new)
            on_start_publishing=self._start_publishing,
            on_stop_publishing=self._stop_publishing,
            on_add_object=self._add_object_to_publish,
            on_remove_object=self._remove_object_from_publish,
            on_configure_publishing=self._configure_publishing
        )
    
    def _cleanup_ui(self):
        """Cleanup UI components"""
        if self._main_window:
            self._main_window.destroy()
            self._main_window = None
    
    async def _initialize_extension(self):
        """Initialize extension core functionality"""
        try:
            self._update_status("Initializing system...")
            
            # Load stage data
            await self._load_stage_data()
            
            # Initialize Kafka processor
            await self.kafka_processor.initialize()
            
            # Set message callback
            self.kafka_processor.set_message_callback(self._on_position_update)
            
            # Initialize publishing manager
            await self.publishing_manager.initialize()
            
            # Start periodic updates
            self._map_update_task = asyncio.create_task(self._periodic_updates())
            
            # Update UI information
            await self._update_info_display()
            
            self._update_status("Ready")
            print("Extension initialization completed successfully")
            
        except Exception as e:
            print(f"Error during extension initialization: {e}")
            self._update_status(f"Error: {e}")
    
    async def _load_stage_data(self):
        """Load Omniverse Stage data"""
        print("Loading Omniverse stage data...")
        
        stage = get_context().get_stage()
        
        if not stage:
            print("Warning: No stage found in context")
            return
        
        # Build prim map
        self.prim_map = {}
        prim_count = 0
        
        for prim in stage.Traverse():
            prim_path = str(prim.GetPath())
            prim_name = prim.GetName()
            
            self.prim_map[prim_path] = prim
            if prim_name:
                self.prim_map[prim_name] = prim
            
            prim_count += 1
        
        print(f"Loaded {prim_count} prims from existing stage")
    
    async def _periodic_updates(self):
        """Periodic data updates"""
        update_interval = self.config_manager.get('uwb.update_interval', 300)
        
        while True:
            try:
                await asyncio.sleep(update_interval)
                print("Performing periodic data update...")
                
                # Update tag mappings
                await self.kafka_processor.update_tag_mappings()
                
                # Update UI
                await self._update_info_display()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic update: {e}")
    
    # Tracking related methods
    async def _start_tracking(self):
        """Start UWB tracking"""
        try:
            self._update_status("Starting tracking...")
            await self.kafka_processor.start_consuming()
            self._update_status("Tracking active")
            
            # Update main window tracking status
            if self._main_window:
                self._main_window.update_tracking_status(True)
            
            print("UWB tracking started")
        except Exception as e:
            print(f"Error starting tracking: {e}")
            self._update_status(f"Error: {e}")
    
    async def _stop_tracking(self):
        """Stop UWB tracking"""
        try:
            self._update_status("Stopping tracking...")
            await self.kafka_processor.stop_consuming()
            self._update_status("Tracking stopped")
            
            # Update main window tracking status
            if self._main_window:
                self._main_window.update_tracking_status(False)
            
            print("UWB tracking stopped")
        except Exception as e:
            print(f"Error stopping tracking: {e}")
            self._update_status(f"Error: {e}")
    
    # Publishing related methods (실제 구현)
    async def _start_publishing(self):
        """Start position publishing"""
        try:
            self._update_status("Starting publishing...")
            success = await self.publishing_manager.start_publishing()
            
            if success:
                await self._update_publishing_display()
                await self._update_info_display()

                self._update_status("Publishing active")
                if self._main_window:
                    self._main_window.update_publishing_status(True)
                print("Position publishing started")
            else:
                self._update_status("Failed to start publishing")
                print("Failed to start publishing")
                
        except Exception as e:
            print(f"Error starting publishing: {e}")
            self._update_status(f"Publishing error: {e}")
    
    async def _stop_publishing(self):
        """Stop position publishing"""
        try:
            self._update_status("Stopping publishing...")
            await self.publishing_manager.stop_publishing()
            self._update_status("Publishing stopped")
            
            if self._main_window:
                self._main_window.update_publishing_status(False)
                
            print("Position publishing stopped")
        except Exception as e:
            print(f"Error stopping publishing: {e}")
            self._update_status(f"Error: {e}")
    async def _add_object_to_publish(self):
        """Add object to publishing list - Manual only"""
        print("Object addition disabled - please add objects manually via DB")
        return False

    async def _remove_object_from_publish(self):
        """Remove object from publishing list"""
        try:
            # 현재 발행 중인 오브젝트 목록 가져오기
            objects = self.publishing_manager.get_publishing_objects()
            
            if not objects:
                print("No objects to remove")
                return
            
            # 첫 번째 오브젝트 제거 (예시)
            first_object = objects[0]
            object_path = first_object['object_path']
            
            success = await self.publishing_manager.remove_object(object_path)
            
            if success:
                print(f"Removed object from publishing: {object_path}")
                await self._update_publishing_display()
            else:
                print(f"Failed to remove object: {object_path}")
                
        except Exception as e:
            print(f"Error removing object from publish: {e}")
    
    async def _configure_publishing(self, publish_rate: float):
        """Configure publishing settings"""
        try:
            # 모든 오브젝트의 발행 주기 업데이트
            objects = self.publishing_manager.get_publishing_objects()
            
            for obj in objects:
                object_path = obj['object_path']
                success = await self.publishing_manager.update_object_rate(object_path, publish_rate)
                if success:
                    print(f"Updated publish rate for {object_path}: {publish_rate} Hz")
            
            await self._update_publishing_display()
            
        except Exception as e:
            print(f"Error configuring publishing: {e}")
    
    # General methods
    async def _refresh_data(self):
        """Refresh all data"""
        try:
            self._update_status("Refreshing data...")
            
            # Reload stage data
            await self._load_stage_data()
            
            # Update tag mappings
            await self.kafka_processor.update_tag_mappings()
            
            # Reload coordinate mapping
            await self.kafka_processor.reload_coordinate_mapping()
            
            # Reload publishing objects
            await self.publishing_manager.reload_objects()
            
            # Update UI
            await self._update_info_display()
            await self._update_publishing_display()
            
            self._update_status("Data refreshed")
            print("Data refresh completed")
            
        except Exception as e:
            print(f"Error refreshing data: {e}")
            self._update_status(f"Error: {e}")
    
    async def _reload_mappings(self):
        """Reload coordinate mappings"""
        try:
            await self.kafka_processor.reload_coordinate_mapping()
            await self._update_info_display()
            print("Coordinate mappings reloaded")
        except Exception as e:
            print(f"Error reloading mappings: {e}")
    
    def _show_transform_info(self):
        """Show coordinate transform information"""
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
        """Update information display in UI"""
        try:
            status = self.kafka_processor.get_status()
            tag_mappings = self.kafka_processor.get_tag_mappings()
            
            info_text = f"Prims loaded: {len(self.prim_map)}\n"
            info_text += f"Tag mappings: {len(tag_mappings)}\n"
            info_text += f"Kafka connected: {'Yes' if status['consumer_connected'] else 'No'}\n"
            info_text += f"Is consuming: {'Yes' if status['is_consuming'] else 'No'}\n"
            
            transform_info = status.get('coordinate_transform_info', {})
            info_text += f"Coordinate mapping: {transform_info.get('mapping_name', 'None')}"
            
            # Update main window info
            if self._main_window:
                self._main_window.update_info(info_text)
            
            # Update main window tracking statistics
            if self._main_window:
                tracking_stats = {
                    "tag_count": len(tag_mappings),
                    "message_count": status.get('message_count', 0),
                    "last_update": status.get('last_update', 'Never')
                }
                self._main_window.update_tracking_statistics(tracking_stats)
                
        except Exception as e:
            print(f"Error updating info display: {e}")
    
    async def _update_publishing_display(self):
        """Update publishing display in UI - None 체크 강화"""
        try:
            if not self._main_window:
                return
            
            # Publishing 통계 가져오기 - None 체크 추가
            pub_stats = self.publishing_manager.get_statistics()
            if not pub_stats:
                print("Warning: Publishing stats is None")
                pub_stats = {}
            
            # 발행 중인 오브젝트 목록 가져오기 - None 체크 추가
            objects = self.publishing_manager.get_publishing_objects()
            if not objects:
                objects = []
            
            # 통계 업데이트 - 안전한 get() 사용
            publishing_stats = {
                "actual_rate": pub_stats.get('average_publish_rate', 0.0),
                "object_count": len(objects),
                "messages_sent": pub_stats.get('total_published', 0)
            }
            self._main_window.update_publishing_statistics(publishing_stats)
            
            # 오브젝트 목록 업데이트
            if objects:
                object_list = []
                for obj in objects[:5]:  # 최대 5개만 표시
                    object_path = obj.get('object_path', 'Unknown') if obj else 'Unknown'
                    virtual_tag_id = obj.get('virtual_tag_id', 'Unknown') if obj else 'Unknown'
                    object_list.append(f"{object_path} ({virtual_tag_id})")
                object_text = "\n".join(object_list)
                if len(objects) > 5:
                    object_text += f"\n... and {len(objects) - 5} more"
            else:
                object_text = "No objects selected"
            
            self._main_window.update_object_list(object_text)
            
            print(f"UI Updated: {len(objects)} objects, {pub_stats.get('total_published', 0)} messages sent")
            
        except Exception as e:
            print(f"Error updating publishing display: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_status(self, status: str):
        """Update status in UI"""
        if self._main_window:
            self._main_window.update_status(status)
        print(f"Status: {status}")
    
    async def _on_position_update(self, object_name: str, tag_id: str, position: tuple, 
                                 uwb_coords: tuple, raw_timestamp: str):
        """Position update callback for object movement"""
        try:
            # Find target prim
            target_prim = None
            
            if object_name in self.prim_map:
                target_prim = self.prim_map[object_name]
            elif object_name.split('/')[-1] in self.prim_map:
                obj_name = object_name.split('/')[-1]
                target_prim = self.prim_map[obj_name]
            
            if not target_prim:
                print(f"Warning: Object '{object_name}' not found in stage")
                return
            
            # Set position using XformCommonAPI
            xformAPI = UsdGeom.XformCommonAPI(target_prim)
            omni_x, omni_y, omni_z = position
            xformAPI.SetTranslate(Gf.Vec3d(omni_x, omni_y, omni_z))
            
            print(f"Moved {object_name} (tag {tag_id}) to ({omni_x:.2f}, {omni_y:.2f}, {omni_z:.2f})")
            
            # Update main window with latest activity
            if self._main_window:
                import datetime
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                tracking_stats = {
                    "last_update": current_time
                }
                self._main_window.update_tracking_statistics(tracking_stats)
            
        except Exception as e:
            print(f"Error moving object {object_name}: {e}")