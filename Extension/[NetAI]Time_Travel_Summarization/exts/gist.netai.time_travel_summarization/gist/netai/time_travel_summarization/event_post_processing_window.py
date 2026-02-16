# event_window.py - Event Processing Window

import omni.ui as ui
import carb
from pathlib import Path


class EventProcessingWindow:
    """Window for processing VLM event detection results."""
    
    def __init__(self, core, ext_id: str):
        self._core = core
        self._ext_id = ext_id
        self._window = None
        
        # UI state
        self._json_filename_model = ui.SimpleStringModel("video_18_20251113_232343.json")
        self._status_label = None
        self._process_button = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the event processing window UI."""
        self._window = ui.Window("Event Post Processing", width=400, height=300)
        
        with self._window.frame:
            with ui.VStack(spacing=10, style={"margin": 3}):
                # Title
                ui.Label("Event Post Processing", height=30, style={"font_size": 18, "font_weight": "bold"})
                
                ui.Spacer(height=5)
                
                # JSON File Input
                with ui.VStack(spacing=5):
                    ui.Label("Input JSON File:", height=20)
                    with ui.HStack(spacing=5):
                        ui.Label("vlm_outputs/", width=60,style={"font_size": 16} )
                        ui.StringField(model=self._json_filename_model, height=25)
                    ui.Label("(VLM output JSON file)", height=15, style={"color": 0xFF888888, "font_size": 16})
                
                ui.Spacer(height=5)

                # Process Button
                self._process_button = ui.Button("Process Events", height=40, clicked_fn=self._on_process_clicked)
                
                ui.Spacer(height=5)
                
                # Status Display
                with ui.VStack(spacing=5):
                    ui.Label("Status:", height=20, style={"font_weight": "bold","font_size": 16})
                    with ui.ScrollingFrame(height=50):
                        self._status_label = ui.Label(
                            "Ready to process events.",
                            word_wrap=True,
                            style={"color": 0xFFCCCCCC}
                        )
                
                ui.Spacer()
    
    def _on_process_clicked(self):
        """Handle process button click."""
        json_filename = self._json_filename_model.get_value_as_string()
        
        if not json_filename:
            self._update_status("Error: Please specify a JSON filename.", error=True)
            return
        
        # Construct full path
        base_dir = Path(__file__).parent
        json_path = base_dir / "vlm_outputs" / json_filename
        
        if not json_path.exists():
            self._update_status(f"Error: File not found: {json_path}", error=True)
            return
        
        self._update_status("Processing events...", processing=True)
        self._process_button.enabled = False
        
        try:
            # Call core to process events
            success = self._core.process_event_json(str(json_path))
            
            if success:
                self._update_status("Events processed successfully!\n" + 
                                  f"- JSONL saved\n" +
                                  f"- Position data extracted\n" +
                                  f"Check vlm_outputs/ folder for results.", 
                                  success=True)
            else:
                self._update_status("✗ Event processing failed. Check console for details.", error=True)
        
        except Exception as e:
            self._update_status(f"✗ Error: {str(e)}", error=True)
            carb.log_error(f"[EventWindow] Processing error: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
        
        finally:
            self._process_button.enabled = True
    
    def _update_status(self, message: str, error=False, success=False, processing=False):
        """Update status label with color coding."""
        if self._status_label:
            self._status_label.text = message
            
            if error:
                self._status_label.style = {"color": 0xFFFF4444}
            elif success:
                self._status_label.style = {"color": 0xFF44FF44}
            elif processing:
                self._status_label.style = {"color": 0xFFFFAA44}
            else:
                self._status_label.style = {"color": 0xFFCCCCCC}
    
    def destroy(self):
        """Clean up the window."""
        if self._window:
            self._window.destroy()
            self._window = None
    
    def show(self):
        """Show the window."""
        if self._window:
            self._window.visible = True
    
    def hide(self):
        """Hide the window."""
        if self._window:
            self._window.visible = False
