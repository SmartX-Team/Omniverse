# view_overlay_core.py - Viewport overlay for displaying object ID labels above prims
# overlay core logic
import omni.ui as ui
import omni.ui.scene as sc
import omni.usd
import omni.kit.app
import carb
from pxr import UsdGeom, Gf
from omni.kit.viewport.utility import get_active_viewport_window


# -----------------------------------------------------------------
#  1. View (Manipulator) Class - Simplified
# -----------------------------------------------------------------
class ObjectIDManipulator(sc.Manipulator):
    """
    Displays an object ID label at the prim's 3D position.
    Directly reads prim position without using a model.
    """
    def __init__(self, prim_path: str, label_text: str, **kwargs):
        super().__init__(**kwargs)
        self._prim_path = prim_path
        self._label_text = label_text
        self._stage = omni.usd.get_context().get_stage()
        self._prim = self._stage.GetPrimAtPath(self._prim_path)
        self._xformable = UsdGeom.Xformable(self._prim) 
        """
        UsdGeom.Xformable(self._prim):
        Prim 객체(self._prim)를 Xformable 인터페이스로 감싸서,
        해당 Prim의 위치, 회전, 스케일 같은 “Transform 정보”에 접근할 수 있게 만드는 것.
        """
        self._label = None
        self._transform = None
        self._last_position = None

    def on_build(self):
        """Build the label UI at prim's current position."""
        if not self._prim or not self._prim.IsValid():
            return

        # Get world position
        xform_cache = UsdGeom.XformCache() # 변환 계산 캐싱
        world_transform = xform_cache.GetLocalToWorldTransform(self._prim) # prim의 월드 변환 행렬 추출
        # print(f"world_transform: {world_transform}")
        translation = world_transform.ExtractTranslation() # 위치 벡터 x,y,z 추출
        # print(f"Extracted translation: {translation}")
        
        # Store transform for updates
        self._transform = sc.Transform(transform=sc.Matrix44.get_translation_matrix( #Matrix44: 행렬 저장, get_translation_matrix: 위치 행렬 생성
            translation[0],         # X 좌표
            translation[1] + 100,   # Y 좌표 (100 단위 위로 오프셋)
            translation[2]          # Z 좌표
        ))
        """
        sc.Matrix44.get_translation_matrix(x, y, z): 이동 행렬 생성
        3D 공간에서 (0,0,0)을 (x, y, z) 위치로 객체를 이동시키는 이동 행렬을 생성합니다.
        [ 1, 0, 0, x ]
        [ 0, 1, 0, y ]
        [ 0, 0, 1, z ]
        [ 0, 0, 0, 1 ]
        
        즉, 그냥 해당 prim의 위치에 오프셋(축 100)을 더한 절대 위치로 라벨의 위치를 지정할 행렬을 생성하는 것임.
        """
        # Create label at world position (offset 100 units above)
        with self._transform: # sc.Transform에 포함시킨 label은 해당 위치(transform)에 그려짐
            # Billboard effect - always face camera
            with sc.Transform(look_at=sc.Transform.LookAt.CAMERA):
                # White circle background
                sc.Arc(
                    radius=30,  # DT VIEW
                    # radius=20,  # DT VIEW
                    color=0xFFFFFFFF,  # 하얀색
                    # color=0xFF000000,  # 검은색
                    thickness=40  # 꽉 찬 원을 만들기 위해 두껍게
                )
                # Draw label text on top
                self._label = sc.Label(
                    self._label_text,
                    color=0xFF000000,  # DT VIEW Black text
                    # color=0xFFFFFFFF,  # SIMPLE VIEW White text
                    size=30, #DT VIEW 18
                    alignment=ui.Alignment.CENTER
                )
        
        # Store position for comparison
        self._last_position = (translation[0], translation[1], translation[2])
    
    def update_position(self):
        """Update label position only if prim has moved."""
        if not self._prim or not self._prim.IsValid() or not self._transform:
            return
        
        # Get current world position
        xform_cache = UsdGeom.XformCache()
        world_transform = xform_cache.GetLocalToWorldTransform(self._prim)
        translation = world_transform.ExtractTranslation()
        
        current_position = (translation[0], translation[1], translation[2])
        
        # Only update if position has changed
        if self._last_position != current_position:
            # Update transform matrix
            self._transform.transform = sc.Matrix44.get_translation_matrix(
                translation[0], translation[1] + 100, translation[2]
            )
            self._last_position = current_position

    def on_model_updated(self, item):
        """Called when model changes (not used in this simplified version)."""
        pass

