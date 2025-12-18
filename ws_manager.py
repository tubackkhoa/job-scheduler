from fastapi import WebSocket
from datetime import datetime


class WSConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_log(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                # add time
                message["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for dc in disconnected:
            self.disconnect(dc)
