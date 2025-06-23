from fastapi import APIRouter
from ..websocket.manager import websocket_manager

router = APIRouter()


@router.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "service": "Omni Web Gateway",
        "version": "1.0.0"
    }


@router.get("/status")
async def server_status():
    """서버 및 연결 상태 확인"""
    client_summary = websocket_manager.get_connected_clients_summary()
    
    return {
        "status": "running",
        "clients": client_summary
    }