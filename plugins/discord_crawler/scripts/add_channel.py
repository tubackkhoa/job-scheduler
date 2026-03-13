#!/usr/bin/env python3
"""CLI to add a Discord channel to the crawl target list.

Usage:
    python scripts/add_channel.py --channel CHANNEL_ID --server SERVER_ID --name CHANNEL_NAME
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_session
from app.models.server import DiscordServer
from app.models.channel import DiscordChannel
from app.models.crawl_target import CrawlTarget

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def add_channel(
    channel_id: int,
    server_id: int,
    channel_name: str,
    server_name: str = "Unknown Server",
    channel_type: str = "text",
) -> None:
    async with get_session() as session:
        # Ensure server exists
        stmt = pg_insert(DiscordServer).values(
            id=server_id,
            name=server_name,
        ).on_conflict_do_nothing(index_elements=["id"])
        await session.execute(stmt)

        # Ensure channel exists
        stmt = pg_insert(DiscordChannel).values(
            id=channel_id,
            server_id=server_id,
            name=channel_name,
            type=channel_type,
        ).on_conflict_do_nothing(index_elements=["id"])
        await session.execute(stmt)

        # Add crawl target
        stmt = pg_insert(CrawlTarget).values(
            channel_id=channel_id,
            is_active=True,
            backfill_status="pending",
        ).on_conflict_do_update(
            constraint="crawl_target_channel_id_key",
            set_={"is_active": True, "backfill_status": "pending"},
        )
        await session.execute(stmt)

    logger.info(
        "Added channel %s (%s) from server %s to crawl targets",
        channel_id, channel_name, server_id,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Add a channel to crawl targets")
    ap.add_argument("--channel", "-c", required=True, type=int, help="Channel ID")
    ap.add_argument("--server", "-s", required=True, type=int, help="Server/Guild ID")
    ap.add_argument("--name", "-n", required=True, help="Channel name")
    ap.add_argument("--server-name", default="Unknown Server", help="Server name")
    ap.add_argument("--type", default="text", choices=["text", "forum", "announcement"])
    args = ap.parse_args()

    asyncio.run(add_channel(
        args.channel, args.server, args.name,
        server_name=args.server_name, channel_type=args.type,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
