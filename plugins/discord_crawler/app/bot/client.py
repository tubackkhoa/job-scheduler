"""Discord channel crawler using REST API polling.

Every CRAWL_INTERVAL seconds:
1. Load all active crawl targets from DB
2. For each channel, get the last message ID from discord_message table
3. Fetch messages after that ID (or up to MAX_HISTORY_DAYS back if no messages exist)
4. Push raw payloads to Redis stream for consumer to process
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy import func as sa_func

from plugins.discord_crawler.app.config import settings
from plugins.discord_crawler.app.database import get_session
from plugins.discord_crawler.app.models.crawl_target import CrawlTarget
from plugins.discord_crawler.app.models.message import DiscordMessage
from plugins.discord_crawler.app.queue.producer import push_message_batch
from plugins.discord_crawler.app.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"
DISCORD_EPOCH_MS = 1420070400000  # 2015-01-01T00:00:00Z


def _snowflake_from_datetime(dt: datetime) -> int:
    """Convert a datetime to a Discord snowflake ID (lower bound)."""
    ts_ms = int(dt.timestamp() * 1000)
    return (ts_ms - DISCORD_EPOCH_MS) << 22


class ChannelCrawler:
    """REST API poller that crawls Discord channels on an interval."""

    def __init__(self, redis_client: Redis, logger: logging.Logger = logger):
        self.redis_client = redis_client
        self.logger = logger
        self.rate_limiter = RateLimiter(settings.RATE_LIMIT_DELAY)
        self._running = True
        token = settings.DISCORD_TOKEN
        auth = f"Bot {token}" if settings.DISCORD_BOT else token
        self._headers = {
            "Authorization": auth,
            "Content-Type": "application/json",
        }

    async def run(self) -> None:
        """Main loop: poll all channels every CRAWL_INTERVAL seconds."""
        self.logger.info(
            "Channel crawler started (interval=%ds, max_history=%dd)",
            settings.CRAWL_INTERVAL,
            settings.MAX_HISTORY_DAYS,
        )
        async with aiohttp.ClientSession(headers=self._headers) as http:
            while self._running:
                try:
                    await self._crawl_all_channels(http)
                except asyncio.CancelledError:
                    self.logger.info("Crawler shutting down")
                    raise
                except Exception:
                    self.logger.exception("Error in crawl cycle")

                await asyncio.sleep(settings.CRAWL_INTERVAL)

    def stop(self) -> None:
        self._running = False

    async def _crawl_all_channels(self, http: aiohttp.ClientSession) -> None:
        """Load active targets and crawl each one."""
        targets = await self._get_active_targets()
        if not targets:
            self.logger.debug("No active crawl targets")
            return

        self.logger.info("Crawling %d active channels", len(targets))
        for channel_id, target_id in targets:
            if not self._running:
                break
            try:
                await self._crawl_channel(http, channel_id, target_id)
            except Exception:
                self.logger.exception("Failed to crawl channel %s", channel_id)

    async def _get_active_targets(self) -> list:
        """Get all active crawl target (channel_id, target_id) pairs."""
        async with get_session() as session:
            result = await session.execute(
                select(CrawlTarget.channel_id, CrawlTarget.id)
                .where(CrawlTarget.is_active == True)
                .order_by(CrawlTarget.id.asc())
            )
            return list(result.fetchall())

    async def _get_last_message_id(self, channel_id: int) -> int | None:
        """Get the most recent message ID for a channel from the DB."""
        async with get_session() as session:
            result = await session.execute(
                select(sa_func.max(DiscordMessage.id)).where(
                    DiscordMessage.channel_id == channel_id
                )
            )
            return result.scalar_one_or_none()

    async def _update_crawl_target(self, target_id: int, last_message_id: int) -> None:
        """Update the crawl target cursor and timestamp."""
        async with get_session() as session:
            await session.execute(
                update(CrawlTarget)
                .where(CrawlTarget.id == target_id)
                .values(
                    last_message_id=last_message_id,
                    crawled_at=datetime.now(timezone.utc),
                    backfill_status="done",
                )
            )

    async def _crawl_channel(
        self, http: aiohttp.ClientSession, channel_id: int, target_id: int
    ) -> None:
        """Crawl a single channel from last known message to now."""
        # Get last message ID from DB
        after_id = await self._get_last_message_id(channel_id)

        # If no messages exist, use MAX_HISTORY_DAYS lookback
        if after_id is None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=settings.MAX_HISTORY_DAYS)
            after_id = _snowflake_from_datetime(cutoff)
            self.logger.info(
                "Channel %s: no messages in DB, crawling from %d days ago (after=%s)",
                channel_id,
                settings.MAX_HISTORY_DAYS,
                after_id,
            )
        else:
            self.logger.debug("Channel %s: crawling after message %s", channel_id, after_id)

        # Paginate forward using ?after= parameter
        total = 0
        newest_id = after_id

        while True:
            messages, should_continue = await self._fetch_messages_after(
                http, channel_id, after=newest_id
            )

            if not messages:
                break

            # Discord returns newest-first with ?after=, sort ascending
            messages.sort(key=lambda m: int(m["id"]))

            # Push to Redis stream
            pushed = await push_message_batch(self.redis_client, messages)
            total += pushed

            # Track the newest message for next page
            newest_id = int(messages[-1]["id"])

            if len(messages) < 100:
                break

            if not should_continue:
                break

        if total > 0:
            await self._update_crawl_target(target_id, newest_id)
            self.logger.info(
                "Channel %s: pushed %d new messages (newest=%s)",
                channel_id,
                total,
                newest_id,
            )

    async def _fetch_messages_after(
        self,
        http: aiohttp.ClientSession,
        channel_id: int,
        *,
        after: int,
    ) -> tuple[list[dict], bool]:
        """Fetch messages after a given ID. Returns (messages, should_continue)."""
        params = {"limit": 100, "after": str(after)}

        max_retries = 5
        for attempt in range(max_retries):
            await self.rate_limiter.wait()

            try:
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

                    # Ensure guild_id is present
                    for msg in messages:
                        if "guild_id" not in msg:
                            msg["guild_id"] = None

                    return messages, True
            except aiohttp.ClientError:
                self.logger.warning(
                    "HTTP error for channel %s (attempt %d)", channel_id, attempt + 1
                )
                await asyncio.sleep(2**attempt)

        self.logger.error("Max retries exceeded for channel %s", channel_id)
        return [], False
