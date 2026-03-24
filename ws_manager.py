from collections import defaultdict
from typing import Dict, List
from fastapi import WebSocket
import asyncio

from log_handler import LogEvent


class WSConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        self.active_connections[job_id].append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        conns = self.active_connections.get(job_id)
        if not conns:
            return

        if websocket in conns:
            conns.remove(websocket)

        if not conns:
            self.active_connections.pop(job_id, None)

    async def send_log(self, event: LogEvent):
        job_id = event["job_id"]
        conns = self.active_connections.get(job_id)
        if not conns:
            return

        payload = {
            "level": event["level"],
            "message": event["message"],
            "time": event["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        }

        results = await asyncio.gather(
            *(ws.send_json(payload) for ws in conns),
            return_exceptions=True,
        )

        for ws, result in zip(conns.copy(), results):
            if isinstance(result, Exception):
                self.disconnect(ws, job_id)
