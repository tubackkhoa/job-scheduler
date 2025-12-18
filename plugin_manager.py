import asyncio
import importlib
import json
import logging
import sys
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor
import pluggy
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import (
    JobExecutionEvent,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_SUBMITTED,
    EVENT_JOB_ADDED,
    EVENT_JOB_REMOVED,
)
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

from models import Job, Plugin

PROJECT_NAME = "alpha-miner"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)


class PluginSpec:
    @hookspec
    def schema(cls) -> dict[str, Any]: ...

    @hookspec
    def config(cls, json: Optional[dict[str, Any]] = None) -> BaseModel: ...

    @hookspec
    async def run(cls, config: BaseModel, logger: logging.Logger) -> bool: ...


class PluginManager:
    """
    Manages plugin loading/unloading, job scheduling, and execution
    """

    def __init__(
        self,
        db_connection: str = "sqlite:///data/apscheduler_events.db",
        module_paths: Optional[list[str]] = None,
        log_handler: Optional[logging.Handler] = None,
        scheduler_kwargs: Optional[dict] = None,
        max_workers: int = 20,
    ) -> None:

        # add module path to sys.path to load more plugins
        if module_paths:
            for path in module_paths:
                if path and path not in sys.path:
                    sys.path.insert(0, path)

        self.manager = pluggy.PluginManager(PROJECT_NAME)
        self.db_engine = create_engine(db_connection)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        # Pass any additional user-provided args
        self.scheduler = AsyncIOScheduler(**(scheduler_kwargs or {}))
        self.scheduler.add_listener(
            self.job_listener,
            EVENT_JOB_ADDED
            | EVENT_JOB_REMOVED
            | EVENT_JOB_SUBMITTED
            | EVENT_JOB_EXECUTED
            | EVENT_JOB_ERROR,
        )

        self.manager.add_hookspecs(PluginSpec)
        self.log_handler = log_handler

        # Register all plugins from the database
        all_plugins = self.get_all_plugins()
        look_up = {}
        for plugin in all_plugins:
            self.load_plugin(str(plugin.package))
            look_up[plugin.id] = plugin
        # verify plugin implementation
        self.manager.check_pending()

        all_jobs = self.get_all_jobs()
        for job in all_jobs:
            self.add_job_instance(job.user_id, look_up[job.plugin_id])  # type: ignore

    def job_listener(self, event: JobExecutionEvent):
        level = logging.INFO
        message = ""
        if event.code == EVENT_JOB_ADDED:
            message = f"Job added to scheduler (jobstore: {event.jobstore})"
        elif event.code == EVENT_JOB_REMOVED:
            message = "Job removed from scheduler"
        elif event.code == EVENT_JOB_SUBMITTED:
            message = f"Job submitted to executor (scheduled: {getattr(event, 'scheduled_run_times')})"
        elif event.code == EVENT_JOB_EXECUTED:
            message = f"Job executed successfully (return value: {event.retval})"
        elif event.code == EVENT_JOB_ERROR:
            level = logging.ERROR
            message = f"Job failed with exception: {event.exception}"

        log_event = logging.LogRecord(
            event.job_id,
            level,
            pathname="",
            lineno=-1,
            args=None,
            exc_info=None,
            msg=message,
        )

        if self.log_handler:
            self.log_handler.emit(log_event)
        # TODO: other logic ....

    def start(self):
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
        self.executor.shutdown(wait=True)

    def unload_module(self, module_path: str):
        # Remove module and submodules from sys.modules cache to reload cleanly
        modules_to_remove = [
            name
            for name in sys.modules
            if name == module_path or name.startswith(module_path + ".")
        ]
        for mod_name in modules_to_remove:
            del sys.modules[mod_name]

    def get_plugin_names(self):
        return [name for name, _ in self.manager.list_name_plugin()]

    def get_plugin_instance(self, package: str) -> Optional[PluginSpec]:
        return self.manager.get_plugin(package)

    @staticmethod
    def _execute_plugin_in_thread(
        plugin: PluginSpec, config: BaseModel, logger: logging.Logger
    ):
        try:
            return asyncio.run(plugin.run(config, logger))
        except Exception as e:
            logger.error(f"Critical error in plugin thread: {e}", exc_info=True)
            return False

    async def run_plugin_job(self, package: str, plugin_id: int, user_id: int):
        """
        Wrapper to run a plugin's 'run' method synchronously within asyncio event loop,
        fetching config from the active job for the user/plugin.
        """
        plugin = self.get_plugin_instance(package)
        if plugin is None:
            return None

        with Session(self.db_engine) as session:
            job = (
                session.query(Job)
                .filter(
                    Job.plugin_id == plugin_id,
                    Job.user_id == user_id,
                    Job.active == 1,
                )
                .first()
            )
            if job is None:
                # No active job means no config to run this plugin instance for this user
                return None

        config = plugin.config(json.loads(str(job.config)))
        scheduler_job_id = f"{package}/{user_id}"
        logger = logging.getLogger(scheduler_job_id)

        loop = asyncio.get_running_loop()
        # EXECUTE IN YOUR DEDICATED POOL
        return await loop.run_in_executor(
            self.executor, self._execute_plugin_in_thread, plugin, config, logger
        )

    def unload_plugin(self, package: str):
        module_path, _ = package.rsplit(".", 1)

        existing_plugin = self.manager.get_plugin(package)
        if existing_plugin:
            self.manager.unregister(existing_plugin, package)

        self.unload_module(module_path)

    def load_plugin(self, package: str, override: bool = False):
        module_path, class_name = package.rsplit(".", 1)

        if override:
            self.unload_plugin(package)

        plugin: PluginSpec | None = self.manager.get_plugin(package)
        if plugin is None:
            module = importlib.import_module(module_path)
            plugin = getattr(module, class_name)
            self.manager.register(plugin, package)

        return plugin

    def add_job(
        self,
        user_id: int,
        plugin_id: int,
        config: str,
        description: Optional[str] = None,
    ):
        with Session(self.db_engine) as session:
            job = Job(
                user_id=user_id,
                plugin_id=plugin_id,
                config=config,
                active=0,
                description=description,
            )
            session.add(job)
            session.commit()

            plugin = session.get(Plugin, plugin_id)
            assert plugin is not None
            self.add_job_instance(user_id, plugin)

    def add_job_instance(self, user_id: int, plugin: Plugin):
        scheduler_job_id = f"{plugin.package}/{user_id}"
        if self.scheduler.get_job(scheduler_job_id) is None:

            self.scheduler.add_job(
                self.run_plugin_job,
                "interval",
                seconds=plugin.interval,
                args=[plugin.package, plugin.id, user_id],
                id=scheduler_job_id,
                name=scheduler_job_id,
            )

            # add handler for this logger
            logger = logging.getLogger(scheduler_job_id)
            if self.log_handler:
                logger.addHandler(self.log_handler)

    def update_job(self, id: int, config: str, description: Optional[str] = None):
        with Session(self.db_engine) as session:
            job_item = session.get(Job, id)
            if job_item:
                job_item.config = config  # type: ignore
                if description:
                    job_item.description = description  # type: ignore
                session.commit()

    def remove_job(self, job_id: int):
        with Session(self.db_engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return

            session.delete(job)
            session.commit()

            # If no other jobs remain for this user/plugin, remove scheduled job
            remaining_jobs = (
                session.query(Job)
                .filter(
                    Job.plugin_id == job.plugin_id,
                    Job.user_id == job.user_id,
                )
                .count()
            )
            if remaining_jobs == 0:
                plugin = session.get(Plugin, job.plugin_id)
                assert plugin is not None
                scheduler_job_id = f"{plugin.package}/{job.user_id}"
                self.scheduler.remove_job(scheduler_job_id)

                # remove handler for this logger
                logger = logging.getLogger(scheduler_job_id)
                if self.log_handler:
                    logger.removeHandler(self.log_handler)

    def activate_job(self, job_id: int):
        with Session(self.db_engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return

            # Deactivate other active jobs for the same user/plugin
            session.execute(
                update(Job)
                .where(
                    Job.active == 1,
                    Job.plugin_id == job.plugin_id,
                    Job.user_id == job.user_id,
                )
                .values(active=0)
            )

            job.active = 1  # type: ignore
            session.commit()

    def deactivate_job(self, job_id: int):
        with Session(self.db_engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return

            job.active = 0  # type: ignore
            session.commit()

    def get_jobs_for_plugin_and_user(self, plugin_id: int, user_id: int):
        with Session(self.db_engine) as session:
            jobs = (
                session.query(Job)
                .filter(
                    Job.plugin_id == plugin_id,
                    Job.user_id == user_id,
                )
                .all()
            )
            return jobs

    def get_plugin_by_id(self, id: int):
        with Session(self.db_engine) as session:
            return session.get(Plugin, id)

    def get_job_by_id(self, id: int):
        with Session(self.db_engine) as session:
            return session.get(Job, id)

    def get_all_plugins(self):
        with Session(self.db_engine) as session:
            plugins = session.query(Plugin).all()
            return plugins

    def get_all_jobs(self):
        with Session(self.db_engine) as session:
            jobs = session.query(Job).all()
            return jobs
