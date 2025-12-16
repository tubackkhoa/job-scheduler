# PYTHONPATH=path_to/alpha-miner
import time

from sqlalchemy import Column, Integer
from models import Job
from plugin_manager import PluginManager


plugin_manager = PluginManager()

plugin_manager.start()

# Keep the process alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down...")
