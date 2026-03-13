"""Push raw Discord message payloads to Redis Stream."""
from __future__ import annotations

import json
import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

STREAM_KEY = "discord:messages"


async def push_message(redis_client: Redis, raw_payload: dict) -> str | None:
    """Push a raw Discord message dict to the Redis stream.

    Returns the stream entry ID on success, None on failure.
    """
    try:
        data = json.dumps(raw_payload, ensure_ascii=False, default=str)
        entry_id = await redis_client.xadd(STREAM_KEY, {"payload": data})
        return entry_id
    except Exception:
        logger.exception("Failed to push message to stream")
        return None


async def push_message_batch(redis_client: Redis, payloads: list[dict]) -> int:
    """Push multiple messages. Returns count of successfully pushed."""
    count = 0
    pipe = redis_client.pipeline()
    for payload in payloads:
        data = json.dumps(payload, ensure_ascii=False, default=str)
        pipe.xadd(STREAM_KEY, {"payload": data})
    try:
        results = await pipe.execute()
        count = sum(1 for r in results if r)
    except Exception:
        logger.exception("Failed to push batch to stream")
    return count
