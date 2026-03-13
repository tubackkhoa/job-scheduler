"""Entry point: run the message queue consumer worker."""

import asyncio
import logging
import os

from redis.asyncio import Redis

from plugins.discord_crawler.app.config import settings
from plugins.discord_crawler.app.queue.consumer import consume
from plugins.discord_crawler.app.workers.message_worker import process_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    consumer_name = f"worker-{os.getpid()}"

    async def handler(payload: dict) -> None:
        await process_message(payload, redis_client)

    try:
        logger.info("Starting worker consumer '%s'...", consumer_name)
        await consume(redis_client, consumer_name, handler)
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
