from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from plugin_manager import PluginManager
from ws_manager import WSConnectionManager

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/logs/{job_id}")
async def websocket_logs_endpoint(websocket: WebSocket, job_id: int):
    scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
    ws_manager: WSConnectionManager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket, scheduler_job_id)
    try:
        while True:
            # Keep connection alive; you can also handle client messages here if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, scheduler_job_id)
