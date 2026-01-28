import asyncio
import logging
import dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models import DAO
from .create_data import create_data
from plugin_manager import PluginManager

import pytest

# Load environment variables from .env file
dotenv.load_dotenv()


@pytest.mark.asyncio
async def test_plugin_manager_with_sample_plugin():

    db_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:?check_same_thread=false", echo=False
    )

    # Prepare test data for a sample plugin package
    package = "plugins.sample_plugin.Plugin"
    plugin_data = [
        {
            "package": package,
            "interval": 1,
            "description": "Sample plugin version 0.1.0 running frequently.",
        }
    ]

    await create_data(
        db_engine,
        session_ids=[1],
        plugin_data=plugin_data,
    )

    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Setup PluginManager with in-memory DB and basic logging
    plugin_manager = PluginManager(
        DAO(session_factory),
        log_handler=logging.StreamHandler(),
        scheduler_kwargs={
            # You can configure jobstores here if needed for integration tests
            # "jobstores": {"default": SQLAlchemyJobStore(url="sqlite:///data/jobs.sqlite")}
        },
    )

    # Load plugins and start the scheduler
    await plugin_manager.reload_all_jobs()
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
