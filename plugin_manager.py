import asyncio
import importlib
import json
import logging
import sys
from typing import Any, Dict, Optional
import pluggy
from pydantic import BaseModel
from apscheduler.util import undefined
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from apscheduler.events import (
    JobExecutionEvent,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_SUBMITTED,
    EVENT_JOB_ADDED,
    EVENT_JOB_REMOVED,
)
from models import Job, Plugin

PROJECT_NAME = "job-scheduler"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)

scheduler_logger = logging.getLogger(PROJECT_NAME)
scheduler_logger.addHandler(logging.StreamHandler())


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

    # static cache of job configs, to remove access to database
    # TODO: move this to redis to cache across multiple workers, later can implement locking to prevent multiple runs of same job
    # @classmethod
    # def run_plugin_job(cls, job_id: int):
    #     lock = cls.redis_client.lock(
    #         f"lock:{PROJECT_NAME}:{job_id}",
    #         timeout=plugin.interval * 2,
    #         blocking=False,
    #     )
    #     if not lock.acquire():
    #         return
    #     try:
    #         return asyncio.run(plugin.run(config, logger))
    #     finally:
    #         lock.release()
    _active_job_cache: Dict[int, str] = {}
    # static pluggy manager, so that all pluginmanager share the same plugins
    manager = pluggy.PluginManager(PROJECT_NAME)
    manager.add_hookspecs(PluginSpec)

    def __init__(
        self,
        db_engine: Engine,
        module_paths: Optional[list[str]] = None,
        log_handler: Optional[logging.Handler] = None,
        scheduler_kwargs: Optional[dict] = None,
    ) -> None:

        # add module path to sys.path to load more plugins
        if module_paths:
            for path in module_paths:
                if path and path not in sys.path:
                    sys.path.insert(0, path)

        self.db_engine = db_engine

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

        self.log_handler = log_handler

    # reload all jobs from database
    def reload_all_jobs(self):
        """
        Reload all jobs from the database into the scheduler.
        Useful for initial load or after a restart.
        """
        # Register all plugins from the database
        all_plugins = self.get_all_plugins()
        look_up = {}
        for plugin in all_plugins:
            self.load_plugin(plugin.package)
            look_up[plugin.id] = plugin

        all_jobs = self.get_all_jobs()

        for job in all_jobs:
            self.add_job_instance(job, look_up[job.plugin_id])

    def start(self):
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def job_listener(self, event: JobExecutionEvent):
        level = logging.INFO
        message = ""
        if event.code == EVENT_JOB_ADDED:
            message = f"Job added to scheduler (jobstore: {event.jobstore})"
        elif event.code == EVENT_JOB_REMOVED:
            message = "Job removed from scheduler"
        elif event.code == EVENT_JOB_SUBMITTED:
            message = (
                f"Job submitted to executor (scheduled: {getattr(event, 'scheduled_run_times')})"
            )
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

    @staticmethod
    def get_job_scheduler_id(job_id: int) -> str:
        return f"{PROJECT_NAME}.job.{job_id}"

    @staticmethod
    def reload_module(module_path: str):
        root, sep, _ = module_path.partition(".")
        prefix = root + sep

        # reload all sub modules, later import root module to make sure in right order
        for name, module in list(sys.modules.items()):
            if name.startswith(prefix):
                importlib.reload(module)

        root_module = sys.modules.get(root)
        if root_module:
            importlib.reload(root_module)

    @classmethod
    def get_plugin_names(cls):
        return [name for name, _ in cls.manager.list_name_plugin()]

    @classmethod
    def get_plugin_instance(cls, package: str) -> Optional[PluginSpec]:
        return cls.manager.get_plugin(package)

    @classmethod
    def run_plugin_job(cls, package: str, job_id: int):
        """
        Wrapper to run a plugin's 'run' method asynchronously,
        fetching config from the active job for the user/plugin.
        """
        plugin = cls.get_plugin_instance(package)

        if plugin is None:
            return None

        job_config = cls._active_job_cache.get(job_id)

        if job_config is None:
            # No active job means no config to run this plugin instance for this user
            return None

        config = plugin.config(json.loads(job_config))

        job_scheduler_id = cls.get_job_scheduler_id(job_id)

        logger = logging.getLogger(job_scheduler_id)
        # prevent log propagation to root logger
        logger.propagate = False
        return asyncio.run(plugin.run(config, logger))

    @classmethod
    def unload_plugin(cls, package: str):
        existing_plugin = cls.manager.get_plugin(package)
        if existing_plugin:
            cls.manager.unregister(existing_plugin, package)

    @classmethod
    def load_plugin(cls, package: str, override: bool = False):
        module_path, _, class_name = package.rpartition(".")

        if override:
            cls.unload_plugin(package)
            cls.reload_module(module_path)

        plugin: PluginSpec | None = cls.manager.get_plugin(package)
        if plugin is None:
            try:
                module = importlib.import_module(module_path)
                plugin = getattr(module, class_name)
                cls.manager.register(plugin, package)
            except Exception as e:
                # show error to terminal to check but keep running
                scheduler_logger.error(e, exc_info=True)

        return plugin

    def add_plugin(self, package: str, interval: int, description: Optional[str] = None) -> int:
        self.load_plugin(package)
        # Insert into DB
        with Session(self.db_engine) as session:
            plugin_row = Plugin(
                package=package,
                interval=interval,
                description=description,
            )

            session.add(plugin_row)
            session.flush()  # get ID
            plugin_id = plugin_row.id
            session.commit()
            return plugin_id

    def add_job(
        self,
        session_id: int,
        plugin_id: int,
        config: str,
        description: Optional[str] = None,
    ):
        with Session(self.db_engine) as session:
            job = Job(
                session_id=session_id,
                plugin_id=plugin_id,
                config=config,
                active=False,
                description=description,
            )
            session.add(job)
            session.commit()

            plugin = session.get(Plugin, plugin_id)
            assert plugin is not None
            self.add_job_instance(job, plugin)

    def add_job_instance(self, job: Job, plugin: Plugin):

        # update cache
        self._active_job_cache[job.id] = job.config

        job_scheduler_id = self.get_job_scheduler_id(job.id)
        if self.scheduler.get_job(job_scheduler_id) is not None:
            return  # job already exists

        # add handler for this logger
        logger = logging.getLogger(job_scheduler_id)
        if self.log_handler:
            logger.addHandler(self.log_handler)

        # replace_existing allow override
        self.scheduler.add_job(
            self.run_plugin_job,
            "interval",
            seconds=plugin.interval,
            args=[plugin.package, job.id],
            next_run_time=undefined if job.active else None,
            id=job_scheduler_id,
            name=job_scheduler_id,
            coalesce=True,
            max_instances=1,  # Single job for each id
            replace_existing=True,
        )

    def update_job(self, id: int, config: str, description: Optional[str] = None):
        with Session(self.db_engine) as session:
            job = session.get(Job, id)
            if job:
                job.config = config
                if description:
                    job.description = description
                self._active_job_cache[job.id] = job.config
                session.commit()

    def remove_job(self, job_id: int):
        with Session(self.db_engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return
            session.delete(job)
            session.commit()

        # Remove the specific job from scheduler
        job_scheduler_id = self.get_job_scheduler_id(job_id)
        if self.scheduler.get_job(job_scheduler_id) is not None:
            self.scheduler.remove_job(job_scheduler_id)
            self._active_job_cache.pop(job_id, None)

            # remove all handlers for this logger to save memory
            logger = logging.getLogger(job_scheduler_id)
            logger.handlers.clear()

    def activate_job(self, job_id: int):
        with Session(self.db_engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return

            job.active = True
            session.commit()

            # Resume the job
            job_scheduler_id = self.get_job_scheduler_id(job_id)
            self.scheduler.resume_job(job_scheduler_id)

    def deactivate_job(self, job_id: int):
        with Session(self.db_engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return

            job.active = False
            session.commit()

            # Pause the job
            job_scheduler_id = self.get_job_scheduler_id(job_id)
            self.scheduler.pause_job(job_scheduler_id)

    def get_jobs_for_plugin_and_user(self, plugin_id: int, session_id: int):
        with Session(self.db_engine) as session:
            jobs = (
                session.query(Job)
                .filter(
                    Job.plugin_id == plugin_id,
                    Job.session_id == session_id,
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
