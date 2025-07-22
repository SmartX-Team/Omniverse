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
from .ui.main_window import MainWindow

class NetAIUWBTrackingExtension(omni.ext.IExt):
    """NetAI UWB Tracking Extension with tab-based UI"""
    
    def __init__(self):
        super().__init__()
        
        # Core modules
        self.config_manager = get_config_manager()
        self.db_manager = get_db_manager()
        self.coordinate_transformer = get_coordinate_transformer()
        self.kafka_processor = get_kafka_processor()
        
        # UI components - only MainWindow needed
        self._main_window = None
        
        # Omniverse related
        self.prim_map = {}
        self._map_update_task = None
        
        # Publishing related (placeholder for future implementation)
        self._publishing_manager = None
        self._is_publishing = False
        
        print("NetAI UWB Tracking Extension initialized with tab-based UI")
    
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
        """Initialize UI components - only MainWindow with tabs"""
        # Create main window with callbacks - it contains everything
        self._main_window = MainWindow(
            on_start_tracking=self._start_tracking,
            on_stop_tracking=self._stop_tracking,
            on_refresh_data=self._refresh_data,
            on_reload_mappings=self._reload_mappings,
            on_show_transform_info=self._show_transform_info
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
    
    async def _update_tracking_mappings(self):
        """Update tracking mappings"""
        try:
            await self.kafka_processor.update_tag_mappings()
            print("Tracking mappings updated")
        except Exception as e:
            print(f"Error updating tracking mappings: {e}")
    
    # Publishing related methods (placeholders for future implementation)
    async def _start_publishing(self):
        """Start position publishing - placeholder"""
        print("Start publishing - not implemented yet")
        
        if self._main_window:
            self._main_window.update_publishing_status(False)
    
    async def _stop_publishing(self):
        """Stop position publishing - placeholder"""
        print("Stop publishing - not implemented yet")
        
        if self._main_window:
            self._main_window.update_publishing_status(False)
        
    async def _add_object_to_publish(self):
        """Add object to publishing list - placeholder"""
        print("Add object to publish - not implemented yet")
        
    async def _remove_object_from_publish(self):
        """Remove object from publishing list - placeholder"""
        print("Remove object from publish - not implemented yet")
        
    async def _configure_publishing(self, publish_rate: float):
        """Configure publishing settings - placeholder"""
        print(f"Configure publishing rate: {publish_rate} Hz - not implemented yet")
    
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
            
            # Update UI
            await self._update_info_display()
            
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
            
            # Update main window publishing statistics
            if self._main_window:
                publishing_stats = {
                    "actual_rate": 0.0,
                    "object_count": 0,
                    "messages_sent": 0
                }
                self._main_window.update_publishing_statistics(publishing_stats)
                
        except Exception as e:
            print(f"Error updating info display: {e}")
    
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