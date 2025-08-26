import omni.ui as ui
import functools
from typing import Dict, Any, Callable
from .base_panel import CameraPanelBase

class KafkaStreamingPanel(CameraPanelBase):
    """Panel for Kafka streaming capture mode"""
    
    def __init__(self, camera_id: int, camera_path: str, container: ui.Widget, callbacks: Dict[str, Callable]):
        super().__init__(camera_id, camera_path, container)
        self.callbacks = callbacks
        self.broker_address = "localhost:9092"  # Default
        self.topic_name = f"camera_{camera_id}"  # Default topic
    
    def build_panel(self, broker: str = "localhost:9092", topic: str = None, 
                   resolution: list = None, interval: float = None, 
                   frame_count: int = None, **kwargs) -> Dict[str, Any]:
        """Build Kafka streaming panel UI"""
        self.broker_address = broker
        self.topic_name = topic if topic else f"camera_{self.camera_id}"
        
        # Create UI models
        self._ui_models = {
            "broker_model": ui.SimpleStringModel(self.broker_address),
            "topic_model": ui.SimpleStringModel(self.topic_name),
            "interval_model": ui.SimpleFloatModel(interval if interval else 1.0),
            "frame_count_model": ui.SimpleIntModel(frame_count if frame_count else 5),
            "resolution_x_model": ui.SimpleIntModel(resolution[0] if resolution else 1280),
            "resolution_y_model": ui.SimpleIntModel(resolution[1] if resolution and len(resolution) > 1 else 720)
        }
        
        # Build UI
        with self.container:
            frame_title = f"Camera {self.camera_id}: {self.camera_path} [KAFKA]"
            self._frame = ui.CollapsableFrame(frame_title, collapsed=False)
            self._ui_refs["frame"] = self._frame
            
            with self._frame:
                with ui.VStack(spacing=5, height=0):
                    self._build_status_section()
                    ui.Line(height=1, style={"color": 0xFF333333})
                    self._build_kafka_settings()
                    ui.Line(height=1, style={"color": 0xFF333333})
                    self._build_capture_settings()
                    ui.Line(height=2)
                    self._build_control_buttons()
        
        # Return combined references
        return self.get_all_refs()
    
    def _build_status_section(self):
        """Build status display section"""
        # Status labels
        self._ui_refs["status_label"] = ui.Label("Status: Ready", 
                                                 style={"color": 0xFF00FF00},
                                                 word_wrap=True)
        self._ui_refs["progress_label"] = ui.Label("", word_wrap=True)
        
        # Connection status
        with ui.HStack(height=25, spacing=5):
            ui.Label("Connection:", width=80)
            self._ui_refs["connection_label"] = ui.Label("Not Connected", 
                                                         style={"color": 0xFFFF9900})
    
    def _build_kafka_settings(self):
        """Build Kafka configuration section"""
        with ui.CollapsableFrame("Kafka Settings", collapsed=False):
            with ui.VStack(spacing=5):
                # Broker address
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Broker:", width=80, 
                            tooltip="Kafka broker address (host:port)")
                    ui.StringField(model=self._ui_models["broker_model"], 
                                 placeholder="localhost:9092")
                
                # Topic name
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Topic:", width=80,
                            tooltip="Kafka topic name for this camera")
                    ui.StringField(model=self._ui_models["topic_model"],
                                 placeholder=f"camera_{self.camera_id}")
                
                # Test connection button
                with ui.HStack(height=30, spacing=5):
                    ui.Spacer(width=80)
                    ui.Button("Test Connection", 
                             clicked_fn=self._test_kafka_connection,
                             tooltip="Test Kafka broker connection",
                             style={"background_color": 0xFF3498DB})
    
    def _build_capture_settings(self):
        """Build capture settings section"""
        with ui.CollapsableFrame("Capture Settings", collapsed=False):
            with ui.VStack(spacing=5):
                # Resolution
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Resolution:", width=80)
                    ui.IntField(model=self._ui_models["resolution_x_model"], width=60)
                    ui.Label("x", width=20)
                    ui.IntField(model=self._ui_models["resolution_y_model"], width=60)
                
                # Interval and frame count
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Interval (s):", width=80)
                    ui.FloatField(model=self._ui_models["interval_model"], width=60)
                    ui.Label("Frames:", width=60)
                    ui.IntField(model=self._ui_models["frame_count_model"], width=60)
                
                # Streaming options
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Format:", width=80)
                    self._ui_refs["format_combo"] = ui.ComboBox(0, "Raw", "JPEG", "PNG")
                    ui.Label("Quality:", width=60)
                    self._ui_refs["quality_slider"] = ui.IntSlider(min=1, max=100, 
                                                                   default_value=85)
    
    def _build_control_buttons(self):
        """Build control buttons"""
        with ui.VStack(spacing=5):
            # Capture controls
            with ui.HStack(spacing=5):
                ui.Button("Test Stream", 
                         clicked_fn=self._on_test_stream,
                         tooltip="Send single test frame to Kafka",
                         style={"background_color": 0xFF9B59B6})
                
                ui.Button("Start Streaming", 
                         clicked_fn=functools.partial(
                             self.callbacks.get("capture_periodic"), 
                             self.camera_path, self.camera_id
                         ),
                         tooltip="Start continuous streaming to Kafka",
                         style={"background_color": 0xFF27AE60})
            
            # Stop and remove controls
            with ui.HStack(spacing=5):
                ui.Button("Stop Stream", 
                         clicked_fn=functools.partial(
                             self.callbacks.get("stop_capture"), 
                             self.camera_path, self.camera_id
                         ),
                         tooltip="Stop Kafka streaming",
                         style={"background_color": 0xFFE67E22})
                
                ui.Button("Remove", 
                         clicked_fn=functools.partial(
                             self.callbacks.get("remove_camera"), 
                             self.camera_path, self.camera_id
                         ),
                         tooltip="Remove camera from management",
                         style={"color": 0xFFFF6666})
    
    def _test_kafka_connection(self):
        """Test Kafka broker connection"""
        broker = self._ui_models["broker_model"].get_value_as_string()
        self._ui_refs["connection_label"].text = "Testing..."
        self._ui_refs["connection_label"].style = {"color": 0xFFFFFF00}
        
        # TODO: Implement actual connection test with aiokafka
        # For now, just update status
        import asyncio
        
        async def mock_test():
            await asyncio.sleep(1)  # Simulate connection test
            self._ui_refs["connection_label"].text = "Mock Test - OK"
            self._ui_refs["connection_label"].style = {"color": 0xFF00FF00}
        
        asyncio.ensure_future(mock_test())
        print(f"[Info] Testing Kafka connection to: {broker}")
    
    def _on_test_stream(self):
        """Send single test frame"""
        if self.callbacks.get("capture_once"):
            self.update_status("Sending test frame...")
            self.callbacks["capture_once"](self.camera_path, self.camera_id)
    
    def get_capture_mode(self) -> str:
        """Return capture mode type"""
        return "KAFKA"
    
    def get_kafka_config(self) -> Dict[str, Any]:
        """Get current Kafka configuration"""
        return {
            "broker": self._ui_models["broker_model"].get_value_as_string(),
            "topic": self._ui_models["topic_model"].get_value_as_string(),
            "format": ["Raw", "JPEG", "PNG"][self._ui_refs["format_combo"].model.get_item_value_model().as_int],
            "quality": self._ui_refs["quality_slider"].model.as_int
        }
    
    def update_connection_status(self, connected: bool, message: str = ""):
        """Update Kafka connection status display"""
        if connected:
            self._ui_refs["connection_label"].text = f"Connected: {message}" if message else "Connected"
            self._ui_refs["connection_label"].style = {"color": 0xFF00FF00}
        else:
            self._ui_refs["connection_label"].text = f"Error: {message}" if message else "Not Connected"
            self._ui_refs["connection_label"].style = {"color": 0xFFFF0000}