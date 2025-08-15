# Camera Capture Extension for Omniverse without viewport changes

import omni.ext
import omni.ui as ui
from omni.usd import get_context
import omni.usd
import omni.kit.app
import omni.replicator.core as rep

import os
import asyncio
import weakref
import functools
from datetime import datetime

# --- Default Configuration ---
DEFAULT_CAMERA_PATH = "/World/Camera"
DEFAULT_OUTPUT_DIR = "/home/netai/Documents/traffic_captures"
DEFAULT_RESOLUTION = (1280, 720)

class CameraCaptureExtension(omni.ext.IExt):
    """
    Omniverse Extension UI for managing multiple camera captures
    without changing viewport using render products.
    """
    
    def on_startup(self, ext_id: str):
        """Called upon extension startup."""
        print(f"[{ext_id}] CameraCaptureExtension startup")
        
        # Initialize members
        self._window = None
        self.stage = get_context().get_stage()
        self.managed_cameras = {}
        self._camera_path_model = ui.SimpleStringModel(DEFAULT_CAMERA_PATH)
        self._output_dir_model = ui.SimpleStringModel(DEFAULT_OUTPUT_DIR)
        self._camera_ui_container = None
        self._next_camera_id = 0
        
        # Capture system
        self._render_products = {}
        self._capture_tasks = {}
        
        # Initialize replicator orchestrator
        try:
            rep.orchestrator.run()
        except Exception as e:
            print(f"[Warning] Orchestrator initialization: {e}")
        
        if not self.stage:
            print("[ERROR] Failed to get USD Stage.")
            
        # Build the UI Window
        self._window = ui.Window("Camera Capture Controller", width=800, height=600)
        
        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                # Header
                ui.Label("Off-screen Camera Capture System", 
                        style={"font_size": 16, "font_weight": "bold"})
                ui.Line()
                
                # Input Section
                with ui.VStack(spacing=5):
                    # Camera path input
                    with ui.HStack(height=30, spacing=5):
                        ui.Label("Camera Path:", width=100)
                        ui.StringField(model=self._camera_path_model, width=ui.Percent(70))
                    
                    # Output directory input
                    with ui.HStack(height=30, spacing=5):
                        ui.Label("Output Dir:", width=100)
                        ui.StringField(model=self._output_dir_model, width=ui.Percent(70))
                    
                    # Add button
                    ui.Button("Add Camera", 
                             clicked_fn=self._on_add_camera_clicked,
                             height=30,
                             style={"background_color": 0xFF4A90E2})
                
                ui.Line()
                
                # Camera List Area
                ui.Label("Managed Cameras:", style={"font_size": 14})
                with ui.ScrollingFrame(
                    height=ui.Pixel(400),
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON
                ):
                    self._camera_ui_container = ui.VStack(spacing=8)
                
                ui.Line()
                
                # Global Controls
                with ui.HStack(spacing=5):
                    ui.Button("Stop All Captures", 
                             clicked_fn=self._stop_all_captures,
                             style={"background_color": 0xFFE74C3C})
                    ui.Button("Clear All", 
                             clicked_fn=self._clear_all_cameras,
                             style={"background_color": 0xFF95A5A6})
    
    def _on_add_camera_clicked(self):
        """Callback when 'Add Camera' button is clicked."""
        camera_path = self._camera_path_model.get_value_as_string().strip()
        output_dir = self._output_dir_model.get_value_as_string().strip()
        
        # Validation
        if not camera_path:
            print("[Warning] Camera path cannot be empty.")
            return
            
        if not camera_path.startswith("/"):
            print(f"[Warning] Invalid path format: '{camera_path}'.")
            return
            
        if camera_path in self.managed_cameras:
            print(f"[Warning] Camera '{camera_path}' is already managed.")
            return
            
        # Check if camera prim exists
        if not self.stage:
            print("[ERROR] USD Stage is not available.")
            return
            
        try:
            camera_prim = self.stage.GetPrimAtPath(camera_path)
            if not camera_prim or not camera_prim.IsValid():
                print(f"[Warning] Camera prim not found at path: '{camera_path}'.")
                return
            if camera_prim.GetTypeName() != "Camera":
                print(f"[Warning] Prim at '{camera_path}' is not a Camera.")
                return
        except Exception as e:
            print(f"[ERROR] Error validating camera path '{camera_path}': {e}")
            return
            
        print(f"[Info] Adding camera: {camera_path}")
        self._add_camera_ui(camera_path, output_dir)
    
    def _add_camera_ui(self, camera_path: str, output_dir: str):
        """Creates UI section for a specific camera."""
        if not self._camera_ui_container:
            print("[ERROR] Camera UI container not initialized.")
            return
            
        # Assign unique camera_id
        camera_id = self._next_camera_id
        self._next_camera_id += 1
        
        # Create models for UI inputs
        interval_model = ui.SimpleFloatModel(1.0)  # Capture interval in seconds
        frame_count_model = ui.SimpleIntModel(5)   # Number of frames to capture
        resolution_x_model = ui.SimpleIntModel(1280)
        resolution_y_model = ui.SimpleIntModel(720)
        
        collapsable_frame = None
        status_label = None
        progress_label = None
        
        with self._camera_ui_container:
            frame_title = f"Camera {camera_id}: {camera_path}"
            collapsable_frame = ui.CollapsableFrame(frame_title, collapsed=False)
            
            with collapsable_frame:
                with ui.VStack(spacing=5, height=0):
                    # Status display
                    status_label = ui.Label("Status: Ready", word_wrap=True)
                    progress_label = ui.Label("", word_wrap=True)
                    
                    # Output directory display
                    with ui.HStack(height=25, spacing=5):
                        ui.Label("Output:", width=80)
                        ui.Label(output_dir, style={"color": 0xFF888888})
                    
                    # Resolution input
                    with ui.HStack(height=25, spacing=5):
                        ui.Label("Resolution:", width=80)
                        ui.IntField(model=resolution_x_model, width=60)
                        ui.Label("x", width=20)
                        ui.IntField(model=resolution_y_model, width=60)
                    
                    # Capture settings
                    with ui.HStack(height=25, spacing=5):
                        ui.Label("Interval (s):", width=80)
                        ui.FloatField(model=interval_model, width=60)
                        ui.Label("Frames:", width=60)
                        ui.IntField(model=frame_count_model, width=60)
                    
                    ui.Line(height=2)
                    
                    # Control buttons
                    on_capture_once = functools.partial(
                        self._on_capture_once_clicked, camera_path, camera_id
                    )
                    on_capture_periodic = functools.partial(
                        self._on_capture_periodic_clicked, camera_path, camera_id
                    )
                    on_stop_capture = functools.partial(
                        self._on_stop_capture_clicked, camera_path, camera_id
                    )
                    on_remove = functools.partial(
                        self._on_remove_clicked, camera_path, camera_id
                    )
                    
                    with ui.HStack(spacing=5):
                        ui.Button("Capture Once", 
                                 clicked_fn=on_capture_once,
                                 tooltip=f"Capture single frame from camera {camera_id}")
                        ui.Button("Start Periodic", 
                                 clicked_fn=on_capture_periodic,
                                 tooltip=f"Start periodic capture",
                                 style={"background_color": 0xFF27AE60})
                    
                    with ui.HStack(spacing=5):
                        ui.Button("Stop Capture", 
                                 clicked_fn=on_stop_capture,
                                 tooltip="Stop ongoing capture",
                                 style={"background_color": 0xFFE67E22})
                        ui.Button("Remove", 
                                 clicked_fn=on_remove,
                                 tooltip="Remove camera from management",
                                 style={"color": 0xFFFF6666})
        
        # Store camera information
        if collapsable_frame and status_label:
            camera_info = {
                "path": camera_path,
                "camera_id": camera_id,
                "output_dir": output_dir,
                "status_label": status_label,
                "progress_label": progress_label,
                "frame_ref": weakref.ref(collapsable_frame),
                "interval_model": interval_model,
                "frame_count_model": frame_count_model,
                "resolution_x_model": resolution_x_model,
                "resolution_y_model": resolution_y_model,
                "render_product": None,
                "writer": None,  # Store writer reference
                "last_resolution": None,  # Track resolution changes
                "capture_task": None,
                "frame_counter": 0
            }
            
            self.managed_cameras[camera_path] = camera_info
            print(f"[Info] Camera added - ID: {camera_id}, Path: {camera_path}")
            print(f"[Info] Total cameras: {len(self.managed_cameras)}")
    
    def _create_render_product(self, camera_path: str, camera_id: int, resolution: tuple):
        """Create render product and writer for off-screen capture."""
        try:
            # Create unique render product for this camera
            rp = rep.create.render_product(camera_path, resolution=resolution)
            
            # Create unique writer with camera-specific name
            writer_name = f"CameraWriter_{camera_id}"
            writer = rep.WriterRegistry.get("BasicWriter")
            
            # Initialize writer with unique output directory per camera
            camera_name = camera_path.split('/')[-1]
            output_subdir = os.path.join(
                self.managed_cameras[camera_path]["output_dir"],
                f"camera_{camera_id}_{camera_name}"
            )
            os.makedirs(output_subdir, exist_ok=True)
            
            writer.initialize(
                output_dir=output_subdir,
                rgb=True,
                colorize_instance_segmentation=False,
                colorize_semantic_segmentation=False
            )
            writer.attach([rp])
            
            # Store both render product and writer
            return rp, writer
        except Exception as e:
            print(f"[ERROR] Failed to create render product for camera {camera_id}: {e}")
            return None, None
    
    async def _capture_single_frame(self, camera_info: dict):
        """Capture a single frame from camera."""
        camera_path = camera_info["path"]
        camera_id = camera_info["camera_id"]
        
        # Get or create render product and writer
        resolution = (
            camera_info["resolution_x_model"].as_int,
            camera_info["resolution_y_model"].as_int
        )
        
        # Check if render product exists or resolution changed
        if not camera_info["render_product"] or camera_info.get("last_resolution") != resolution:
            # Clean up old render product if resolution changed
            if camera_info["render_product"] and camera_info.get("last_resolution") != resolution:
                print(f"[Info] Resolution changed for camera {camera_id}, recreating render product")
                camera_info["render_product"] = None
                camera_info["writer"] = None
            
            # Create new render product and writer
            rp, writer = self._create_render_product(camera_path, camera_id, resolution)
            if not rp or not writer:
                camera_info["status_label"].text = "Error: Failed to create render product"
                return False
            
            camera_info["render_product"] = rp
            camera_info["writer"] = writer
            camera_info["last_resolution"] = resolution
        
        try:
            # Capture frame using existing writer
            await rep.orchestrator.step_async()
            
            camera_info["frame_counter"] += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            camera_info["progress_label"].text = f"Captured frame {camera_info['frame_counter']} at {timestamp}"
            
            return True
        except Exception as e:
            print(f"[ERROR] Capture failed for camera {camera_id}: {e}")
            camera_info["status_label"].text = f"Error: {str(e)}"
            return False
    
    async def _capture_periodic_task(self, camera_info: dict):
        """Periodic capture task."""
        interval = camera_info["interval_model"].as_float
        total_frames = camera_info["frame_count_model"].as_int
        
        camera_info["status_label"].text = f"Capturing: 0/{total_frames}"
        
        for i in range(total_frames):
            if camera_info.get("stop_requested"):
                break
                
            await self._capture_single_frame(camera_info)
            camera_info["status_label"].text = f"Capturing: {i+1}/{total_frames}"
            
            if i < total_frames - 1:
                await asyncio.sleep(interval)
        
        if not camera_info.get("stop_requested"):
            camera_info["status_label"].text = f"Complete: {camera_info['frame_counter']} frames captured"
        else:
            camera_info["status_label"].text = f"Stopped: {camera_info['frame_counter']} frames captured"
        
        camera_info["capture_task"] = None
        camera_info["stop_requested"] = False
    
    # --- Callback Methods ---
    def _on_capture_once_clicked(self, camera_path: str, camera_id: int):
        """Capture single frame."""
        camera_info = self.managed_cameras.get(camera_path)
        if not camera_info:
            return
        
        camera_info["status_label"].text = "Capturing..."
        
        task = asyncio.ensure_future(self._capture_single_frame(camera_info))
        
        def on_complete(future):
            if future.result():
                camera_info["status_label"].text = "Single frame captured"
            else:
                camera_info["status_label"].text = "Capture failed"
        
        task.add_done_callback(on_complete)
    
    def _on_capture_periodic_clicked(self, camera_path: str, camera_id: int):
        """Start periodic capture."""
        camera_info = self.managed_cameras.get(camera_path)
        if not camera_info:
            return
        
        if camera_info["capture_task"]:
            print(f"[Warning] Capture already in progress for camera {camera_id}")
            return
        
        camera_info["stop_requested"] = False
        camera_info["capture_task"] = asyncio.ensure_future(
            self._capture_periodic_task(camera_info)
        )
    
    def _on_stop_capture_clicked(self, camera_path: str, camera_id: int):
        """Stop ongoing capture."""
        camera_info = self.managed_cameras.get(camera_path)
        if not camera_info:
            return
        
        if camera_info["capture_task"]:
            camera_info["stop_requested"] = True
            camera_info["status_label"].text = "Stopping..."
        else:
            camera_info["status_label"].text = "No active capture"
    
    def _on_remove_clicked(self, camera_path: str, camera_id: int):
        """Remove camera from management."""
        self._remove_camera_ui(camera_path)
    
    def _remove_camera_ui(self, camera_path: str):
        """Remove camera UI and cleanup."""
        print(f"[Info] Removing camera: {camera_path}")
        
        if camera_path not in self.managed_cameras:
            return
        
        camera_info = self.managed_cameras[camera_path]
        
        # Stop any ongoing capture
        if camera_info.get("capture_task"):
            camera_info["stop_requested"] = True
        
        # Clean up render product and writer
        if camera_info.get("writer"):
            try:
                # Detach and clean up writer
                camera_info["writer"] = None
            except Exception as e:
                print(f"[Warning] Failed to clean up writer: {e}")
        
        if camera_info.get("render_product"):
            try:
                # Clean up render product
                camera_info["render_product"] = None
            except Exception as e:
                print(f"[Warning] Failed to clean up render product: {e}")
        
        # Destroy UI
        frame_ref = camera_info.get("frame_ref")
        if frame_ref:
            frame = frame_ref()
            if frame:
                try:
                    frame.visible = False
                    frame.destroy()
                except:
                    pass
        
        del self.managed_cameras[camera_path]
        print(f"[Info] Camera removed. Remaining: {len(self.managed_cameras)} cameras")
    
    def _stop_all_captures(self):
        """Stop all ongoing captures."""
        for camera_path, camera_info in self.managed_cameras.items():
            if camera_info.get("capture_task"):
                camera_info["stop_requested"] = True
                camera_info["status_label"].text = "Stopped"
    
    def _clear_all_cameras(self):
        """Remove all cameras."""
        for camera_path in list(self.managed_cameras.keys()):
            self._remove_camera_ui(camera_path)
    
    def on_shutdown(self):
        """Called upon extension shutdown."""
        print("[CameraCaptureExtension] Shutdown")
        
        # Stop all captures
        self._stop_all_captures()
        
        # Clean up all render products and writers
        for camera_path, camera_info in self.managed_cameras.items():
            if camera_info.get("writer"):
                try:
                    camera_info["writer"] = None
                except:
                    pass
            if camera_info.get("render_product"):
                try:
                    camera_info["render_product"] = None
                except:
                    pass
        
        # Clear all cameras
        self._clear_all_cameras()
        
        if self._window:
            self._window.destroy()
        self._window = None
        self.stage = None
        print("[CameraCaptureExtension] Shutdown complete")