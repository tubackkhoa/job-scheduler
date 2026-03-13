"""Read from Redis Stream using consumer groups with retry and dead-letter support."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

STREAM_KEY = "discord:messages"
GROUP_NAME = "discord_workers"
DEAD_LETTER_STREAM = "discord:messages:dead"
MAX_RETRIES = 3


async def ensure_consumer_group(redis_client: Redis) -> None:
    """Create consumer group if it doesn't exist."""
    try:
        await redis_client.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
        logger.info("Created consumer group '%s'", GROUP_NAME)
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass  # Group already exists
        else:
            raise


async def consume(
    redis_client: Redis,
    consumer_name: str,
    handler: Callable[[dict], Coroutine[Any, Any, None]],
    *,
    batch_size: int = 10,
    block_ms: int = 5000,
) -> None:
    """Main consumer loop. Reads from stream, calls handler, acks on success."""
    await ensure_consumer_group(redis_client)
    logger.info("Consumer '%s' started", consumer_name)

    # First, claim any pending messages (crash recovery)
    await _process_pending(redis_client, consumer_name, handler)

    while True:
        try:
            entries = await redis_client.xreadgroup(
                GROUP_NAME,
                consumer_name,
                {STREAM_KEY: ">"},
                count=batch_size,
                block=block_ms,
            )
            if not entries:
                continue

            for stream_name, messages in entries:
                for msg_id, data in messages:
                    await _handle_message(redis_client, consumer_name, handler, msg_id, data)

        except asyncio.CancelledError:
            logger.info("Consumer '%s' shutting down", consumer_name)
            break
        except Exception:
            logger.exception("Consumer error, retrying in 5s")
            await asyncio.sleep(5)


async def _process_pending(
    redis_client: Redis,
    consumer_name: str,
    handler: Callable[[dict], Coroutine[Any, Any, None]],
) -> None:
    """Process any pending messages from previous crashed sessions."""
    try:
        pending = await redis_client.xpending_range(
            STREAM_KEY, GROUP_NAME, min="-", max="+", count=100, consumername=consumer_name
        )
        if not pending:
            return
        logger.info("Found %d pending messages to reprocess", len(pending))
        msg_ids = [p["message_id"] for p in pending]
        claimed = await redis_client.xclaim(
            STREAM_KEY, GROUP_NAME, consumer_name, min_idle_time=0, message_ids=msg_ids
        )
        for msg_id, data in claimed:
            await _handle_message(redis_client, consumer_name, handler, msg_id, data)
    except Exception:
        logger.exception("Error processing pending messages")


async def _handle_message(
    redis_client: Redis,
    consumer_name: str,
    handler: Callable[[dict], Coroutine[Any, Any, None]],
    msg_id: str | bytes,
    data: dict,
) -> None:
    """Handle a single message with retry tracking."""
    try:
        payload_str = data.get(b"payload") or data.get("payload")
        if not payload_str:
            logger.warning("Empty payload for %s, acking", msg_id)
            await redis_client.xack(STREAM_KEY, GROUP_NAME, msg_id)
            return

        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8")

        payload = json.loads(payload_str)
        await handler(payload)
        await redis_client.xack(STREAM_KEY, GROUP_NAME, msg_id)

    except Exception:
        logger.exception("Failed to process message %s", msg_id)
        # Check retry count via pending info
        try:
            pending_info = await redis_client.xpending_range(
                STREAM_KEY, GROUP_NAME, min=msg_id, max=msg_id, count=1
            )
            if pending_info and pending_info[0].get("times_delivered", 0) >= MAX_RETRIES:
                logger.error("Message %s exceeded max retries, dead-lettering", msg_id)
                await redis_client.xadd(DEAD_LETTER_STREAM, data)
                await redis_client.xack(STREAM_KEY, GROUP_NAME, msg_id)
        except Exception:
            logger.exception("Error checking retry count for %s", msg_id)