# -----------------------------------------------------------------
#  2. Manager Class (Model removed - not needed)
# -----------------------------------------------------------------
class ViewOverlay:
    """
    Manages viewport overlay, creating and updating
    3D labels and 2D time display.
    """
    def __init__(self, viewport_window, ext_id, core):
        self._viewport_window = viewport_window
        self._ext_id = ext_id
        self._core = core  # TimeTravelCore for time data
        self._usd_context = omni.usd.get_context()
        self._scene_view = None
        self._manipulators = []
        self._stage_event_sub = None
        self._update_sub = None
        self._visible = True
        self._labels_visible = True  # 3D labels visibility
        self._time_visible = True    # Time display visibility
        
        # Time display UI elements
        self._time_frame = None
        self._time_label = None

        # Subscribe to stage events
        self._stage_event_sub = self._usd_context.get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event, name="ViewOverlayStageEvent"
        ) # usd_context 를 보면서 stage 이벤트 변화가 생길 때 마다 _on_stage_event 함수를 호출함.
        
        carb.log_info("[ViewOverlay] Initialized")
        
        # Create time display
        self._create_time_overlay()
        
        # If stage is already open, build UI immediately
        stage = self._usd_context.get_stage()
        if stage:
            carb.log_info("[ViewOverlay] Stage already open, building UI now...")
            self._build_scene_for_stage()
        else:
            carb.log_info("[ViewOverlay] No stage yet, waiting for OPENED event...")
    
    def _create_time_overlay(self):
        """Create time display overlay in bottom-right corner."""
        viewport_window = get_active_viewport_window()
        
        if not viewport_window:
            carb.log_warn("[ViewOverlay] No active viewport for time overlay")
            return
        
        try:
            with viewport_window.get_frame("timetravel_time_overlay"):
                self._time_frame = ui.Frame(separate_window=False)
                
                with self._time_frame:
                    # Bottom-right corner positioning
                    with ui.HStack():
                        ui.Spacer()
                        with ui.VStack(width=0):
                            ui.Spacer()
                            # Time display box
                            with ui.ZStack(width=0, height=40):
                                # Background rectangle
                                ui.Rectangle(
                                    style={
                                        "background_color": 0xFF1A1A1A,
                                        "border_color": 0xFF00FF00,
                                        "border_width": 2,
                                        "border_radius": 5
                                    }
                                )
                                
                                # Date and Time text in one line
                                with ui.VStack(height=20):
                                    ui.Spacer()
                                    with ui.HStack():
                                        ui.Spacer(width=5)
                                        self._time_label = ui.Label(
                                            "00:00:00",
                                            style={
                                                "font_size": 24,
                                                "color": 0xFFFFFFFF,
                                                "font_weight": "bold"
                                            }
                                        )
                                        ui.Spacer(width=5)
                                    ui.Spacer()
                            ui.Spacer(height=0)
                
                self._time_frame.visible = self._visible
                carb.log_info("[ViewOverlay] Time display created")
        except Exception as e:
            carb.log_error(f"[ViewOverlay] Failed to create time display: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
    
    def set_visible(self, visible: bool):
        """Show or hide all labels and time display."""
        self._visible = visible
        self._labels_visible = visible
        self._time_visible = visible
        
        # Control 3D labels
        if self._scene_view:
            self._scene_view.visible = visible
        
        # Control time display
        if self._time_frame:
            self._time_frame.visible = visible
            
        carb.log_info(f"[ViewOverlay] All visibility set to: {visible}")
    
    def set_labels_visible(self, visible: bool):
        """Show or hide 3D object ID labels only."""
        self._labels_visible = visible
        if self._scene_view:
            self._scene_view.visible = visible
        carb.log_info(f"[ViewOverlay] Labels visibility set to: {visible}")
    
    def set_time_visible(self, visible: bool):
        """Show or hide time display only."""
        self._time_visible = visible
        if self._time_frame:
            self._time_frame.visible = visible
        carb.log_info(f"[ViewOverlay] Time visibility set to: {visible}")
    
    def is_visible(self) -> bool:
        """Get current visibility state."""
        return self._visible

    def shutdown(self):
        """Clean up all resources."""
        carb.log_info("[ViewOverlay] Shutting down...")
        
        self._stage_event_sub = None
        self._update_sub = None

        # Clean up scene components (manipulators, scene view)
        self._cleanup_scene()
        
        # Clean up time display
        if self._time_frame:
            self._time_frame.clear()
            self._time_frame = None
        
        self._time_label = None
        
        carb.log_info("[ViewOverlay] Cleanup complete")

    def _on_stage_event(self, event):
        """Handle stage open/close events."""
        if event.type == int(omni.usd.StageEventType.OPENED):
            carb.log_info("[ViewOverlay] Stage opened. Building UI...")
            self._build_scene_for_stage()
        elif event.type == int(omni.usd.StageEventType.CLOSED):
            carb.log_info("[ViewOverlay] Stage closed. Cleaning up UI...")
            self._cleanup_scene()

    def _get_id_from_name(self, prim_name: str) -> str:
        """
        Extract ID from prim name's last 3 digits.
        Example: 'Astronaut001' -> '1'
        """
        if len(prim_name) < 3:
            return None
        
        last_three = prim_name[-3:]
        if not last_three.isdigit():
            return None
        
        # Convert to int to remove leading zeros, then back to string
        return str(int(last_three))

    def _cleanup_scene(self):
        """Clean up UI when stage is closed."""
        # Stop update subscription
        self._update_sub = None
        
        # Explicitly invalidate manipulators
        if self._manipulators:
            for manipulator in self._manipulators:
                if hasattr(manipulator, "invalidate"):
                    manipulator.invalidate()
        self._manipulators = []
        
        # Remove and clear scene view
        if self._scene_view:
            self._scene_view.visible = False
            if self._viewport_window and hasattr(self._viewport_window, "viewport_api"):
                self._viewport_window.viewport_api.remove_scene_view(self._scene_view)
            self._scene_view = None
        
        carb.log_info("[ViewOverlay] Scene view cleaned up")

    def _build_scene_for_stage(self):
        """
        Build all Models and Manipulators when stage is ready.
        Creates labels for all prims under /World/TimeTravel_Objects.
        """
        if self._scene_view:
            carb.log_info("[ViewOverlay] Scene view already exists. Cleaning up...")
            self._cleanup_scene()

        stage = self._usd_context.get_stage()
        if not stage:
            carb.log_error("[ViewOverlay] Cannot get stage")
            return

        parent_prim_path = "/World/TimeTravel_Objects"
        parent_prim = stage.GetPrimAtPath(parent_prim_path)
        
        if not parent_prim.IsValid():
            carb.log_warn(f"[ViewOverlay] '{parent_prim_path}' prim not found")
            return

        # Create scene view
        with self._viewport_window.get_frame(self._ext_id): 
            """
            viewport의 프레임을 가져옴. 그 프레임에UI를 그릴수 있게 함.
            그리고  self._ext_id에게 할당함. 즉 extension에게 할당함
            with 문 안에서 생성된 UI 요소들은 이 프레임에 속하게 됨.
            """
            self._scene_view = sc.SceneView()   # 3D 공간을 포함하는 컨테이너 역할. 3D 공간에 3D 객체나 라벨 등을 배치할 수 있음.
            
            with self._scene_view.scene: # 루트 scene 컨테이너에 접근하는 속성
                # Create manipulator for each child prim
                for prim in parent_prim.GetChildren():
                    prim_name = prim.GetName()
                    label_id = self._get_id_from_name(prim_name)

                    if not label_id:
                        carb.log_info(f"[ViewOverlay] Cannot extract ID from '{prim_name}', skipping")
                        continue

                    prim_path = str(prim.GetPath())
                    
                    carb.log_info(f"[ViewOverlay] Tracking '{prim_path}' (ID: {label_id})")
                    
                    # Create manipulator (reads prim position directly)
                    manipulator = ObjectIDManipulator(prim_path=prim_path, label_text=label_id) # prim 마다 manipulator 생성
                    self._manipulators.append(manipulator)

            # Add scene view to viewport
            self._viewport_window.viewport_api.add_scene_view(self._scene_view) # viewport에 scene view 추가. 즉 화면에 표시

        # Subscribe to frame updates
        if not self._update_sub:
            self._update_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
                self._on_update, name="ViewOverlayFrameUpdate"
            )

    def _on_update(self, e):
        """Called every frame to update all manipulators and time display."""
        # Update 3D label positions (only if visible and changed - no flicker)
        if self._labels_visible and self._manipulators:
            for manipulator in self._manipulators:
                manipulator.update_position()
        
        # Update time display
        if self._time_visible and self._time_label:
            try:
                current_time = self._core.get_current_time()
                time_str = current_time.strftime("%H:%M:%S")
                self._time_label.text = time_str
            except Exception as e:
                carb.log_error(f"[ViewOverlay] Error updating time: {e}")
