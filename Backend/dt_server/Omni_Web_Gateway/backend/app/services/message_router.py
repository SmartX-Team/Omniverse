from typing import Optional, Dict, Any


class MessageRouter:
    """메시지 라우팅 서비스"""
    
    def get_message_route(self, client_type: str, message: Dict[str, Any]) -> Optional[str]:
        """메시지 타입과 클라이언트 타입에 따른 라우팅 결정"""
        message_type = message.get("type")
        
        if message_type == "coordinate_update" and client_type == "omniverse_extension":
            return "broadcast_to_web_clients"
        elif message_type == "select_object" and client_type == "web_ui":
            return "send_to_omniverse_clients"
        
        return None