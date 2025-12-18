from collections import defaultdict
from typing import List
from fastapi import WebSocket
from datetime import datetime


class WSConnectionManager:
    def __init__(self):
        # Map user_id to list of their connections
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        connections = self.active_connections.get(user_id)
        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            self.active_connections.pop(user_id, None)

    async def send_log(self, message: dict):
        # Expected logger name format: "{package}/{user_id}"
        user_id = int(message["job_id"].rsplit("/")[1])

        connections = self.active_connections.get(user_id)
        if not connections:
            return

        disconnected: List[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_json(
                    {
                        **message,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws, user_id)
