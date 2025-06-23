from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class BaseMessage(BaseModel):
    type: str
    timestamp: Optional[str] = None


class ClientRegisterMessage(BaseMessage):
    type: str = Field(default="client_register", const=True)
    client_type: ClientType


class CoordinateUpdateMessage(BaseMessage):
    type: str = Field(default="coordinate_update", const=True)  
    prim_path: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180) 
    height: float = Field(default=0.0)
    metadata: Optional[Dict[str, Any]] = None


class SelectObjectMessage(BaseMessage):
    type: str = Field(default="select_object", const=True)
    prim_path: str


class ErrorMessage(BaseMessage):
    type: str = Field(default="error", const=True)
    error_code: str
    error_message: str


class AckMessage(BaseMessage):
    type: str = Field(default="ack", const=True)
    original_type: str
    status: str = "success"