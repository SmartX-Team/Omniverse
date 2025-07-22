import omni.ui as ui
import asyncio
from typing import Optional, Callable, Dict, Any

class TrackingPanel:
    """UI panel for tracking control (UWB to Omniverse)"""
    
    def __init__(self, 
                 on_start_tracking: Optional[Callable] = None,
                 on_stop_tracking: Optional[Callable] = None,
                 on_update_mappings: Optional[Callable] = None):
        
        self._on_start_tracking = on_start_tracking
        self._on_stop_tracking = on_stop_tracking
        self._on_update_mappings = on_update_mappings
        
        # UI elements
        self._tracking_status_label = None
        self._tag_count_label = None
        self._message_count_label = None
        self._last_update_label = None
        self._start_button = None
        self._stop_button = None
        
        self._is_tracking = False
    
    def create_panel(self, parent):
        """Create tracking control panel within parent container"""
        with parent:
            with ui.CollapsableFrame("Tracking Control (UWB → Omniverse)", 
                                   collapsed=False, height=200):
                with ui.VStack(spacing=8):
                    self._create_status_section()
                    self._create_statistics_section()
                    self._create_control_section()
    
    def _create_status_section(self):
        """Create status display section"""
        with ui.VStack(spacing=4):
            ui.Label("Tracking Status:", style={"font_weight": "bold"})
            with ui.HStack():
                ui.Label("Current Status: ", width=100)
                self._tracking_status_label = ui.Label("Stopped", 
                                                      style={"color": 0xFFFF6666})
    
    def _create_statistics_section(self):
        """Create statistics display section"""
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
    
    def _create_control_section(self):
        """Create control buttons section"""
        with ui.VStack(spacing=4):
            ui.Label("Controls:", style={"font_weight": "bold"})
            
            with ui.HStack(spacing=10):
                self._start_button = ui.Button("Start Tracking", 
                                              clicked_fn=self._handle_start_tracking,
                                              width=120, height=30)
                
                self._stop_button = ui.Button("Stop Tracking", 
                                             clicked_fn=self._handle_stop_tracking,
                                             width=120, height=30,
                                             enabled=False)
                
                ui.Button("Update Mappings", 
                         clicked_fn=self._handle_update_mappings,
                         width=120, height=30)
    
    def _handle_start_tracking(self):
        """Handle start tracking button"""
        if self._on_start_tracking:
            asyncio.ensure_future(self._on_start_tracking())
    
    def _handle_stop_tracking(self):
        """Handle stop tracking button"""
        if self._on_stop_tracking:
            asyncio.ensure_future(self._on_stop_tracking())
    
    def _handle_update_mappings(self):
        """Handle update mappings button"""
        if self._on_update_mappings:
            asyncio.ensure_future(self._on_update_mappings())
    
    def update_tracking_status(self, is_tracking: bool):
        """Update tracking status display"""
        self._is_tracking = is_tracking
        
        if self._tracking_status_label:
            if is_tracking:
                self._tracking_status_label.text = "Active"
                self._tracking_status_label.style = {"color": 0xFF66FF66}
            else:
                self._tracking_status_label.text = "Stopped"
                self._tracking_status_label.style = {"color": 0xFFFF6666}
        
        # Update button states
        if self._start_button:
            self._start_button.enabled = not is_tracking
        if self._stop_button:
            self._stop_button.enabled = is_tracking
    
    def update_statistics(self, stats: Dict[str, Any]):
        """Update statistics display"""
        if self._tag_count_label and "tag_count" in stats:
            self._tag_count_label.text = str(stats["tag_count"])
        
        if self._message_count_label and "message_count" in stats:
            self._message_count_label.text = str(stats["message_count"])
        
        if self._last_update_label and "last_update" in stats:
            self._last_update_label.text = str(stats["last_update"])
    
    def set_error_state(self, error_message: str):
        """Set panel to error state"""
        if self._tracking_status_label:
            self._tracking_status_label.text = f"Error: {error_message}"
            self._tracking_status_label.style = {"color": 0xFFFFAA00}
        
        # Disable all buttons during error
        if self._start_button:
            self._start_button.enabled = False
        if self._stop_button:
            self._stop_button.enabled = False