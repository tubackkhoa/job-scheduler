import asyncio
import time
from unittest.mock import MagicMock

import pytest

from models import DAO
from plugin_manager import PluginManager

N_JOBS = 100
timestamps = []


class DummyDAO(DAO):

    def __init__(self):
        mock_session_factory = MagicMock()
        super().__init__(mock_session_factory)
        self.job_config_cache = {1: {"key": "value"}}
        self.plugin_cache = {1: (3, "test_plugin.TestPlugin", None)}

    async def activate_job(self, job_id):
        return True

    async def deactivate_job(self, job_id):
        return True

    async def add_job(self, *args, **kwargs):
        return 0

    async def remove_job(self, job_id):
        return True

    async def get_all_jobs(self):
        return []


class TestPlugin:
    dir = None

    @classmethod
    def schema(cls, ctx):
        return {}

    @classmethod
    def config(cls, ctx, json=None, validate=False):
        return json

    @classmethod
    async def run(cls, ctx, config, logger, render):
        timestamps.append(time.perf_counter())

    @classmethod
    def env(cls):
        return {}

    @classmethod
    def roles(cls):
        return {}

    @classmethod
    def routes(cls):
        return []


@pytest.mark.asyncio
async def test_scheduler_executes_jobs_concurrently():

    timestamps.clear()

    dao = DummyDAO()
    pm = PluginManager(dao)

    pm.manager.register(TestPlugin, "test_plugin.TestPlugin")

    for i in range(N_JOBS):
        pm.add_job_instance(i, False, 3, "test_plugin.TestPlugin")

    pm.start()

    for i in range(N_JOBS):
        await pm.activate_job(i)

    timeout = time.perf_counter() + 5

    while len(timestamps) < N_JOBS:
        if time.perf_counter() > timeout:
            pytest.fail("Timeout waiting for jobs to execute")
        await asyncio.sleep(0.001)

    pm.stop()

    timestamps.sort()

    max_gap = max(timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps)))

    total_span = timestamps[-1] - timestamps[0]

    # Assertions
    assert len(timestamps) == N_JOBS

    # Jobs should run close together if scheduler concurrency works
    assert total_span < 0.5

    # No huge scheduling gaps
    assert max_gap < 0.1
