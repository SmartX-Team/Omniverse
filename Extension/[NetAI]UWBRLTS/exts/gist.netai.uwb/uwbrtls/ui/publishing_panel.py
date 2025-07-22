import omni.ui as ui
import asyncio
from typing import Optional, Callable, Dict, Any, List

class PublishingPanel:
    """UI panel for publishing control (Omniverse to UWB)"""
    
    def __init__(self, 
                 on_start_publishing: Optional[Callable] = None,
                 on_stop_publishing: Optional[Callable] = None,
                 on_add_object: Optional[Callable] = None,
                 on_remove_object: Optional[Callable] = None,
                 on_configure_publishing: Optional[Callable] = None):
        
        self._on_start_publishing = on_start_publishing
        self._on_stop_publishing = on_stop_publishing
        self._on_add_object = on_add_object
        self._on_remove_object = on_remove_object
        self._on_configure_publishing = on_configure_publishing
        
        # UI elements
        self._publishing_status_label = None
        self._publish_rate_label = None
        self._object_count_label = None
        self._messages_sent_label = None
        self._start_button = None
        self._stop_button = None
        self._object_list_label = None  # Changed from TreeView to Label
        self._publish_rate_field = None
        
        self._is_publishing = False
        self._monitored_objects = []
    
    def create_panel(self, parent):
        """Create publishing control panel within parent container"""
        with parent:
            with ui.CollapsableFrame("Publishing Control (Omniverse → UWB)", 
                                   collapsed=False, height=300):
                with ui.VStack(spacing=8):
                    self._create_status_section()
                    self._create_configuration_section()
                    self._create_object_management_section()
                    self._create_control_section()
    
    def _create_status_section(self):
        """Create status display section"""
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
    
    def _create_configuration_section(self):
        """Create configuration section"""
        with ui.VStack(spacing=4):
            ui.Label("Configuration:", style={"font_weight": "bold"})
            
            with ui.HStack():
                ui.Label("Publish Rate (Hz): ", width=120)
                self._publish_rate_field = ui.FloatField(width=80)
                self._publish_rate_field.model.set_value(10.0)  # Default 10 Hz
                
                ui.Button("Apply", 
                         clicked_fn=self._handle_configure_publishing,
                         width=60, height=20)
    
    def _create_object_management_section(self):
        """Create object management section"""
        with ui.VStack(spacing=4):
            ui.Label("Monitored Objects:", style={"font_weight": "bold"})
            
            # Object list - using ScrollingFrame with Label instead of TreeView
            with ui.HStack():
                with ui.VStack():
                    with ui.ScrollingFrame(height=80):
                        self._object_list_label = ui.Label("No objects selected", 
                                                          style={"font_size": 12, "color": 0xFFAAAAAA})
                
                with ui.VStack(width=80, spacing=4):
                    ui.Button("Add Object", 
                             clicked_fn=self._handle_add_object,
                             height=25)
                    ui.Button("Remove", 
                             clicked_fn=self._handle_remove_object,
                             height=25)
    
    def _create_control_section(self):
        """Create control buttons section"""
        with ui.VStack(spacing=4):
            ui.Label("Controls:", style={"font_weight": "bold"})
            
            with ui.HStack(spacing=10):
                self._start_button = ui.Button("Start Publishing", 
                                              clicked_fn=self._handle_start_publishing,
                                              width=120, height=30)
                
                self._stop_button = ui.Button("Stop Publishing", 
                                             clicked_fn=self._handle_stop_publishing,
                                             width=120, height=30,
                                             enabled=False)
    
    def _handle_start_publishing(self):
        """Handle start publishing button"""
        if self._on_start_publishing:
            asyncio.ensure_future(self._on_start_publishing())
    
    def _handle_stop_publishing(self):
        """Handle stop publishing button"""
        if self._on_stop_publishing:
            asyncio.ensure_future(self._on_stop_publishing())
    
    def _handle_add_object(self):
        """Handle add object button"""
        if self._on_add_object:
            asyncio.ensure_future(self._on_add_object())
    
    def _handle_remove_object(self):
        """Handle remove object button"""
        if self._on_remove_object:
            # Get selected object from list
            asyncio.ensure_future(self._on_remove_object())
    
    def _handle_configure_publishing(self):
        """Handle configure publishing button"""
        if self._on_configure_publishing and self._publish_rate_field:
            publish_rate = self._publish_rate_field.model.get_value_as_float()
            asyncio.ensure_future(self._on_configure_publishing(publish_rate))
    
    def update_publishing_status(self, is_publishing: bool):
        """Update publishing status display"""
        self._is_publishing = is_publishing
        
        if self._publishing_status_label:
            if is_publishing:
                self._publishing_status_label.text = "Active"
                self._publishing_status_label.style = {"color": 0xFF66FF66}
            else:
                self._publishing_status_label.text = "Stopped"
                self._publishing_status_label.style = {"color": 0xFFFF6666}
        
        # Update button states
        if self._start_button:
            self._start_button.enabled = not is_publishing
        if self._stop_button:
            self._stop_button.enabled = is_publishing
    
    def update_statistics(self, stats: Dict[str, Any]):
        """Update statistics display"""
        if self._publish_rate_label and "actual_rate" in stats:
            self._publish_rate_label.text = f"{stats['actual_rate']:.1f} Hz"
        
        if self._object_count_label and "object_count" in stats:
            self._object_count_label.text = str(stats["object_count"])
        
        if self._messages_sent_label and "messages_sent" in stats:
            self._messages_sent_label.text = str(stats["messages_sent"])
    
    def update_object_list(self, objects: List[str]):
        """Update monitored objects list"""
        self._monitored_objects = objects.copy()
        
        # Update object list display
        if self._object_list_label:
            if objects:
                object_text = "\n".join(objects)
                self._object_list_label.text = object_text
            else:
                self._object_list_label.text = "No objects selected"
    
    def get_publish_rate(self) -> float:
        """Get current publish rate setting"""
        if self._publish_rate_field:
            return self._publish_rate_field.model.get_value_as_float()
        return 10.0  # Default rate
    
    def set_publish_rate(self, rate: float):
        """Set publish rate field value"""
        if self._publish_rate_field:
            self._publish_rate_field.model.set_value(rate)
    
    def set_error_state(self, error_message: str):
        """Set panel to error state"""
        if self._publishing_status_label:
            self._publishing_status_label.text = f"Error: {error_message}"
            self._publishing_status_label.style = {"color": 0xFFFFAA00}
        
        # Disable all buttons during error
        if self._start_button:
            self._start_button.enabled = False
        if self._stop_button:
            self._stop_button.enabled = False