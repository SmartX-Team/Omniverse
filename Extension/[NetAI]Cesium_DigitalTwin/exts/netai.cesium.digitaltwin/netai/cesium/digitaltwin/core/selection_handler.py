"""
Object selection handler for Omniverse
"""

import omni.kit.app
import omni.kit.selection
from typing import List, Callable, Optional

from ..utils.logger import logger


class SelectionHandler:
    """Omniverse 객체 선택 처리 클래스"""
    
    def __init__(self):
        self.selection_api = omni.kit.selection.get_selection()
        self.app = omni.kit.app.get_app()
        
        # 콜백 함수들
        self.selection_callbacks: List[Callable] = []
        
        logger.info("SelectionHandler initialized")
        
    def add_selection_callback(self, callback: Callable[[List[str]], None]):
        """선택 변경 콜백 추가"""
        self.selection_callbacks.append(callback)
        logger.debug(f"Selection callback added. Total: {len(self.selection_callbacks)}")
        
    def remove_selection_callback(self, callback: Callable):
        """선택 변경 콜백 제거"""
        if callback in self.selection_callbacks:
            self.selection_callbacks.remove(callback)
            logger.debug(f"Selection callback removed. Total: {len(self.selection_callbacks)}")
            
    def select_object(self, prim_path: str, clear_previous: bool = True) -> bool:
        """
        객체 선택
        
        Args:
            prim_path: 선택할 객체의 Prim 경로
            clear_previous: 이전 선택을 지울지 여부
            
        Returns:
            선택 성공 여부
        """
        try:
            # 메인 스레드에서 실행하도록 스케줄링
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
                    if clear_previous:
                        self._focus_on_selected_object(prim_path)
                        
                    return True
                    
                except Exception as e:
                    logger.error(f"Error selecting object {prim_path}: {e}")
                    return False
            
            # 메인 스레드에서 실행
            if self.app:
                self.app.get_main_thread_dispatcher().queue(do_selection)
                return True
            else:
                logger.error("App instance not available")
                return False
                
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
                        
                    logger.info(f"Multiple objects selected: {prim_paths}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Error selecting multiple objects: {e}")
                    return False
            
            if self.app:
                self.app.get_main_thread_dispatcher().queue(do_multiple_selection)
                return True
            else:
                logger.error("App instance not available")
                return False
                
        except Exception as e:
            logger.error(f"Error scheduling multiple object selection: {e}")
            return False
            
    def clear_selection(self) -> bool:
        """선택 해제"""
        try:
            def do_clear_selection():
                try:
                    self.selection_api.clear_selected_prim_paths()
                    logger.info("Selection cleared")
                    return True
                except Exception as e:
                    logger.error(f"Error clearing selection: {e}")
                    return False
            
            if self.app:
                self.app.get_main_thread_dispatcher().queue(do_clear_selection)
                return True
            else:
                logger.error("App instance not available")
                return False
                
        except Exception as e:
            logger.error(f"Error scheduling selection clear: {e}")
            return False
            
    def get_selected_objects(self) -> List[str]:
        """현재 선택된 객체들 가져오기"""
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
            
    def _focus_on_selected_object(self, prim_path: str):
        """선택된 객체로 카메라 포커스 (선택사항)"""
        try:
            # 뷰포트 카메라를 선택된 객체로 이동
            # 이 기능은 선택사항이며, 필요에 따라 구현
            logger.debug(f"Focusing camera on {prim_path}")
            
            # 실제 구현은 카메라 API를 사용해야 함
            # import omni.kit.viewport.utility
            # viewport_api = omni.kit.viewport.utility.get_active_viewport()
            # if viewport_api:
            #     viewport_api.frame_selection([prim_path])
            
        except Exception as e:
            logger.error(f"Error focusing on object {prim_path}: {e}")
            
    def setup_selection_monitoring(self):
        """선택 변경 모니터링 설정"""
        try:
            # Selection API의 변경 이벤트를 구독
            # 실제 구현에서는 selection API의 이벤트를 구독해야 함
            logger.info("Selection monitoring setup")
            
            # 예시: selection changed 이벤트 구독
            # self.selection_api.add_selection_changed_fn(self._on_selection_changed)
            
        except Exception as e:
            logger.error(f"Error setting up selection monitoring: {e}")
            
    def _on_selection_changed(self, selected_paths: List[str]):
        """선택 변경 이벤트 핸들러"""
        try:
            logger.debug(f"Selection changed: {selected_paths}")
            
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
            action: 수행할 액션 ("select", "clear", "toggle")
            
        Returns:
            처리 성공 여부
        """
        try:
            logger.info(f"Web selection request: {action} {prim_path}")
            
            if action == "select":
                return self.select_object(prim_path, clear_previous=True)
            elif action == "clear":
                return self.clear_selection()
            elif action == "toggle":
                if self.is_object_selected(prim_path):
                    return self.clear_selection()
                else:
                    return self.select_object(prim_path, clear_previous=True)
            else:
                logger.warning(f"Unknown selection action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling web selection request: {e}")
            return False
            
    def cleanup(self):
        """정리 작업"""
        self.selection_callbacks.clear()
        logger.info("SelectionHandler cleaned up")