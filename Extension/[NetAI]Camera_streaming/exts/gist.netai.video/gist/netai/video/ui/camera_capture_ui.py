# ui/camera_capture_ui.py
import omni.ui as ui
import asyncio
from typing import Dict, Callable, Optional
from .panels.local_storage_panel import LocalStoragePanel
from .panels.kafka_streaming_panel import KafkaStreamingPanel
from .panels.base_panel import CameraPanelBase

# Import CaptureMode from models
from ..models.capture_mode import CaptureMode

class CameraCaptureUI:
    """Manages the UI for Camera Capture Extension with panel abstraction"""
    
    def __init__(self, 
                 default_camera_path: str,
                 default_output_dir: str,
                 callbacks: Dict[str, Callable]):
        self._window = None
        self._callbacks = callbacks
        self._camera_ui_container = None
        self._camera_panels = {}  # Store panel objects
        
        # Models for input fields
        self._camera_path_model = ui.SimpleStringModel(default_camera_path)
        self._output_dir_model = ui.SimpleStringModel(default_output_dir)
        
        # Kafka specific models
        self._kafka_broker_model = ui.SimpleStringModel("localhost:9092")
        self._kafka_topic_model = ui.SimpleStringModel("")
        
        self._build_window()
    
    def _build_window(self):
        """Build the main UI window"""
        self._window = ui.Window("Camera Capture Controller", width=800, height=600)
        
        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                self._build_header()
                self._build_input_section()
                ui.Line()
                self._build_camera_list_section()
                ui.Line()
                self._build_global_controls()
    
    def _build_header(self):
        """Build header section"""
        ui.Label("Off-screen Camera Capture System", 
                style={"font_size": 16, "font_weight": "bold"})
        ui.Line()
    
    def _build_input_section(self):
        """Build input section for adding cameras with capture mode selection"""
        with ui.VStack(spacing=5):
            # Preset loading section
            with ui.CollapsableFrame("Preset Configuration", collapsed=True):
                with ui.VStack(spacing=5):
                    # Preset file path input
                    with ui.HStack(height=30, spacing=5):
                        ui.Label("Preset File:", width=100)
                        self._preset_path_model = ui.SimpleStringModel("")
                        ui.StringField(model=self._preset_path_model, width=ui.Percent(60))
                        ui.Button("Browse", 
                                clicked_fn=self._on_browse_preset,
                                width=80)
                    
                    # Load/Save preset buttons
                    with ui.HStack(height=30, spacing=5):
                        ui.Button("Load Preset", 
                                clicked_fn=self._on_load_preset,
                                height=30,
                                style={"background_color": 0xFF27AE60})
                        ui.Button("Save Preset",
                                clicked_fn=self._on_save_preset,
                                height=30,
                                style={"background_color": 0xFF2980B9})
            
            ui.Separator(height=10)
            
            # Manual camera add section - 올바른 들여쓰기로 수정
            with ui.CollapsableFrame("Manual Camera Add", collapsed=False):
                with ui.VStack(spacing=5):
                    # Camera path input
                    with ui.HStack(height=30, spacing=5):
                        ui.Label("Camera Path:", width=100)
                        ui.StringField(model=self._camera_path_model, width=ui.Percent(70))
                    
                    ui.Separator(height=5)
                    
                    # Local Storage section
                    ui.Label("Local Storage Mode:", style={"color": 0xFF4A90E2, "font_weight": "bold"})
                    with ui.HStack(height=30, spacing=5):
                        ui.Label("Output Dir:", width=100)
                        ui.StringField(model=self._output_dir_model, width=ui.Percent(70))
                    
                    # Add Local button
                    ui.Button("Add Camera (Local)", 
                            clicked_fn=self._on_add_local_camera,
                            height=30,
                            style={"background_color": 0xFF4A90E2})
                    
                    ui.Separator(height=10)
                    
                    # Kafka Streaming section
                    ui.Label("Kafka Streaming Mode:", style={"color": 0xFF9B59B6, "font_weight": "bold"})
                    
                    with ui.HStack(height=30, spacing=5):
                        ui.Label("Kafka Broker:", width=100,
                                tooltip="Format: host:port")
                        ui.StringField(model=self._kafka_broker_model, 
                                     placeholder="localhost:9092")
                    
                    with ui.HStack(height=30, spacing=5):
                        ui.Label("Topic (optional):", width=100,
                                tooltip="Leave empty to auto-generate")
                        ui.StringField(model=self._kafka_topic_model,
                                     placeholder="auto-generate")
                    
                    # Add Kafka button
                    ui.Button("Add Camera (Kafka)", 
                            clicked_fn=self._on_add_kafka_camera,
                            height=30,
                            style={"background_color": 0xFF9B59B6})
    
    def _build_camera_list_section(self):
        """Build camera list section"""
        ui.Label("Managed Cameras:", style={"font_size": 14})
        with ui.ScrollingFrame(
            height=ui.Pixel(400),
            horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
            vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON
        ):
            self._camera_ui_container = ui.VStack(spacing=8)
    
    def _build_global_controls(self):
        """Build global control buttons"""
        with ui.HStack(spacing=5):
            ui.Button("Stop All Captures", 
                     clicked_fn=self._callbacks.get("stop_all"),
                     style={"background_color": 0xFFE74C3C})
            ui.Button("Clear All", 
                     clicked_fn=self._callbacks.get("clear_all"),
                     style={"background_color": 0xFF95A5A6})
    
    def _on_add_local_camera(self):
        """Handle add camera button click for LOCAL mode"""
        camera_path = self._camera_path_model.get_value_as_string().strip()
        output_dir = self._output_dir_model.get_value_as_string().strip()
        capture_mode = "LOCAL"
        
        print(f"[DEBUG] Add Local Camera:")
        print(f"  - Camera Path: {camera_path}")
        print(f"  - Output Dir: {output_dir}")
        
        if self._callbacks.get("add_camera"):
            self._callbacks["add_camera"](camera_path, output_dir, capture_mode)
    
    def _on_add_kafka_camera(self):
        """Handle add camera button click for KAFKA mode"""
        camera_path = self._camera_path_model.get_value_as_string().strip()
        broker = self._kafka_broker_model.get_value_as_string().strip()
        topic = self._kafka_topic_model.get_value_as_string().strip()
        kafka_config = f"{broker}|{topic}" if topic else broker
        capture_mode = "KAFKA"
        
        print(f"[DEBUG] Add Kafka Camera:")
        print(f"  - Camera Path: {camera_path}")
        print(f"  - Broker: {broker}")
        print(f"  - Topic: {topic if topic else 'auto-generate'}")
        print(f"  - Config: {kafka_config}")
        
        if self._callbacks.get("add_camera"):
            self._callbacks["add_camera"](camera_path, kafka_config, capture_mode)
    
    def add_camera_panel(self, camera_id: int, camera_path: str, output_or_config: str, 
                        capture_mode: str = "LOCAL") -> Optional[Dict]:
        """Add a camera panel based on capture mode"""
        print(f"[DEBUG] add_camera_panel called:")
        print(f"  - Camera ID: {camera_id}")
        print(f"  - Camera Path: {camera_path}")
        print(f"  - Config: {output_or_config}")
        print(f"  - Capture Mode: {capture_mode}")
        
        if not self._camera_ui_container:
            print("[ERROR] Camera UI container not initialized.")
            return None
        
        # Create appropriate panel based on mode
        panel = None
        if capture_mode == "LOCAL":
            print("[DEBUG] Creating LocalStoragePanel")
            panel = LocalStoragePanel(camera_id, camera_path, self._camera_ui_container, self._callbacks)
            ui_refs = panel.build_panel(output_dir=output_or_config)
            
        elif capture_mode == "KAFKA":
            print("[DEBUG] Creating KafkaStreamingPanel")
            panel = KafkaStreamingPanel(camera_id, camera_path, self._camera_ui_container, self._callbacks)
            # Parse Kafka config
            if "|" in output_or_config:
                broker, topic = output_or_config.split("|", 1)
            else:
                broker = output_or_config
                topic = f"camera_{camera_id}"
            print(f"[DEBUG] Kafka panel params - Broker: {broker}, Topic: {topic}")
            ui_refs = panel.build_panel(broker=broker, topic=topic)
            
        else:
            print(f"[ERROR] Unknown capture mode: {capture_mode}")
            return None
        
        # Store panel object
        self._camera_panels[camera_path] = panel
        print(f"[DEBUG] Panel created and stored. Total panels: {len(self._camera_panels)}")
        
        return ui_refs
    
    def _on_browse_preset(self):
        """Open file browser for preset selection"""
        import os
        default_preset = os.path.expanduser("~/Documents/camera_preset.json")
        self._preset_path_model.set_value(default_preset)
        print(f"[Info] Set preset path to: {default_preset}")
    
    def _on_load_preset(self):
        """Load cameras from preset file"""
        preset_path = self._preset_path_model.get_value_as_string().strip()
        if not preset_path:
            print("[Warning] Please specify a preset file path")
            return
        
        if self._callbacks.get("load_preset"):
            self._callbacks["load_preset"](preset_path)
    
    def _on_save_preset(self):
        """Save current cameras to preset file"""
        preset_path = self._preset_path_model.get_value_as_string().strip()
        if not preset_path:
            print("[Warning] Please specify a preset file path")
            return
        
        if self._callbacks.get("save_preset"):
            self._callbacks["save_preset"](preset_path)
    
    def remove_camera_panel(self, camera_path: str):
        """Remove camera panel with proper cleanup"""
        if camera_path not in self._camera_panels:
            print(f"[Warning] Camera panel not found for path: {camera_path}")
            return
        
        panel = self._camera_panels[camera_path]
        
        # Hide immediately
        panel.hide()
        
        # Deferred destroy
        async def cleanup():
            await asyncio.sleep(0.1)
            if not panel.is_destroyed():
                panel.destroy()
        
        # Remove from dictionary
        del self._camera_panels[camera_path]
        print(f"[Info] Camera panel removed: {camera_path}")
        
        # Schedule cleanup
        asyncio.ensure_future(cleanup())
    
    def update_status(self, camera_path: str, status: str):
        """Update status for a camera panel"""
        if camera_path in self._camera_panels:
            self._camera_panels[camera_path].update_status(status)
    
    def update_progress(self, camera_path: str, progress: str):
        """Update progress for a camera panel"""
        if camera_path in self._camera_panels:
            self._camera_panels[camera_path].update_progress(progress)
    
    def get_panel(self, camera_path: str) -> Optional[CameraPanelBase]:
        """Get panel object for a camera"""
        return self._camera_panels.get(camera_path)
    
    def destroy(self):
        """Clean up UI"""
        # Destroy all panels
        for panel in self._camera_panels.values():
            if not panel.is_destroyed():
                panel.destroy()
        
        if self._window:
            self._window.destroy()
        
        self._window = None
        self._camera_ui_container = None
        self._camera_panels.clear()