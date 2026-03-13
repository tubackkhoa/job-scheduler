import logging
from typing import Literal
from aiohttp import ClientSession
import pluggy
from pydantic import BaseModel, Field

from enforcer import ExecutionContext
from plugins import ui_schema
from .app.database import init_db

# Import crawler logic from your project
from .app.bot.client import ChannelCrawler
from .app.backfill.worker import BackfillWorker
from redis.asyncio import Redis


hookimpl = pluggy.HookimplMarker("job-scheduler")


# -----------------------------
# Config schema
# -----------------------------

CrawlMode = Literal["crawl", "backfill"]


class Config(BaseModel):
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
        json_schema_extra=ui_schema({"ui:options": {"size": 12}}),
    )

    mode: CrawlMode = Field(
        default="crawl",
        description="crawl or backfill",
        json_schema_extra=ui_schema({"ui:field": "Select", "enum": ["crawl", "backfill"]}),
    )

    run_once: bool = Field(
        default=True,
        description="Run only one cycle per scheduler execution",
        json_schema_extra=ui_schema({"ui:options": {"size": 9}}),
    )


# -----------------------------
# Plugin
# -----------------------------


class Plugin:

    # optional template environment
    _env = {}

    # -------------------------
    # Hooks required by system
    # -------------------------

    @classmethod
    @hookimpl
    def env(cls):
        return cls._env

    @classmethod
    @hookimpl
    def schema(cls, ctx):
        return Config.model_json_schema()

    @classmethod
    @hookimpl
    def config(cls, ctx, json=None, validate=False):
        return Config.model_validate(json or {})

    @classmethod
    @hookimpl
    def roles(cls):
        return {}

    @classmethod
    @hookimpl
    async def install(cls):
        await init_db()
        return True

    @classmethod
    @hookimpl
    async def uninstall(cls):
        return True

    # -------------------------
    # Main scheduled job
    # -------------------------

    @classmethod
    @hookimpl
    async def run(
        cls,
        ctx: ExecutionContext,
        config: Config,
        logger: logging.Logger,
        render,
    ):
        logger.info("Starting Discord crawler job")

        redis = Redis.from_url(config.redis_url, decode_responses=False)

        try:
            if config.mode == "crawl":
                crawler = ChannelCrawler(redis)

                async with ClientSession() as http:
                    if config.run_once:
                        logger.info("Running single crawl cycle")
                        await crawler._crawl_all_channels(http)
                    else:
                        logger.info("Running continuous crawler")
                        await crawler.run()

            elif config.mode == "backfill":
                worker = BackfillWorker(redis)

                if config.run_once:
                    processed = await worker.run_once()
                    logger.info(f"Backfill processed {processed} targets")
                else:
                    await worker.run()

        finally:
            await redis.aclose()

        logger.info("Discord crawler job finished")
        return True
