"""Entry point: run the REST API polling crawler."""

import asyncio
import logging

from redis.asyncio import Redis

from plugins.discord_crawler.app.bot.client import ChannelCrawler
from plugins.discord_crawler.app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    crawler = ChannelCrawler(redis_client=redis_client)

    try:
        logger.info("Starting channel crawler...")
        await crawler.run()
    finally:
        crawler.stop()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
