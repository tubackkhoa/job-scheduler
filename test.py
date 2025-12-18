import asyncio
import logging
import os
import dotenv
from plugin_manager import PluginManager

dotenv.load_dotenv()
logging.basicConfig(level=logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.CRITICAL)


async def main():
    plugin_manager = PluginManager(
        log_handler=logging.NullHandler(),
        module_paths=os.getenv("MODULE_PATH", "").split(":"),
    )
    plugin = plugin_manager.load_plugin(
        "src.plugins.lab_webhook_worker@v0_1_0.LabWebhookWorkerPlugin"
    )
    assert plugin
    config = plugin.config()
    await plugin.run(config, logging.getLogger("worker"))

    try:
        await asyncio.sleep(3600)  # Keep process alive
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutting down gracefully...")
    finally:
        plugin_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
