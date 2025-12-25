import asyncio
import logging
import os
import sys
import dotenv
from sqlalchemy import create_engine
from create_data import create_data
from plugin_manager import PluginManager
from apscheduler.jobstores.redis import RedisJobStore

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, handlers=[logging.NullHandler()])


async def main(package: str):
    db_engine = create_engine("sqlite:///:memory:?check_same_thread=false")

    # test a sample plugin in memory DB
    plugin_data = (
        [
            {
                "package": package,
                "interval": 1,
                "description": "Sample plugin version 0.1.0 running frequently.",
            }
        ]
        if package
        else []
    )

    create_data(db_engine, session_ids=[1], plugin_data=plugin_data)

    plugin_manager = PluginManager(
        db_engine,
        log_handler=logging.StreamHandler(),
        module_paths=os.getenv("MODULE_PATH", "").split(":"),
        scheduler_kwargs={
            "jobstores": {"default": RedisJobStore(host="localhost", port=6379, db=0)},
        },
    )

    # run specific package or run all from database
    plugin_manager.start()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutting down gracefully...")
    finally:
        plugin_manager.stop()
        os._exit(0)


if __name__ == "__main__":
    # python test.py "plugins.sample_plugin@v0_1_0.Plugin"
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else ""))
