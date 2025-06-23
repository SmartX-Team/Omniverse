from enum import Enum
from typing import Optional
from pydantic import BaseModel
from fastapi import WebSocket


class ClientType(str, Enum):
    OMNIVERSE_EXTENSION = "omniverse_extension"
    WEB_UI = "web_ui"


class ClientInfo(BaseModel):
    client_id: str
    client_type: Optional[ClientType] = None
    websocket: Optional[WebSocket] = None
    is_registered: bool = False
    
    class Config:
        arbitrary_types_allowed = True  # WebSocket 객체 허용