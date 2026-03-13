"""Entry point: run the backfill worker."""

import asyncio
import logging
import sys

from plugins.discord_crawler.app.backfill.worker import run_backfill

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


if __name__ == "__main__":
    once = "--once" in sys.argv
    asyncio.run(run_backfill(once=once))
