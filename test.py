import asyncio
import logging
import os
import sys
import dotenv
from sqlalchemy import create_engine
from create_data import create_data
from plugin_manager import PluginManager

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)
# logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


async def main(package: str):
    db_connection = os.getenv("DB_CONNECTION")
    assert db_connection

    db_engine = create_engine(db_connection)
    if ":memory:" in db_connection:
        create_data(db_engine, [1])

    plugin_manager = PluginManager(
        db_engine,
        log_handler=logging.NullHandler(),
        module_paths=os.getenv("MODULE_PATH", "").split(":"),
    )

    # run specific package or run all from database
    if package:
        plugin = plugin_manager.load_plugin(package)
        assert plugin
        config = plugin.config()
        await plugin.run(config, logging.getLogger("worker"))
    else:
        plugin_manager.start()
        try:
            await asyncio.sleep(3600)  # Keep process alive
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nShutting down gracefully...")
        finally:
            plugin_manager.stop()
            os._exit(0)


if __name__ == "__main__":
    # python test.py "src.plugins.lab_webhook_worker@v0_1_0.LabWebhookWorkerPlugin"
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else ""))
