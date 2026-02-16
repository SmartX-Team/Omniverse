# vlm_client_window.py - UI for VLM Client

import omni.ui as ui
import carb
import threading


class VLMClientWindow:
    """VLM Client UI Window."""
    
    def __init__(self, vlm_core, ext_id):
        """Initialize VLM Client window."""
        self._vlm_core = vlm_core
        self._ext_id = ext_id
        
        # Create window
        self._window = ui.Window("VLM Client", width=450, height=285)
        
        with self._window.frame:
            with ui.VStack(spacing=5, style={"margin": 3}):
                # Title
                ui.Label("VLM Video Analysis Client", style={"font_size": 20, "font_weight": "bold"})
                
                # Video input section
                with ui.HStack(height=22, spacing=5):
                    ui.Label("Video:", width=50, style={"font_size": 16, "font_weight": "bold"})
                    ui.Label("video/", width=45)
                    self._video_filename_field = ui.StringField()
                    self._video_filename_field.model.set_value("video_19.mp4")
                
                # Video ID display
                with ui.HStack(height=20, spacing=5):
                    ui.Label("Video ID:", width=60, style={"font_size": 15})
                    self._video_id_label = ui.Label("Not uploaded", style={"color": 0xFF888888, "font_size": 15})
                
                # Action buttons
                with ui.HStack(height=28, spacing=8):
                    self._upload_button = ui.Button("Upload", width=0)
                    self._upload_button.set_clicked_fn(self._on_upload_clicked)
                    
                    self._delete_button = ui.Button("Delete", width=0)
                    self._delete_button.set_clicked_fn(self._on_delete_clicked)
                    self._delete_button.enabled = False
                    
                    self._generate_button = ui.Button("Generate", width=0)
                    self._generate_button.set_clicked_fn(self._on_generate_clicked)
                    self._generate_button.enabled = False
                
                # Separator
                with ui.HStack(height=1):
                    ui.Line(style={"color": 0xFF666666})
                
                # Model and preset selection
                ui.Label("Settings:", style={"font_size": 16, "font_weight": "bold"})
                
                with ui.HStack(height=22, spacing=5):
                    ui.Label("Model:", width=50)
                    self._model_combo = ui.ComboBox(1, "gpt-4o", "Qwen3-VL-8B-Instruct", "cosmos-reason1", "vila-1.5", "nvila")
                
                with ui.HStack(height=22, spacing=5):
                    ui.Label("Preset:", width=50)
                    self._preset_combo = ui.ComboBox(0, "simple_view", "twin_view")
                
                with ui.HStack(height=22, spacing=5):
                    ui.Label("Overlap:", width=50)
                    self._overlap_field = ui.IntField()
                    self._overlap_field.model.set_value(0)
                    ui.Label("sec", width=30)
                
                # Separator
                with ui.HStack(height=1):
                    ui.Line(style={"color": 0xFF666666})
                
                # Status display
                with ui.HStack(height=20, spacing=5):
                    ui.Label("Status:", width=50, style={"font_size": 16})
                    self._status_label = ui.Label("Ready", style={"color": 0xFF00AA00, "font_size": 16})

    def _on_upload_clicked(self):
        """Handle Upload button click."""
        video_filename = self._video_filename_field.model.get_value_as_string()
        
        if not video_filename:
            self._update_status("Please enter video filename", is_error=True)
            return
        
        self._update_status("Uploading video...", is_processing=True)
        
        # Disable upload button during processing
        self._upload_button.enabled = False
        
        # Run upload in separate thread to avoid blocking UI
        def upload_async():
            success = self._vlm_core.upload_video(video_filename)
            
            # Update UI with results
            self._upload_button.enabled = True
            if success:
                video_id = self._vlm_core.get_current_video_id()
                self._video_id_label.text = video_id
                self._video_id_label.style = {"color": 0xFF00AA00}
                
                # Enable delete and generate buttons
                self._delete_button.enabled = True
                self._generate_button.enabled = True
                
                self._update_status(f"Upload successful! ID: {video_id[:8]}...", is_error=False)
            else:
                self._update_status("Upload failed. Check console for details.", is_error=True)
        
        thread = threading.Thread(target=upload_async, daemon=True)
        thread.start()
    
    def _on_delete_clicked(self):
        """Handle Delete button click."""
        if not self._vlm_core.has_video_uploaded():
            self._update_status("No video to delete", is_error=True)
            return
        
        self._update_status("Deleting video...", is_processing=True)
        
        # Disable delete button during processing
        self._delete_button.enabled = False
        
        # Run delete in separate thread to avoid blocking UI
        def delete_async():
            success = self._vlm_core.delete_video()
            
            # Update UI with results
            if success:
                self._video_id_label.text = "Not uploaded"
                self._video_id_label.style = {"color": 0xFF888888}
                
                # Disable generate button (delete button already disabled)
                self._generate_button.enabled = False
                
                self._update_status("Video deleted successfully", is_error=False)
            else:
                # Re-enable delete button on failure
                self._delete_button.enabled = True
                self._update_status("Delete failed. Check console for details.", is_error=True)
        
        thread = threading.Thread(target=delete_async, daemon=True)
        thread.start()
    
    def _on_generate_clicked(self):
        """Handle Generate button click."""
        if not self._vlm_core.has_video_uploaded():
            self._update_status("No video uploaded", is_error=True)
            return
        
        # Get selected model and preset
        model_index = self._model_combo.model.get_item_value_model().as_int
        preset_index = self._preset_combo.model.get_item_value_model().as_int
        
        models = ["gpt-4o", "Qwen3-VL-8B-Instruct", "cosmos-reason1", "vila-1.5", "nvila"]
        presets = ["simple_view", "twin_view"]
        
        model = models[model_index]
        preset = presets[preset_index]
        
        self._update_status(f"Generating with {model}...", is_processing=True)
        
        # Disable generate button during processing
        self._generate_button.enabled = False
        
        # Get video filename for output naming
        video_filename = self._video_filename_field.model.get_value_as_string()
        
        # Get chunk overlap duration
        chunk_overlap = self._overlap_field.model.get_value_as_int()
        
        # Run generation in separate thread to avoid blocking UI
        def generate_async():
            success, output_filename = self._vlm_core.generate_captions(
                model=model,
                preset_name=preset,
                video_filename=video_filename,
                chunk_overlap_duration=chunk_overlap
            )
            
            # Update UI with results (simple assignment is thread-safe for display)
            self._generate_button.enabled = True
            if success and output_filename:
                self._update_status(f"Saved: {output_filename}", is_error=False)
            else:
                self._update_status("Generation failed. Check console for details.", is_error=True)
        
        thread = threading.Thread(target=generate_async, daemon=True)
        thread.start()
    
    def _update_status(self, message: str, is_error: bool = False, is_processing: bool = False):
        """Update status label with color."""
        self._status_label.text = message
        
        if is_error:
            self._status_label.style = {"color": 0xFFFF0000}  # Red
        elif is_processing:
            self._status_label.style = {"color": 0xFFFFAA00}  # Orange
        else:
            self._status_label.style = {"color": 0xFF00AA00}  # Green
    
    def destroy(self):
        """Clean up the window."""
        if self._window:
            self._window.destroy()
            self._window = None
