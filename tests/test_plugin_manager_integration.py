import asyncio
import logging
import dotenv
from sqlalchemy import create_engine
from create_data import create_data
from plugin_manager import PluginManager

import pytest

# Load environment variables from .env file
dotenv.load_dotenv()


@pytest.mark.asyncio
async def test_plugin_manager_with_sample_plugin():
    db_engine = create_engine("sqlite:///:memory:?check_same_thread=false")

    # Prepare test data for a sample plugin package
    package = "plugins.sample_plugin.Plugin"
    plugin_data = [
        {
            "package": package,
            "interval": 1,
            "description": "Sample plugin version 0.1.0 running frequently.",
        }
    ]

    create_data(db_engine, session_ids=[1], plugin_data=plugin_data)

    # Setup PluginManager with in-memory DB and basic logging
    plugin_manager = PluginManager(
        db_engine,
        log_handler=logging.StreamHandler(),
        scheduler_kwargs={
            # You can configure jobstores here if needed for integration tests
            # "jobstores": {"default": SQLAlchemyJobStore(url="sqlite:///data/jobs.sqlite")}
        },
    )

    # Load plugins and start the scheduler
    plugin_manager.reload_all_jobs()
    plugin_manager.start()

    # Run the scheduler for a short period to simulate activity (e.g., 2 seconds)
    await asyncio.sleep(2)

    # Clean up: stop scheduler
    plugin_manager.stop()

    # Optionally assert plugin loaded and jobs scheduled (basic sanity checks)
    assert package in PluginManager.get_plugin_names()

    # Check if jobs are scheduled - this depends on your implementation detail
    # For example, you might want to check scheduler jobs count:
    jobs = plugin_manager.scheduler.get_jobs()
    assert len(jobs) > 0
