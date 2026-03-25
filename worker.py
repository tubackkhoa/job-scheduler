import asyncio
import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from dao import DAO
from log_handler import JobLogHandler, LogEvent
from plugin_manager import PluginManager
from enforcer import create_enforcer, GLOBAL_PERMISSION_REGISTRY, freeze_permission_registry
from renderer import Renderer
from schemas import settings
import redis.asyncio as aioredis

import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
logging.basicConfig(level=logging.DEBUG, handlers=[logging.NullHandler()])


async def run_worker():
    logger = logging.getLogger("worker")
    logger.setLevel(logging.INFO)
    logger.info("🚀 Starting Job Scheduler Worker...")

    engine = create_async_engine(settings.db_connection, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    dao = DAO(session_factory)

    log_handler = JobLogHandler()

    # Redis for locking + log publishing
    redis_client = None
    if settings.redis_host:
        redis_client = aioredis.from_url(
            f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db or 0}"
        )

        # 2. Publish to Redis (workers only)
        async def publish_log(log_event: LogEvent):
            channel = f"logs:{log_event['job_id']}"
            await redis_client.publish(channel, log_event["message"])

        log_handler.add_hook(publish_log)

    GLOBAL_PERMISSION_REGISTRY.update({"dao": dao})
    freeze_permission_registry()
    Renderer.update()

    plugin_manager = PluginManager(
        dao=dao,
        enforcer=create_enforcer(),
        log_handler=log_handler,
        module_paths=settings.module_path.split(":") if settings.module_path else None,
        plugin_path=settings.plugin_path,
        redis_client=redis_client,
    )

    await plugin_manager.reload_all_jobs()
    plugin_manager.start()

    logger.info("✅ Worker ready - scheduler running")

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        plugin_manager.stop()
        if redis_client:
            await redis_client.aclose()
        # Immediate hard exit after 1 second for cleaning up
        await asyncio.sleep(1)
        os._exit(0)


if __name__ == "__main__":
    asyncio.run(run_worker())
