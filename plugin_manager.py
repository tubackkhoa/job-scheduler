import asyncio
import importlib
import json
import logging
import sys
from typing import Any, Dict, Optional
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
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from models import Job, Plugin

PROJECT_NAME = "job-scheduler"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)

scheduler_logger = logging.getLogger(__name__)
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

        self.manager = pluggy.PluginManager(PROJECT_NAME)
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

        self.manager.add_hookspecs(PluginSpec)
        self.log_handler = log_handler

        # Register all plugins from the database
        all_plugins = self.get_all_plugins()
        look_up = {}
        for plugin in all_plugins:
            self.load_plugin(str(plugin.package))
            look_up[plugin.id] = plugin

        all_jobs = self.get_all_jobs()

        self._active_job_cache: Dict[str, str] = {}
        for job in all_jobs:
            self.add_job_instance(job, look_up[job.plugin_id])  # type: ignore

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

    def start(self):
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def reload_module(self, module_path: str):
        root, sep, _ = module_path.partition(".")
        prefix = root + sep

        # reload all sub modules, later import root module to make sure in right order
        for name, module in list(sys.modules.items()):
            if name.startswith(prefix):
                importlib.reload(module)

        root_module = sys.modules.get(root)
        if root_module:
            importlib.reload(root_module)

    def get_plugin_names(self):
        return [name for name, _ in self.manager.list_name_plugin()]

    def get_plugin_instance(self, package: str) -> Optional[PluginSpec]:
        return self.manager.get_plugin(package)

    def run_plugin_job(self, package: str, scheduler_job_id: str):
        """
        Wrapper to run a plugin's 'run' method synchronously within asyncio event loop,
        fetching config from the active job for the user/plugin.
        """
        plugin = self.get_plugin_instance(package)
        if plugin is None:
            return None

        job_config = self._active_job_cache.get(scheduler_job_id)

        if job_config is None:
            # No active job means no config to run this plugin instance for this user
            return None

        config = plugin.config(json.loads(job_config))

        logger = logging.getLogger(scheduler_job_id)

        return asyncio.run(plugin.run(config, logger))

    def unload_plugin(self, package: str):
        existing_plugin = self.manager.get_plugin(package)
        if existing_plugin:
            self.manager.unregister(existing_plugin, package)

    def load_plugin(self, package: str, override: bool = False):
        module_path, _, class_name = package.rpartition(".")

        if override:
            self.unload_plugin(package)
            self.reload_module(module_path)

        plugin: PluginSpec | None = self.manager.get_plugin(package)
        if plugin is None:
            try:
                module = importlib.import_module(module_path)
                plugin = getattr(module, class_name)
                self.manager.register(plugin, package)
            except Exception as e:
                # show error to terminal to check but keep running
                scheduler_logger.error(e, exc_info=True)

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
            self.add_job_instance(job, plugin)

    def add_job_instance(self, job: Job, plugin: Plugin):
        scheduler_job_id = f"{plugin.id}/{job.user_id}"

        if self.scheduler.get_job(scheduler_job_id) is None:
            # make sure job run 1 time
            self.scheduler.add_job(
                self.run_plugin_job,
                "interval",
                seconds=plugin.interval,
                args=[plugin.package, scheduler_job_id],
                next_run_time=None,
                id=scheduler_job_id,
                name=scheduler_job_id,
                coalesce=True,
                max_instances=1,
            )

            # add handler for this logger
            logger = logging.getLogger(scheduler_job_id)
            if self.log_handler:
                logger.addHandler(self.log_handler)

        # active job
        if bool(job.active):
            self._active_job_cache[scheduler_job_id] = str(job.config)
            self.scheduler.resume_job(scheduler_job_id)

    def update_job(self, id: int, config: str, description: Optional[str] = None):
        with Session(self.db_engine) as session:
            job = session.get(Job, id)
            if job:
                job.config = config  # type: ignore
                if description:
                    job.description = description  # type: ignore
                # update the active config
                if bool(job.active):
                    scheduler_job_id = f"{job.plugin_id}/{job.user_id}"
                    self._active_job_cache[scheduler_job_id] = str(job.config)
                session.commit()

    def remove_job(self, job_id: int):
        with Session(self.db_engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return
            plugin_id = job.plugin_id
            user_id = job.user_id
            scheduler_job_id = f"{plugin_id}/{user_id}"
            session.delete(job)
            session.commit()

            # If no other jobs remain for this user/plugin, remove scheduled job
            remaining_jobs = (
                session.query(Job)
                .filter(
                    Job.plugin_id == plugin_id,
                    Job.user_id == user_id,
                )
                .count()
            )
            if remaining_jobs == 0:
                self.scheduler.remove_job(scheduler_job_id)
                self._active_job_cache.pop(scheduler_job_id)

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

            # this is active config
            scheduler_job_id = f"{job.plugin_id}/{job.user_id}"
            self._active_job_cache[scheduler_job_id] = str(job.config)
            self.scheduler.resume_job(scheduler_job_id)

    def deactivate_job(self, job_id: int):
        with Session(self.db_engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return

            # so no config is active
            if bool(job.active):
                scheduler_job_id = f"{job.plugin_id}/{job.user_id}"
                self._active_job_cache.pop(scheduler_job_id)
                self.scheduler.pause_job(scheduler_job_id)

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
