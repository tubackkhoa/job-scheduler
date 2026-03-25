from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ws_manager import WSConnectionManager

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/logs/{job_id}")
async def websocket_logs_endpoint(websocket: WebSocket, job_id: int):
    ws_manager: WSConnectionManager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket, job_id)
    try:
        while True:
            # Keep connection alive; you can also handle client messages here if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, job_id)
