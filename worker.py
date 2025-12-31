from sqlalchemy import create_engine
import logging
import os
import asyncio
from plugin_manager import PluginManager
import dotenv

dotenv.load_dotenv()


async def main():
    plugin_manager = PluginManager(
        create_engine(os.getenv("DB_CONNECTION")),
        log_handler=logging.StreamHandler(),
        module_paths=os.getenv("MODULE_PATH", "").split(":"),
    )
    plugin_manager.reload_all_jobs(False)
    plugin_manager.start()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutting down gracefully...")
    finally:
        plugin_manager.stop()
        os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
