from datetime import datetime

import redis.asyncio as aioredis
from collections import defaultdict
from typing import Dict, List
from fastapi import WebSocket
import asyncio

from helper import extract_job_id
from log_handler import LogEvent


class WSConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, job_id: int):
        await websocket.accept()
        self.active_connections[job_id].append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: int):
        conns = self.active_connections.get(job_id)
        if not conns:
            return

        if websocket in conns:
            conns.remove(websocket)

        if not conns:
            self.active_connections.pop(job_id, None)

    async def send_log(self, event: LogEvent):
        job_id = extract_job_id(event["job_id"])
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

    async def log_subscriber(self, redis_client: aioredis.Redis):
        pubsub = redis_client.pubsub()
        await pubsub.psubscribe("logs:job-scheduler.job.*")

        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                # channel = "logs:job-scheduler.job.123"
                job_id = extract_job_id(message["channel"])
                log_event: LogEvent = {
                    "job_id": f"job-scheduler.job.{job_id}",
                    "level": "INFO",
                    "message": message["data"],
                    "created_at": datetime.now(),
                    "type": "log",
                }
                await self.send_log(log_event)
            except Exception:
                pass  # never crash the subscriber
