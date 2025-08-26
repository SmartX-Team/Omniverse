# ui/panels/base_panel.py
from abc import ABC, abstractmethod
import omni.ui as ui
from typing import Dict, Any, Optional

class CameraPanelBase(ABC):
    """Abstract base class for camera capture panels"""
    
    def __init__(self, camera_id: int, camera_path: str, container: ui.Widget):
        self.camera_id = camera_id
        self.camera_path = camera_path
        self.container = container
        self._frame = None
        self._ui_models = {}
        self._ui_refs = {}
        self._is_destroyed = False
    
    @abstractmethod
    def build_panel(self, **kwargs) -> Dict[str, Any]:
        """Build the panel UI and return UI references"""
        pass
    
    @abstractmethod
    def get_capture_mode(self) -> str:
        """Return capture mode type (LOCAL, KAFKA, etc)"""
        pass
    
    def get_ui_models(self) -> Dict[str, Any]:
        """Get all UI models"""
        return self._ui_models
    
    def get_ui_refs(self) -> Dict[str, Any]:
        """Get all UI references"""
        return self._ui_refs
    
    def get_all_refs(self) -> Dict[str, Any]:
        """Get combined models and refs"""
        return {**self._ui_models, **self._ui_refs}
    
    def update_status(self, status: str):
        """Update status label"""
        if self._ui_refs.get("status_label"):
            self._ui_refs["status_label"].text = status
    
    def update_progress(self, progress: str):
        """Update progress label"""
        if self._ui_refs.get("progress_label"):
            self._ui_refs["progress_label"].text = progress
    
    def hide(self):
        """Hide the panel"""
        if self._frame and not self._is_destroyed:
            self._frame.visible = False
    
    def show(self):
        """Show the panel"""
        if self._frame and not self._is_destroyed:
            self._frame.visible = True
    
    def destroy(self):
        """Destroy the panel"""
        if self._frame and not self._is_destroyed:
            self._frame.visible = False
            self._frame.destroy()
            self._is_destroyed = True
    
    def is_destroyed(self) -> bool:
        """Check if panel is destroyed"""
        return self._is_destroyed