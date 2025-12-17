import asyncio
import importlib
import json
import logging
import sys
from typing import Any, Callable, Optional

import pluggy
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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


class JobLogHandler(logging.Handler):
    def __init__(self, log_callback):
        super().__init__()
        self.log_callback = log_callback

    def emit(self, record: logging.LogRecord):
        if self.log_callback is None:
            return

        log_entry = self.format(record)

        log_event = {
            "job_id": record.name,
            "level": record.levelname,
            "message": log_entry,
        }
        self.log_callback(log_event)


class PluginManager:
    """
    Manages plugin loading/unloading, job scheduling, and execution
    """

    def __init__(
        self,
        db_connection: str = "sqlite:///data/apscheduler_events.db",
        log_callback: Optional[Callable[[dict], Any]] = None,
        scheduler_kwargs: Optional[dict] = None,
    ) -> None:
        self.plugin_manager = pluggy.PluginManager(PROJECT_NAME)
        self.engine = create_engine(db_connection)
        # Pass any additional user-provided args
        self.scheduler = AsyncIOScheduler(**(scheduler_kwargs or {}))
        self.plugin_manager.add_hookspecs(PluginSpec)
        self.log_handler = JobLogHandler(log_callback)

        # Register all plugins from the database
        all_plugins = self.get_all_plugins()
        look_up = {}
        for plugin in all_plugins:
            self.load_plugin(str(plugin.package))
            look_up[plugin.id] = plugin

        self.plugin_manager.check_pending()

        all_jobs = self.get_all_jobs()
        for job in all_jobs:
            self.add_job_instance(job.user_id, look_up[job.plugin_id])  # type: ignore

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()

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
        return [name for name, _ in self.plugin_manager.list_name_plugin()]

    def get_plugin_instance(self, package: str) -> Optional[PluginSpec]:
        return self.plugin_manager.get_plugin(package)

    async def run_plugin_job_sync(self, package: str, plugin_id: int, user_id: int):
        """
        Wrapper to run a plugin's 'run' method synchronously within asyncio event loop,
        fetching config from the active job for the user/plugin.
        """
        plugin = self.get_plugin_instance(package)
        if plugin is None:
            return None

        with Session(self.engine) as session:
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
            job_id = f"{package}/{user_id}"
            logger = logging.getLogger(job_id)
            return await plugin.run(config, logger)

    def unload_plugin(self, package: str):
        module_path, _ = package.rsplit(".", 1)

        existing_plugin = self.plugin_manager.get_plugin(package)
        if existing_plugin:
            self.plugin_manager.unregister(existing_plugin, package)

        self.unload_module(module_path)

    def load_plugin(self, package: str, override: bool = False):
        module_path, class_name = package.rsplit(".", 1)

        if override:
            self.unload_plugin(package)

        plugin: PluginSpec | None = self.plugin_manager.get_plugin(package)
        if plugin is None:
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            self.plugin_manager.register(plugin_class, package)

        return plugin

    def add_job(
        self,
        user_id: int,
        plugin_id: int,
        config: str,
        description: Optional[str] = None,
    ):
        with Session(self.engine) as session:
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
        job_id = f"{plugin.package}/{user_id}"
        if self.scheduler.get_job(job_id) is None:

            self.scheduler.add_job(
                self.run_plugin_job_sync,
                "interval",
                seconds=plugin.interval,
                args=[plugin.package, plugin.id, user_id],
                id=job_id,
            )

            # add handler for this logger
            logger = logging.getLogger(job_id)
            logger.addHandler(self.log_handler)

    def update_job(self, id: int, config: str, description: Optional[str] = None):
        with Session(self.engine) as session:
            job_item = session.get(Job, id)
            if job_item:
                job_item.config = config  # type: ignore
                if description:
                    job_item.description = description  # type: ignore
                session.commit()

    def remove_job(self, job_id: int):
        with Session(self.engine) as session:
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
                logger.removeHandler(self.log_handler)

    def activate_job(self, job_id: int):
        with Session(self.engine) as session:
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
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return

            job.active = 0  # type: ignore
            session.commit()

    def get_jobs_for_plugin_and_user(self, plugin_id: int, user_id: int):
        with Session(self.engine) as session:
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
        with Session(self.engine) as session:
            return session.get(Plugin, id)

    def get_job_by_id(self, id: int):
        with Session(self.engine) as session:
            return session.get(Job, id)

    def get_all_plugins(self):
        with Session(self.engine) as session:
            plugins = session.query(Plugin).all()
            return plugins

    def get_all_jobs(self):
        with Session(self.engine) as session:
            jobs = session.query(Job).all()
            return jobs
