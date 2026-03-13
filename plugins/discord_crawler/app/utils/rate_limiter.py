"""Rate limiter for Discord API requests."""
from __future__ import annotations

import asyncio
import logging
import time

import aiohttp

logger = logging.getLogger(__name__)


class RateLimiter:
    """Handles Discord API rate limiting with exponential backoff for 429s."""

    def __init__(self, default_delay: float = 0.5):
        self.default_delay = default_delay
        self._last_request: float = 0

    async def wait(self) -> None:
        """Wait for the default delay between requests."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.default_delay:
            await asyncio.sleep(self.default_delay - elapsed)
        self._last_request = time.monotonic()

    async def handle_response(self, response: aiohttp.ClientResponse) -> None:
        """Handle rate limit headers from Discord response."""
        if response.status == 429:
            retry_after = None
            try:
                data = await response.json()
                retry_after = data.get("retry_after")
            except Exception:
                pass
            if retry_after is None:
                retry_after = float(response.headers.get("Retry-After", "5"))
            delay = min(float(retry_after) + 1.0, 60.0)
            logger.warning("Rate limited (429). Waiting %.1fs", delay)
            await asyncio.sleep(delay)
            return

        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_after = response.headers.get("X-RateLimit-Reset-After")
        if remaining is not None and reset_after is not None:
            try:
                if int(remaining) <= 1:
                    delay = min(float(reset_after) + 0.5, 60.0)
                    logger.info("Rate limit approaching, waiting %.1fs", delay)
                    await asyncio.sleep(delay)
            except (ValueError, TypeError):
                pass
