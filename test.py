import asyncio
import logging
import os
import sys
import dotenv
from plugin_manager import PluginManager

dotenv.load_dotenv()
logging.basicConfig(level=logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.CRITICAL)


async def main(package: str):
    plugin_manager = PluginManager(
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


if __name__ == "__main__":
    # python test.py "src.plugins.lab_webhook_worker@v0_1_0.LabWebhookWorkerPlugin"
    asyncio.run(main(sys.argv[1]))
