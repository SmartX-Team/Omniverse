from typing import Optional, Any, Dict, Literal
from pydantic import BaseModel, Field
from .client import ClientType


class BaseMessage(BaseModel):
    type: str
    timestamp: Optional[str] = None


class ClientRegisterMessage(BaseMessage):
    type: Literal["client_register"] = "client_register"
    client_type: ClientType


class CoordinateUpdateMessage(BaseMessage):
    type: Literal["coordinate_update"] = "coordinate_update"
    prim_path: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180) 
    height: float = Field(default=0.0)
    metadata: Optional[Dict[str, Any]] = None


class SelectObjectMessage(BaseMessage):
    type: Literal["select_object"] = "select_object"
    prim_path: str


class ErrorMessage(BaseMessage):
    type: Literal["error"] = "error"
    error_code: str
    error_message: str


class AckMessage(BaseMessage):
    type: Literal["ack"] = "ack"
    original_type: str
    status: str = "success"