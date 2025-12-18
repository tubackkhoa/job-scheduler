import asyncio
import logging
import sys
from plugin_manager import PluginManager

logging.basicConfig(level=logging.ERROR)


async def main():
    plugin_manager = PluginManager(log_handler=logging.StreamHandler(sys.stdout))
    plugin_manager.start()

    try:
        await asyncio.sleep(3600)  # Keep process alive
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutting down gracefully...")
    finally:
        plugin_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
