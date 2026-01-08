import asyncio
from ctypes import ArgumentError
import importlib
import json
import logging
import sys
from typing import Any, Dict, Optional
import pluggy
from pydantic import BaseModel
from apscheduler.util import undefined
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from jinja2 import Environment
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from models import Job, Plugin
from pip._internal.cli.main import main as pip_main
import zipfile
import tarfile
import glob
import shutil
import os

PROJECT_NAME = "job-scheduler"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)

scheduler_logger = logging.getLogger(PROJECT_NAME)
scheduler_logger.addHandler(logging.StreamHandler())


def extract_package_files(target_dir: str) -> bool:
    # Find supported archives (prefer wheel over tar.gz)
    archives = glob.glob(os.path.join(target_dir, "*.whl")) or glob.glob(
        os.path.join(target_dir, "*.tar.gz")
    )

    if not archives:
        scheduler_logger.info("No archive found to extract.")
        return False

    archive_path = archives[0]
    scheduler_logger.info(f"Extracting archive: {archive_path}")

    # Extract archive
    if archive_path.endswith(".whl"):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(target_dir)
    else:  # .tar.gz
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(target_dir)

    os.remove(archive_path)

    # Remove *.dist-info directories
    for dist_info in glob.glob(os.path.join(target_dir, "*.dist-info")):
        scheduler_logger.info(f"Removing dist-info folder: {dist_info}")
        shutil.rmtree(dist_info, ignore_errors=True)

    # Get non-junk entries
    entries = [
        e for e in os.listdir(target_dir) if e != "__pycache__" and not e.endswith(".dist-info")
    ]

    # Flatten single nested directory
    if len(entries) == 1:
        nested_dir = os.path.join(target_dir, entries[0])
        if os.path.isdir(nested_dir):
            scheduler_logger.info(f"Flattening directory: {nested_dir} → {target_dir}")
            for name in os.listdir(nested_dir):
                src = os.path.join(nested_dir, name)
                dst = os.path.join(target_dir, name)

                if os.path.exists(dst):
                    shutil.rmtree(dst) if os.path.isdir(dst) else os.remove(dst)

                shutil.move(src, dst)

            os.rmdir(nested_dir)

    scheduler_logger.info("Extraction and cleanup complete.")
    return True


class PluginSpec:

    @hookspec
    def env(cls) -> Environment: ...

    @hookspec
    def schema(cls) -> dict[str, Any]: ...

    @hookspec
    def config(cls, json: Optional[dict[str, Any]] = None) -> BaseModel: ...

    @hookspec
    async def run(cls, config: BaseModel, logger: logging.Logger) -> Any: ...


class PluginManager:
    """
    Manages plugin loading/unloading, job scheduling, and execution
    """

    # static cache of job configs, to remove access to database
    # TODO: because schedule only make sure 1 job is added to queue, but can not verify job is done on a machine
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
        db_engine: Engine | str,
        module_paths: Optional[list[str]] = None,
        plugin_path="plugins",
        log_handler: Optional[logging.Handler] = None,
        scheduler_kwargs: Optional[dict] = None,
    ) -> None:

        # add module path to sys.path to load more plugins
        if module_paths:
            for path in module_paths:
                if path and path not in sys.path:
                    sys.path.insert(0, path)
        self.plugin_path = plugin_path
        self.db_engine = create_engine(db_engine) if isinstance(db_engine, str) else db_engine
        # Pass any additional user-provided args
        self.scheduler = AsyncIOScheduler(**(scheduler_kwargs or {}))
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
            print(f"Loading plugin: {plugin.package}")
            try:
                self.load_plugin(plugin.package)
            except Exception as e:
                logging.error(f"Error loading plugin: {e}", exc_info=True)
                continue
            look_up[plugin.id] = plugin

        all_jobs = self.get_all_jobs()

        for job in all_jobs:
            self.add_job_instance(job, look_up[job.plugin_id])

    def start(self):
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def download_package(self, name: str, version: str) -> bool:
        if not version:
            raise ArgumentError(f"Please provide package with a version, e.g. 1.2.3")
        version_underscore = version.replace(".", "_")
        target_dir = f"{self.plugin_path}/{name}@{version_underscore}"
        os.makedirs(target_dir, exist_ok=True)

        # Construct the download arguments exactly like the pip CLI
        args = [
            "download",  # pip command to download
            f"{name}=={version}",
            "--dest",
            target_dir,
            "--no-deps",  # Optional: just the main package, no dependencies
        ]

        scheduler_logger.info(f"Downloading {name}=={version} into {target_dir} ...")
        # Call pip's internal main function with the args
        result = pip_main(args)

        if result == 0:
            return extract_package_files(target_dir)
        else:
            scheduler_logger.info(f"Download failed with exit code {result}")

        return False

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
        # Ensure logger level is set (default to INFO if not set)
        if logger.level == logging.NOTSET:
            logger.setLevel(logging.INFO)

        try:
            retval = asyncio.run(plugin.run(config, logger))
            # logger.info(f"Job executed successfully (return value: {retval})")
            return retval
        except Exception as e:
            logger.error(f"Job failed with exception: {e}", exc_info=True)

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
                # Raise exception to prevent saving invalid plugin to database
                raise RuntimeError(f"Failed to load plugin '{package}': {str(e)}") from e

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

        logger = logging.getLogger(job_scheduler_id)
        logger.propagate = False
        if logger.level == logging.NOTSET:
            logger.setLevel(logging.INFO)

        existing_handlers = logger.handlers[:]
        for handler in existing_handlers:
            logger.removeHandler(handler)

        # Add the handler - this handler uses record.name (job_scheduler_id) to determine file
        if self.log_handler:
            if self.log_handler not in logger.handlers:
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

    def remove_jobs(self, job_ids: list[int]):
        """Batch remove multiple jobs from database and scheduler."""
        if not job_ids:
            return
        # Remove jobs from scheduler
        for job_id in job_ids:
            job_scheduler_id = self.get_job_scheduler_id(job_id)
            if self.scheduler.get_job(job_scheduler_id) is not None:
                self.scheduler.remove_job(job_scheduler_id)
            self._active_job_cache.pop(job_id, None)

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

    def delete_plugin(self, plugin_id: int):
        """
        Delete a plugin from the database and unload it from memory.
        Also removes all associated jobs.
        """
        with Session(self.db_engine) as session:
            plugin = session.get(Plugin, plugin_id)
            if not plugin:
                raise ValueError(f"Plugin with id {plugin_id} not found")

            # Get all jobs for this plugin
            jobs = session.query(Job).filter(Job.plugin_id == plugin_id).all()

            # Remove all jobs from scheduler and delete them
            for job in jobs:
                job_scheduler_id = self.get_job_scheduler_id(job.id)
                if self.scheduler.get_job(job_scheduler_id) is not None:
                    self.scheduler.remove_job(job_scheduler_id)
                    self._active_job_cache.pop(job.id, None)

                    # Remove logger handlers
                    logger = logging.getLogger(job_scheduler_id)
                    logger.handlers.clear()
                session.delete(job)

            # Unload plugin from memory
            self.unload_plugin(plugin.package)

            # Delete plugin from database
            session.delete(plugin)
            session.commit()
