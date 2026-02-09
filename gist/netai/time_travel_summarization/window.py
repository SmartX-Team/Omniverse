# window.py - UI for Time Travel Extension

import omni.ui as ui
import datetime
import carb


class TimeTravelWindow:
    """Time Travel UI Window."""
    
    def __init__(self, core):
        """Initialize the Time Travel window."""
        self._core = core
        self._updating_slider = False  # Flag to prevent infinite loops
        
        # Create window
        self._window = ui.Window("Time Travel", width=500, height=450)
        
        with self._window.frame:
            with ui.VStack(spacing=5):
                # Title
                with ui.HStack(height=30):
                    ui.Label("Time Travel Control", style={"font_size": 18, "font_weight": "bold"})
                
                # Dataset time range display
                with ui.VStack(spacing=3):
                    ui.Label("Dataset Range:", style={"font_size": 14, "font_weight": "bold"})
                    with ui.HStack(height=20):
                        ui.Label("Start:", width=50)
                        start_str = self._core.get_start_time().strftime("%Y-%m-%d %H:%M:%S")
                        self._start_label = ui.Label(start_str, style={"color": 0xFF888888})
                    
                    with ui.HStack(height=20):
                        ui.Label("End:", width=50)
                        end_str = self._core.get_end_time().strftime("%Y-%m-%d %H:%M:%S")
                        self._end_label = ui.Label(end_str, style={"color": 0xFF888888})
                
                # Separator
                ui.Spacer(height=5)
                with ui.HStack(height=2):
                    ui.Line(style={"color": 0xFF666666})
                
                # Go to time controls
                ui.Label("Go to Time:", style={"font_size": 14, "font_weight": "bold"})
                with ui.HStack(height=25):
                    # Date inputs
                    self._goto_year = ui.IntField(width=50)
                    self._goto_year.model.set_value(self._core.get_current_time().year)
                    ui.Label("/", width=10)
                    self._goto_month = ui.IntField(width=35)
                    self._goto_month.model.set_value(self._core.get_current_time().month)
                    ui.Label("/", width=10)
                    self._goto_day = ui.IntField(width=35)
                    self._goto_day.model.set_value(self._core.get_current_time().day)
                    
                    ui.Spacer(width=20)
                    
                    # Time inputs
                    self._goto_hour = ui.IntField(width=35)
                    self._goto_hour.model.set_value(self._core.get_current_time().hour)
                    ui.Label(":", width=10)
                    self._goto_minute = ui.IntField(width=35)
                    self._goto_minute.model.set_value(self._core.get_current_time().minute)
                    ui.Label(":", width=10)
                    self._goto_second = ui.IntField(width=35)
                    self._goto_second.model.set_value(self._core.get_current_time().second)
                    
                    ui.Spacer(width=10)
                    self._goto_button = ui.Button("Go", width=50)
                    self._goto_button.set_clicked_fn(self._on_goto_clicked)
                
                # Event Summary checkbox with Next Event button
                with ui.HStack(height=25, spacing=10):
                    self._event_checkbox = ui.CheckBox(width=20)
                    self._event_checkbox.model.set_value(False)
                    self._event_checkbox.model.add_value_changed_fn(self._on_event_checkbox_changed)
                    
                    if self._core.has_events():
                        self._event_label = ui.Label(f"Event based Summary Mode ({len(self._core.get_summary_events())} events)", width=0)
                    else:
                        self._event_label = ui.Label("Event based Summary (Check to load events)", width=0, style={"color": 0xFF888888})
                    
                    self._next_event_button = ui.Button("Next Event", width=100)
                    self._next_event_button.set_clicked_fn(self._on_next_event_clicked)
                    self._next_event_button.enabled = False  # Initially disabled
                
                # Separator
                ui.Spacer(height=5)
                with ui.HStack(height=2):
                    ui.Line(style={"color": 0xFF666666})
                
                # Current stage time display
                with ui.HStack(height=25):
                    ui.Label("Stage Time:", width=80, style={"font_size": 14, "font_weight": "bold"})
                    self._stage_time_label = ui.Label("", style={"font_size": 20, "color": 0xFF00AA00})
                
                # Playback controls
                with ui.HStack(height=30):
                    self._play_button = ui.Button("▶ Play", width=80)
                    self._play_button.set_clicked_fn(self._on_play_clicked)
                    
                    ui.Spacer(width=20)
                    
                    ui.Label("Speed:", width=50)
                    self._speed_field = ui.FloatField(width=60)
                    self._speed_field.model.set_value(self._core.get_playback_speed())
                    self._speed_field.model.add_end_edit_fn(self._on_speed_changed)
                    ui.Label("x", width=20)
                
                # Separator
                ui.Spacer(height=5)
                with ui.HStack(height=2):
                    ui.Line(style={"color": 0xFF666666})
                
                # Time slider
                ui.Label("Timeline Slider:", style={"font_size": 16, "font_weight": "bold"})
                with ui.HStack(height=30):
                    ui.Spacer(width=10)
                    self._time_slider = ui.FloatSlider(min=0.0, max=1.0)
                    self._time_slider.model.set_value(0.0)
                    self._time_slider.model.add_value_changed_fn(self._on_slider_changed)
                    ui.Spacer(width=10)
                
                # Progress percentage
                with ui.HStack(height=20):
                    ui.Spacer()
                    self._progress_label = ui.Label("0.0%", style={"font_size": 12})
                    ui.Spacer()
    
    def _on_goto_clicked(self):
        """Handle Go button click - go to user-specified time."""
        try:
            goto_time = datetime.datetime(
                self._goto_year.model.get_value_as_int(),
                self._goto_month.model.get_value_as_int(),
                self._goto_day.model.get_value_as_int(),
                self._goto_hour.model.get_value_as_int(),
                self._goto_minute.model.get_value_as_int(),
                self._goto_second.model.get_value_as_int()
            )
            
            # Always go to the specified time
            self._core.set_current_time(goto_time)
            
            # Update slider
            self._time_slider.model.set_value(self._core.get_progress())
            
        except Exception as e:
            carb.log_error(f"[TimeTravel] Error setting time: {e}")
    
    def _on_next_event_clicked(self):
        """Handle Next Event button click - jump to next event."""
        if self._core.has_events():
            self._core.go_to_next_event()
            
            # Update slider
            self._time_slider.model.set_value(self._core.get_progress())
            
            # Update goto fields to reflect new time
            self._update_goto_fields()
    
    def _on_play_clicked(self):
        """Handle Play/Pause button click."""
        self._core.toggle_playback()
        self._update_play_button()
    
    def _on_slider_changed(self, model):
        """Handle slider value change."""
        # Prevent infinite loop when updating slider programmatically
        if self._updating_slider:
            return
            
        progress = model.get_value_as_float()
        self._core.set_progress(progress)
        self._update_goto_fields()
    
    def _on_speed_changed(self, model):
        """Handle speed value change."""
        speed = model.get_value_as_float()
        self._core.set_playback_speed(speed)
    
    def _on_event_checkbox_changed(self, model):
        """Handle event summary checkbox change."""
        requested_value = model.get_value_as_bool()
        
        if requested_value:
            # User wants to enable event mode - check if events exist
            if not self._core.has_events():
                # Try to load events from Events directory
                if self._core.load_events_from_positions_jsonl():
                    # Successfully loaded events
                    self._core.set_use_event_summary(True)
                    carb.log_info("[TimeTravel] Event based Summary Mode enabled")
                    # Update label to show event count
                    self._update_event_label()
                    # Enable Next Event button
                    self._next_event_button.enabled = True
                else:
                    # No events found - revert checkbox
                    model.set_value(False)
                    carb.log_warn("[TimeTravel] No events available - Event based Summary Mode disabled")
                    self._next_event_button.enabled = False
            else:
                # Events already exist
                self._core.set_use_event_summary(True)
                carb.log_info("[TimeTravel] Event based Summary Mode enabled")
                self._next_event_button.enabled = True
        else:
            # User wants to disable event mode
            self._core.set_use_event_summary(False)
            self._next_event_button.enabled = False
            carb.log_info("[TimeTravel] Event based Summary Mode disabled")
    
    def _update_event_label(self):
        """Update event label with current event count."""
        if self._core.has_events():
            event_count = len(self._core.get_summary_events())
            self._event_label.text = f"Event based Summary Mode ({event_count} events)"
            self._event_label.style = {"color": 0xFFFFFFFF}
        else:
            self._event_label.text = "Event based Summary (Check to load events)"
            self._event_label.style = {"color": 0xFF888888}
    
    def _update_play_button(self):
        """Update play button text."""
        if self._core.is_playing():
            self._play_button.text = "Pause"
        else:
            self._play_button.text = "Play"
    
    def _update_goto_fields(self):
        """Update goto time fields with current time."""
        current = self._core.get_current_time()
        self._goto_year.model.set_value(current.year)
        self._goto_month.model.set_value(current.month)
        self._goto_day.model.set_value(current.day)
        self._goto_hour.model.set_value(current.hour)
        self._goto_minute.model.set_value(current.minute)
        self._goto_second.model.set_value(current.second)
    
    def update_ui(self):
        """Update UI elements (called every frame)."""
        # Update stage time display
        self._stage_time_label.text = self._core.get_stage_time_string()
        
        # Update slider if playing (but don't interfere with user dragging)
        if self._core.is_playing():
            progress = self._core.get_progress()
            self._updating_slider = True  # Prevent triggering _on_slider_changed
            self._time_slider.model.set_value(progress)
            self._updating_slider = False
            # self._update_goto_fields()
        
        # Update progress percentage
        progress_pct = self._core.get_progress() * 100
        self._progress_label.text = f"{progress_pct:.1f}%"
        
        # Update play button
        self._update_play_button()
    
    def destroy(self):
        """Clean up the window."""
        if self._window:
            self._window.destroy()
            self._window = None