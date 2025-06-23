from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..core.logger import logger
from ..websocket.manager import websocket_manager
from ..websocket.handlers import message_handler

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = await websocket_manager.connect(websocket)
    
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            raw_message = await websocket.receive_text()
            
            # 메시지 처리
            await message_handler.handle_message(client_id, raw_message)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
    finally:
        websocket_manager.disconnect(client_id)