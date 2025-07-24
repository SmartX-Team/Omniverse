import omni.ui as ui
import asyncio
from typing import Optional, Callable

class MainWindow:
    """Main UI window for NetAI UWB Tracking Extension with tab layout"""
    
    def __init__(self, 
                 on_start_tracking: Optional[Callable] = None,
                 on_stop_tracking: Optional[Callable] = None,
                 on_refresh_data: Optional[Callable] = None,
                 on_reload_mappings: Optional[Callable] = None,
                 on_show_transform_info: Optional[Callable] = None,
                 # Publishing callbacks 추가
                 on_start_publishing: Optional[Callable] = None,
                 on_stop_publishing: Optional[Callable] = None,
                 on_add_object: Optional[Callable] = None,
                 on_remove_object: Optional[Callable] = None,
                 on_configure_publishing: Optional[Callable] = None):
        
        self._window = None
        self._status_label = None
        self._info_label = None
        self._tab_bar = None
        self._tab_content_frame = None
        
        # Callback functions
        self._on_start_tracking = on_start_tracking
        self._on_stop_tracking = on_stop_tracking
        self._on_refresh_data = on_refresh_data
        self._on_reload_mappings = on_reload_mappings
        self._on_show_transform_info = on_show_transform_info
        
        # Publishing callbacks
        self._on_start_publishing = on_start_publishing
        self._on_stop_publishing = on_stop_publishing
        self._on_add_object = on_add_object
        self._on_remove_object = on_remove_object
        self._on_configure_publishing = on_configure_publishing
        
        # Tab management
        self._tracking_panel = None
        self._publishing_panel = None
        self._current_tab = 0
        
        self._create_window()
    
    def _create_window(self):
        """Create main window with tab layout"""
        self._window = ui.Window("NetAI UWB Tracking", width=500, height=800)
        
        with self._window.frame:
            with ui.VStack(spacing=2):
                self._create_header()
                ui.Separator()
                self._create_global_status_section()
                ui.Separator()
                self._create_tab_layout()
                ui.Separator()
                self._create_global_controls()
    
    def _create_header(self):
        """Create header with title"""
        with ui.HStack(height=12):
            ui.Label("NetAI UWB Real-time Tracking System", 
                    style={"font_size": 18, "color": 0xFF00AAFF})
    
    def _create_global_status_section(self):
        """Create global status display section"""
        with ui.HStack(height=16):
            ui.Label("System Status: ", width=100)
            self._status_label = ui.Label("Initializing...", 
                                         style={"color": 0xFFFFAA00})
    
    def _create_tab_layout(self):
        """Create tab layout for different panels"""
        with ui.VStack():
            # Tab bar
            with ui.HStack(height=30):
                ui.Button("Tracking", 
                         clicked_fn=lambda: self._switch_tab(0),
                         width=100, height=25)
                ui.Button("Publishing", 
                         clicked_fn=lambda: self._switch_tab(1),
                         width=100, height=25)
                ui.Spacer()  # Push buttons to left
            
            # Tab content area
            self._tab_content_frame = ui.Frame()
            self._create_tab_content()
    
    def _create_tab_content(self):
        """Create content for current tab"""
        with self._tab_content_frame:
            if self._current_tab == 0:
                self._create_tracking_tab()
            elif self._current_tab == 1:
                self._create_publishing_tab()
    
    def _create_tracking_tab(self):
        """Create tracking tab content"""
        with ui.VStack(spacing=4, style={"margin_height": 0}):
            # Tracking Status
            with ui.VStack(spacing=2):
                ui.Label("Tracking Status:", style={"font_weight": "bold"})
                with ui.HStack():
                    ui.Label("Current Status: ", width=100)
                    self._tracking_status_label = ui.Label("Stopped", 
                                                          style={"color": 0xFFFF6666})
            
            ui.Separator()
            
            # Statistics
            with ui.VStack(spacing=4):
                ui.Label("Statistics:", style={"font_weight": "bold"})
                
                with ui.HStack():
                    ui.Label("Active Tags: ", width=100)
                    self._tag_count_label = ui.Label("0")
                
                with ui.HStack():
                    ui.Label("Messages: ", width=100)
                    self._message_count_label = ui.Label("0")
                
                with ui.HStack():
                    ui.Label("Last Update: ", width=100)
                    self._last_update_label = ui.Label("Never")
            
            ui.Separator()
            
            # Controls
            with ui.VStack(spacing=4):
                ui.Label("Controls:", style={"font_weight": "bold"})
                
                with ui.HStack(spacing=10):
                    ui.Button("Start Tracking", 
                             clicked_fn=self._handle_start_tracking,
                             width=120, height=30)
                    
                    ui.Button("Stop Tracking", 
                             clicked_fn=self._handle_stop_tracking,
                             width=120, height=30)
                    
                    ui.Button("Update Mappings", 
                             clicked_fn=self._handle_update_mappings,
                             width=120, height=30)
    
    def _create_publishing_tab(self):
        """Create publishing tab content"""
        with ui.VStack(spacing=8):
            # Publishing Status
            with ui.VStack(spacing=4):
                ui.Label("Publishing Status:", style={"font_weight": "bold"})
                
                with ui.HStack():
                    ui.Label("Current Status: ", width=100)
                    self._publishing_status_label = ui.Label("Stopped", 
                                                            style={"color": 0xFFFF6666})
                
                with ui.HStack():
                    ui.Label("Publish Rate: ", width=100)
                    self._publish_rate_label = ui.Label("0 Hz")
                
                with ui.HStack():
                    ui.Label("Objects: ", width=100)
                    self._object_count_label = ui.Label("0")
                
                with ui.HStack():
                    ui.Label("Messages Sent: ", width=100)
                    self._messages_sent_label = ui.Label("0")
            
            ui.Separator()
            
            # Configuration
            with ui.VStack(spacing=4):
                ui.Label("Configuration:", style={"font_weight": "bold"})
                
                with ui.HStack():
                    ui.Label("Publish Rate (Hz): ", width=120)
                    self._publish_rate_field = ui.FloatField(width=80)
                    self._publish_rate_field.model.set_value(10.0)
                    
                    ui.Button("Apply", 
                             clicked_fn=self._handle_configure_publishing,
                             width=60, height=20)
            
            ui.Separator()
            
            # Object Management
            with ui.VStack(spacing=4):
                ui.Label("Monitored Objects:", style={"font_weight": "bold"})
                
                with ui.HStack():
                    with ui.VStack():
                        with ui.ScrollingFrame(height=100):
                            self._object_list_label = ui.Label("No objects selected", 
                                                              style={"color": 0xFFAAAAAA, "font_size": 12})
                    
                    with ui.VStack(width=80, spacing=4):
                        ui.Button("Add Object", 
                                 clicked_fn=self._handle_add_object,
                                 height=25)
                        ui.Button("Remove", 
                                 clicked_fn=self._handle_remove_object,
                                 height=25)
            
            ui.Separator()
            
            # Controls
            with ui.VStack(spacing=4):
                ui.Label("Controls:", style={"font_weight": "bold"})
                
                with ui.HStack(spacing=10):
                    self._start_publishing_button = ui.Button("Start Publishing", 
                                                            clicked_fn=self._handle_start_publishing,
                                                            width=120, height=30)
                    
                    self._stop_publishing_button = ui.Button("Stop Publishing", 
                                                           clicked_fn=self._handle_stop_publishing,
                                                           width=120, height=30,
                                                           enabled=False)
    
    def _create_global_controls(self):
        """Create global control buttons"""
        with ui.VStack(spacing=4):
            ui.Label("Global Controls:", style={"font_weight": "bold"})
            
            with ui.HStack(spacing=10):
                ui.Button("Refresh All Data", 
                         clicked_fn=self._handle_refresh_data,
                         width=120, height=30)
                
                ui.Button("Reload Mappings", 
                         clicked_fn=self._handle_reload_mappings,
                         width=120, height=30)
                
                ui.Button("Transform Info", 
                         clicked_fn=self._handle_show_transform_info,
                         width=120, height=30)
            
            # System Information
            with ui.VStack(spacing=4):
                ui.Label("System Information:", style={"font_size": 12})
                self._info_label = ui.Label("Loading...", 
                                          style={"font_size": 10, "color": 0xFFAAAAAA})
    
    def _switch_tab(self, tab_index: int):
        """Switch to specified tab"""
        self._current_tab = tab_index
        
        # Clear all tab-specific UI element references
        self._clear_tab_ui_references()
        
        # Clear and recreate tab content
        self._tab_content_frame.clear()
        self._create_tab_content()
    
    def _clear_tab_ui_references(self):
        """Clear all tab-specific UI element references to prevent overlap"""
        # Clear tracking tab references
        if hasattr(self, '_tracking_status_label'):
            self._tracking_status_label = None
        if hasattr(self, '_tag_count_label'):
            self._tag_count_label = None
        if hasattr(self, '_message_count_label'):
            self._message_count_label = None
        if hasattr(self, '_last_update_label'):
            self._last_update_label = None
            
        # Clear publishing tab references
        if hasattr(self, '_publishing_status_label'):
            self._publishing_status_label = None
        if hasattr(self, '_publish_rate_label'):
            self._publish_rate_label = None
        if hasattr(self, '_object_count_label'):
            self._object_count_label = None
        if hasattr(self, '_messages_sent_label'):
            self._messages_sent_label = None
        if hasattr(self, '_publish_rate_field'):
            self._publish_rate_field = None
        if hasattr(self, '_object_list_label'):
            self._object_list_label = None
        if hasattr(self, '_start_publishing_button'):
            self._start_publishing_button = None
        if hasattr(self, '_stop_publishing_button'):
            self._stop_publishing_button = None
    
    # Tab-specific handlers for tracking
    def _handle_start_tracking(self):
        """Handle start tracking button click"""
        if self._on_start_tracking:
            asyncio.ensure_future(self._on_start_tracking())
    
    def _handle_stop_tracking(self):
        """Handle stop tracking button click"""
        if self._on_stop_tracking:
            asyncio.ensure_future(self._on_stop_tracking())
    
    def _handle_update_mappings(self):
        """Handle update mappings button click"""
        if self._on_reload_mappings:
            asyncio.ensure_future(self._on_reload_mappings())
    
    # Tab-specific handlers for publishing (실제 콜백 연결)
    def _handle_start_publishing(self):
        """Handle start publishing button click"""
        if self._on_start_publishing:
            asyncio.ensure_future(self._on_start_publishing())
        else:
            print("Start publishing callback not set")
    
    def _handle_stop_publishing(self):
        """Handle stop publishing button click"""
        if self._on_stop_publishing:
            asyncio.ensure_future(self._on_stop_publishing())
        else:
            print("Stop publishing callback not set")
    
    def _handle_add_object(self):
        """Handle add object button click"""
        if self._on_add_object:
            asyncio.ensure_future(self._on_add_object())
        else:
            print("Add object callback not set")
    
    def _handle_remove_object(self):
        """Handle remove object button click"""
        if self._on_remove_object:
            asyncio.ensure_future(self._on_remove_object())
        else:
            print("Remove object callback not set")
    
    def _handle_configure_publishing(self):
        """Handle configure publishing button click"""
        if self._on_configure_publishing and hasattr(self, '_publish_rate_field') and self._publish_rate_field:
            rate = self._publish_rate_field.model.get_value_as_float()
            asyncio.ensure_future(self._on_configure_publishing(rate))
        else:
            print("Configure publishing callback not set or field not available")
    
    # Global handlers
    def _handle_refresh_data(self):
        """Handle refresh data button click"""
        if self._on_refresh_data:
            asyncio.ensure_future(self._on_refresh_data())
    
    def _handle_reload_mappings(self):
        """Handle reload mappings button click"""
        if self._on_reload_mappings:
            asyncio.ensure_future(self._on_reload_mappings())
    
    def _handle_show_transform_info(self):
        """Handle show transform info button click"""
        if self._on_show_transform_info:
            self._on_show_transform_info()
    
    # Update methods
    def update_status(self, status: str):
        """Update status label text"""
        if self._status_label:
            self._status_label.text = status
    
    def update_info(self, info_text: str):
        """Update information label text"""
        if self._info_label:
            self._info_label.text = info_text
    
    def update_tracking_status(self, is_tracking: bool):
        """Update tracking status in tracking tab"""
        if hasattr(self, '_tracking_status_label') and self._tracking_status_label:
            if is_tracking:
                self._tracking_status_label.text = "Active"
                self._tracking_status_label.style = {"color": 0xFF66FF66}
            else:
                self._tracking_status_label.text = "Stopped"
                self._tracking_status_label.style = {"color": 0xFFFF6666}
    
    def update_tracking_statistics(self, stats: dict):
        """Update tracking statistics"""
        if hasattr(self, '_tag_count_label') and self._tag_count_label and "tag_count" in stats:
            self._tag_count_label.text = str(stats["tag_count"])
        
        if hasattr(self, '_message_count_label') and self._message_count_label and "message_count" in stats:
            self._message_count_label.text = str(stats["message_count"])
        
        if hasattr(self, '_last_update_label') and self._last_update_label and "last_update" in stats:
            self._last_update_label.text = str(stats["last_update"])
    
    def update_publishing_status(self, is_publishing: bool):
        """Update publishing status in publishing tab"""
        if hasattr(self, '_publishing_status_label') and self._publishing_status_label:
            if is_publishing:
                self._publishing_status_label.text = "Active"
                self._publishing_status_label.style = {"color": 0xFF66FF66}
            else:
                self._publishing_status_label.text = "Stopped"
                self._publishing_status_label.style = {"color": 0xFFFF6666}
        
        # Update button states
        if hasattr(self, '_start_publishing_button') and self._start_publishing_button:
            self._start_publishing_button.enabled = not is_publishing
        if hasattr(self, '_stop_publishing_button') and self._stop_publishing_button:
            self._stop_publishing_button.enabled = is_publishing
    
    def update_publishing_statistics(self, stats: dict):
        """Update publishing statistics"""
        if hasattr(self, '_publish_rate_label') and self._publish_rate_label and "actual_rate" in stats:
            self._publish_rate_label.text = f"{stats['actual_rate']:.1f} Hz"
        
        if hasattr(self, '_object_count_label') and self._object_count_label and "object_count" in stats:
            self._object_count_label.text = str(stats["object_count"])
        
        if hasattr(self, '_messages_sent_label') and self._messages_sent_label and "messages_sent" in stats:
            self._messages_sent_label.text = str(stats["messages_sent"])
    
    def update_object_list(self, object_text: str):
        """Update monitored objects list display"""
        if hasattr(self, '_object_list_label') and self._object_list_label:
            self._object_list_label.text = object_text
    
    def destroy(self):
        """Destroy window and cleanup"""
        if self._window:
            self._window.destroy()
            self._window = None
    
    @property
    def window(self):
        """Get window reference"""
        return self._window