import time
from plugin_manager import PluginManager

# PYTHONPATH=path_to/alpha-miner
plugin_manager = PluginManager(
    [
        {
            "package": "src.plugins.worker_plugin.WorkerPlugin",
            "interval": 5,
        },
    ]
)

plugin_manager.start()

# Keep the process alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down...")
