"""
Object selection handler for Omniverse
"""

import omni.kit.app
import omni.kit.selection
from typing import List, Callable, Optional, Dict, Any

from ..utils.logger import logger


class SelectionHandler:
    """Omniverse 객체 선택 처리 클래스"""
    
    def __init__(self):
        try:
            self.selection_api = omni.kit.selection.get_selection()
            self.app = omni.kit.app.get_app()
            
            # 콜백 함수들
            self.selection_callbacks: List[Callable] = []
            
            # 선택 모니터링 설정
            self._selection_subscription = None
            self.setup_selection_monitoring()
            
            logger.info("SelectionHandler initialized")
            
        except Exception as e:
            logger.error(f"Error initializing SelectionHandler: {e}")
            self.selection_api = None
            self.app = None
        
    def add_selection_callback(self, callback: Callable[[List[str]], None]):
        """선택 변경 콜백 추가"""
        if callback not in self.selection_callbacks:
            self.selection_callbacks.append(callback)
            logger.debug(f"Selection callback added. Total: {len(self.selection_callbacks)}")
        
    def remove_selection_callback(self, callback: Callable):
        """선택 변경 콜백 제거"""
        if callback in self.selection_callbacks:
            self.selection_callbacks.remove(callback)
            logger.debug(f"Selection callback removed. Total: {len(self.selection_callbacks)}")
            
    def select_object(self, prim_path: str, clear_previous: bool = True, focus_camera: bool = False) -> bool:
        """
        객체 선택
        
        Args:
            prim_path: 선택할 객체의 Prim 경로
            clear_previous: 이전 선택을 지울지 여부
            focus_camera: 선택된 객체로 카메라 포커스 여부
            
        Returns:
            선택 성공 여부
        """
        if not self._is_api_available():
            return False
            
        try:
            success_flag = {"success": False}  # 클로저에서 사용할 플래그
            
            def do_selection():
                try:
                    if clear_previous:
                        self.selection_api.set_selected_prim_paths([prim_path], False)
                    else:
                        current_selection = self.get_selected_objects()
                        if prim_path not in current_selection:
                            current_selection.append(prim_path)
                            self.selection_api.set_selected_prim_paths(current_selection, False)
                            
                    logger.info(f"Object selected: {prim_path}")
                    
                    # 선택된 객체로 카메라 포커스 (선택사항)
                    if focus_camera:
                        self._focus_on_selected_object(prim_path)
                        
                    success_flag["success"] = True
                    
                except Exception as e:
                    logger.error(f"Error selecting object {prim_path}: {e}")
                    success_flag["success"] = False
            
            # 메인 스레드에서 실행
            self.app.get_main_thread_dispatcher().queue(do_selection)
            
            # 선택 작업이 큐에 추가되었으므로 True 반환
            # 실제 성공 여부는 콜백에서 확인 가능
            return True
                
        except Exception as e:
            logger.error(f"Error scheduling object selection {prim_path}: {e}")
            return False
            
    def select_multiple_objects(self, prim_paths: List[str], clear_previous: bool = True) -> bool:
        """
        여러 객체 선택
        
        Args:
            prim_paths: 선택할 객체들의 Prim 경로 리스트
            clear_previous: 이전 선택을 지울지 여부
            
        Returns:
            선택 성공 여부
        """
        if not self._is_api_available() or not prim_paths:
            return False
            
        try:
            def do_multiple_selection():
                try:
                    if clear_previous:
                        self.selection_api.set_selected_prim_paths(prim_paths, False)
                    else:
                        current_selection = self.get_selected_objects()
                        for prim_path in prim_paths:
                            if prim_path not in current_selection:
                                current_selection.append(prim_path)
                        self.selection_api.set_selected_prim_paths(current_selection, False)
                        
                    logger.info(f"Multiple objects selected: {len(prim_paths)} objects")
                    
                except Exception as e:
                    logger.error(f"Error selecting multiple objects: {e}")
            
            self.app.get_main_thread_dispatcher().queue(do_multiple_selection)
            return True
                
        except Exception as e:
            logger.error(f"Error scheduling multiple object selection: {e}")
            return False
            
    def clear_selection(self) -> bool:
        """선택 해제"""
        if not self._is_api_available():
            return False
            
        try:
            def do_clear_selection():
                try:
                    self.selection_api.clear_selected_prim_paths()
                    logger.info("Selection cleared")
                except Exception as e:
                    logger.error(f"Error clearing selection: {e}")
            
            self.app.get_main_thread_dispatcher().queue(do_clear_selection)
            return True
                
        except Exception as e:
            logger.error(f"Error scheduling selection clear: {e}")
            return False
            
    def get_selected_objects(self) -> List[str]:
        """현재 선택된 객체들 가져오기"""
        if not self._is_api_available():
            return []
            
        try:
            selected_paths = self.selection_api.get_selected_prim_paths()
            return list(selected_paths)
        except Exception as e:
            logger.error(f"Error getting selected objects: {e}")
            return []
            
    def is_object_selected(self, prim_path: str) -> bool:
        """특정 객체가 선택되어 있는지 확인"""
        try:
            selected_paths = self.get_selected_objects()
            return prim_path in selected_paths
        except Exception as e:
            logger.error(f"Error checking object selection {prim_path}: {e}")
            return False
            
    def get_selection_count(self) -> int:
        """선택된 객체 수 가져오기"""
        try:
            return len(self.get_selected_objects())
        except Exception as e:
            logger.error(f"Error getting selection count: {e}")
            return 0
            
    def _focus_on_selected_object(self, prim_path: str):
        """선택된 객체로 카메라 포커스 (선택사항)"""
        try:
            logger.debug(f"Focusing camera on {prim_path}")
            
            # Omniverse 뷰포트 API를 사용한 카메라 포커스
            try:
                import omni.kit.viewport.utility
                viewport_api = omni.kit.viewport.utility.get_active_viewport()
                if viewport_api:
                    # Frame selection - 선택된 객체에 카메라 포커스
                    viewport_api.frame_selection([prim_path])
                    logger.debug(f"Camera focused on {prim_path}")
                else:
                    logger.warning("Active viewport not available for camera focus")
            except ImportError:
                logger.debug("Viewport utility not available - skipping camera focus")
            except Exception as e:
                logger.warning(f"Error focusing camera: {e}")
            
        except Exception as e:
            logger.error(f"Error focusing on object {prim_path}: {e}")
            
    def setup_selection_monitoring(self):
        """선택 변경 모니터링 설정"""
        try:
            if not self._is_api_available():
                return
                
            # Selection API의 변경 이벤트를 구독
            if hasattr(self.selection_api, 'add_selection_changed_fn'):
                self._selection_subscription = self.selection_api.add_selection_changed_fn(
                    self._on_selection_changed
                )
                logger.debug("Selection monitoring setup successfully")
            else:
                logger.debug("Selection changed event not available")
            
        except Exception as e:
            logger.error(f"Error setting up selection monitoring: {e}")
            
    def _on_selection_changed(self, selected_paths: List[str]):
        """선택 변경 이벤트 핸들러"""
        try:
            logger.debug(f"Selection changed: {len(selected_paths)} objects selected")
            
            # 콜백 호출
            for callback in self.selection_callbacks:
                try:
                    callback(selected_paths)
                except Exception as e:
                    logger.error(f"Error in selection callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling selection change: {e}")
            
    def handle_web_selection_request(self, prim_path: str, action: str = "select") -> bool:
        """
        웹에서 온 선택 요청 처리
        
        Args:
            prim_path: 대상 객체 경로
            action: 수행할 액션 ("select", "clear", "toggle", "focus")
            
        Returns:
            처리 성공 여부
        """
        try:
            logger.info(f"Web selection request: {action} {prim_path}")
            
            if action == "select":
                return self.select_object(prim_path, clear_previous=True, focus_camera=False)
            elif action == "select_and_focus":
                return self.select_object(prim_path, clear_previous=True, focus_camera=True)
            elif action == "add_to_selection":
                return self.select_object(prim_path, clear_previous=False, focus_camera=False)
            elif action == "clear":
                return self.clear_selection()
            elif action == "toggle":
                if self.is_object_selected(prim_path):
                    return self.clear_selection()
                else:
                    return self.select_object(prim_path, clear_previous=True, focus_camera=False)
            elif action == "focus":
                # 선택하지 않고 카메라만 포커스
                def do_focus():
                    self._focus_on_selected_object(prim_path)
                self.app.get_main_thread_dispatcher().queue(do_focus)
                return True
            else:
                logger.warning(f"Unknown selection action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling web selection request: {e}")
            return False
            
    def validate_selection_request(self, prim_path: str) -> bool:
        """
        선택 요청의 유효성 검증
        
        Args:
            prim_path: 검증할 Prim 경로
            
        Returns:
            유효성 여부
        """
        try:
            if not prim_path or not isinstance(prim_path, str):
                return False
                
            # Prim 경로 형식 검증
            if not prim_path.startswith('/'):
                return False
                
            # USD Stage에서 실제 존재하는지 확인
            import omni.usd
            from pxr import Sdf
            
            context = omni.usd.get_context()
            if context:
                stage = context.get_stage()
                if stage:
                    prim = stage.GetPrimAtPath(Sdf.Path(prim_path))
                    return prim.IsValid()
                    
            return False
            
        except Exception as e:
            logger.error(f"Error validating selection request for {prim_path}: {e}")
            return False
            
    def get_status(self) -> Dict[str, Any]:
        """SelectionHandler 상태 정보"""
        return {
            "api_available": self._is_api_available(),
            "selection_count": self.get_selection_count(),
            "monitoring_enabled": self._selection_subscription is not None,
            "callback_count": len(self.selection_callbacks)
        }
        
    def _is_api_available(self) -> bool:
        """Selection API 사용 가능 여부 확인"""
        return self.selection_api is not None and self.app is not None
            
    def cleanup(self):
        """정리 작업"""
        try:
            # 선택 모니터링 해제
            if self._selection_subscription:
                try:
                    if hasattr(self.selection_api, 'remove_selection_changed_fn'):
                        self.selection_api.remove_selection_changed_fn(self._selection_subscription)
                except Exception as e:
                    logger.error(f"Error removing selection subscription: {e}")
                finally:
                    self._selection_subscription = None
                    
            # 콜백 정리
            self.selection_callbacks.clear()
            
            logger.info("SelectionHandler cleaned up")
            
        except Exception as e:
            logger.error(f"Error during SelectionHandler cleanup: {e}")