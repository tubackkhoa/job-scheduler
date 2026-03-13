"""Redis SET-based message deduplication."""
from __future__ import annotations

import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

DEDUP_KEY = "dedup:messages"
DEDUP_TTL = 7 * 24 * 3600  # 7 days


async def is_duplicate(redis_client: Redis, message_id: int | str) -> bool:
    """Check if message has already been processed."""
    return bool(await redis_client.sismember(DEDUP_KEY, str(message_id)))


async def mark_processed(redis_client: Redis, message_id: int | str) -> None:
    """Mark message as processed. Refreshes TTL on the set."""
    await redis_client.sadd(DEDUP_KEY, str(message_id))
    # Refresh TTL on the whole set periodically
    ttl = await redis_client.ttl(DEDUP_KEY)
    if ttl < 0:  # no TTL set
        await redis_client.expire(DEDUP_KEY, DEDUP_TTL)
