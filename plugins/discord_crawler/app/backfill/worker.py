"""Backfill worker: paginate historical Discord messages via REST API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
from redis.asyncio import Redis
from sqlalchemy import select, update

from plugins.discord_crawler.app.config import settings
from plugins.discord_crawler.app.database import get_session
from plugins.discord_crawler.app.models.crawl_target import CrawlTarget
from plugins.discord_crawler.app.queue.producer import push_message_batch
from plugins.discord_crawler.app.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"


class BackfillWorker:
    """Paginate Discord REST API to backfill historical messages."""

    def __init__(self, redis_client: Redis, logger: logging.Logger = logger):
        self.logger = logger
        self.redis_client = redis_client
        self.rate_limiter = RateLimiter(settings.RATE_LIMIT_DELAY)
        token = settings.DISCORD_TOKEN
        auth = f"Bot {token}" if settings.DISCORD_BOT else token
        self._headers = {
            "Authorization": auth,
            "Content-Type": "application/json",
        }

    async def run(self) -> None:
        """Main loop: find pending targets and backfill them."""
        self.logger.info("Backfill worker started")
        async with aiohttp.ClientSession(headers=self._headers) as http:
            while True:
                target = await self._get_next_target()
                if not target:
                    self.logger.info("No pending backfill targets. Sleeping 60s...")
                    await asyncio.sleep(60)
                    continue

                channel_id, target_id, last_message_id = target
                await self._backfill_channel(http, target_id, channel_id, last_message_id)

    async def run_once(self) -> int:
        """Process all pending targets once, then exit. Returns count of targets processed."""
        count = 0
        async with aiohttp.ClientSession(headers=self._headers) as http:
            while True:
                target = await self._get_next_target()
                if not target:
                    break
                channel_id, target_id, last_message_id = target
                await self._backfill_channel(http, target_id, channel_id, last_message_id)
                count += 1
        self.logger.info("Backfill complete. Processed %d targets.", count)
        return count

    async def _get_next_target(self) -> tuple[int, int, int | None] | None:
        """Get next pending crawl target."""
        async with get_session() as session:
            result = await session.execute(
                select(CrawlTarget.channel_id, CrawlTarget.id, CrawlTarget.last_message_id)
                .where(CrawlTarget.backfill_status == "pending")
                .where(CrawlTarget.is_active == True)
                .order_by(CrawlTarget.added_at.asc())
                .limit(1)
            )
            row = result.first()
            if row:
                return row[0], row[1], row[2]
            return None

    async def _set_status(self, target_id: int, status: str) -> None:
        async with get_session() as session:
            await session.execute(
                update(CrawlTarget)
                .where(CrawlTarget.id == target_id)
                .values(
                    backfill_status=status,
                    crawled_at=datetime.now(timezone.utc) if status in ("done", "failed") else None,
                )
            )

    async def _update_cursor(self, target_id: int, last_message_id: int) -> None:
        async with get_session() as session:
            await session.execute(
                update(CrawlTarget)
                .where(CrawlTarget.id == target_id)
                .values(last_message_id=last_message_id)
            )

    async def _backfill_channel(
        self,
        http: aiohttp.ClientSession,
        target_id: int,
        channel_id: int,
        last_message_id: int | None,
    ) -> None:
        self.logger.info(
            "Starting backfill for channel %s (cursor=%s)", channel_id, last_message_id
        )
        await self._set_status(target_id, "running")

        cursor_before = last_message_id
        total = 0
        batch_size = settings.BACKFILL_BATCH_SIZE
        consecutive_errors = 0

        try:
            while True:
                messages, should_continue = await self._fetch_page(
                    http, channel_id, before=cursor_before, limit=batch_size
                )

                if not messages:
                    break

                # Push to Redis stream (same as realtime)
                pushed = await push_message_batch(self.redis_client, messages)
                total += pushed

                # Update cursor to oldest message in batch
                oldest_id = int(messages[-1]["id"])
                cursor_before = oldest_id
                await self._update_cursor(target_id, oldest_id)

                self.logger.info(
                    "Backfill channel %s: %d messages (cursor=%s)",
                    channel_id,
                    total,
                    oldest_id,
                )

                consecutive_errors = 0

                if len(messages) < batch_size:
                    break  # No more pages

                if not should_continue:
                    break

                await self.rate_limiter.wait()

            await self._set_status(target_id, "done")
            self.logger.info("Backfill done for channel %s: %d messages total", channel_id, total)

        except Exception:
            consecutive_errors += 1
            self.logger.exception(
                "Backfill failed for channel %s after %d messages", channel_id, total
            )
            await self._set_status(target_id, "failed")

    async def _fetch_page(
        self,
        http: aiohttp.ClientSession,
        channel_id: int,
        *,
        before: int | None = None,
        limit: int = 100,
    ) -> tuple[list[dict], bool]:
        """Fetch a page of messages. Returns (messages, should_continue)."""
        params = {"limit": min(limit, 100)}
        if before:
            params["before"] = before

        max_retries = 5
        for attempt in range(max_retries):
            await self.rate_limiter.wait()

            async with http.get(
                f"{DISCORD_API}/channels/{channel_id}/messages",
                params=params,
            ) as resp:
                if resp.status == 429:
                    await self.rate_limiter.handle_response(resp)
                    continue

                if resp.status == 403:
                    self.logger.error("No access to channel %s (403)", channel_id)
                    return [], False

                if resp.status != 200:
                    self.logger.warning(
                        "Unexpected status %s for channel %s (attempt %d)",
                        resp.status,
                        channel_id,
                        attempt + 1,
                    )
                    await asyncio.sleep(2**attempt)
                    continue

                await self.rate_limiter.handle_response(resp)
                messages = await resp.json()

                # Add guild_id to each message payload for the worker
                for msg in messages:
                    if "guild_id" not in msg:
                        msg["guild_id"] = None  # Will be set from channel info

                return messages, True

        self.logger.error("Max retries exceeded for channel %s", channel_id)
        return [], False


async def run_backfill(once: bool = False) -> None:
    """Entry point for the backfill worker."""
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        worker = BackfillWorker(redis_client)
        if once:
            await worker.run_once()
        else:
            await worker.run()
    finally:
        await redis_client.aclose()
