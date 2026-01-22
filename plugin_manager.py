import asyncio
import importlib
import logging
import sys

from typing import Any, Callable, Concatenate, Optional

import pluggy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.util import undefined
from casbin.enforcer import Enforcer
from pydantic import BaseModel

from auth import User
from enforcer import (
    ADMIN_ROLE,
    ExecutionContext,
)
from models import DAO, Plugin
from renderer import Renderer

PROJECT_NAME = "job-scheduler"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)

scheduler_logger = logging.getLogger(PROJECT_NAME)
scheduler_logger.addHandler(logging.StreamHandler())


class PluginSpec:

    @hookspec
    def env(cls) -> dict[str, Any]: ...

    @hookspec
    def schema(cls, ctx: ExecutionContext) -> dict[str, Any]: ...

    @hookspec
    def config(
        cls,
        ctx: ExecutionContext,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ) -> BaseModel: ...

    @hookspec
    async def run(
        cls,
        ctx: ExecutionContext,
        config: BaseModel,
        logger: logging.Logger,
        render: Callable[
            Concatenate[ExecutionContext, str, dict[str, Any], ...],
            Any,
        ],
    ) -> Any: ...

    @hookspec
    def roles(cls) -> dict[str, set[str]]: ...

    @hookspec
    async def install(cls) -> bool: ...

    @hookspec
    async def uninstall(cls) -> bool: ...

    @hookspec
    def validate(cls, config: BaseModel) -> None:
        """
        Optional hook for validating job configuration before saving.
        Should raise an exception if validation fails.
        """
        ...


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

    enforcer: Optional[Enforcer] = None

    # static pluggy manager, so that all pluginmanager share the same plugins
    manager = pluggy.PluginManager(PROJECT_NAME)
    manager.add_hookspecs(PluginSpec)

    def __init__(
        self,
        dao: DAO,
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
        self.dao = dao
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
        ctx = self.create_ctx(User(0, frozenset({ADMIN_ROLE})))
        all_plugins = self.dao.get_all_plugins(ctx)
        look_up = {}
        for plugin in all_plugins:
            scheduler_logger.info(f"Loading plugin: {plugin.package}")
            try:
                self.load_plugin(plugin.package)
            except Exception as e:
                logging.error(f"Error loading plugin: {e}", exc_info=True)
                continue
            look_up[plugin.id] = plugin

        all_jobs = self.dao.get_all_jobs()
        for job in all_jobs:
            # Populate job config cache so jobs can run after restart
            if job.config:
                DAO.job_config_cache[job.id] = job.config
            self.add_job_instance(job.id, job.active, look_up[job.plugin_id])

    def start(self):
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    @classmethod
    def register_plugin_permissions(cls, package: str, plugin_cls: PluginSpec):
        if not cls.enforcer:
            return
        try:
            mapping = plugin_cls.roles()
            if not isinstance(mapping, dict):
                return
            enforcer = cls.enforcer
            for permission_key, roles in mapping.items():
                # with : to avoid name collision
                permission = f"{package}:{permission_key}"
                for role in roles:
                    # make sure not override by mistake in plugin, even we have make permission non-conflict
                    if role != ADMIN_ROLE and not enforcer.has_policy(role, permission):
                        enforcer.add_policy(role, permission)

        except Exception as ex:
            scheduler_logger.exception(
                "Failed to register plugin permissions",
                extra={"package": package},
            )

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
    def run_plugin_job(cls, package: str, job_id: int, user: User):
        """
        Wrapper to run a plugin's 'run' method asynchronously,
        fetching config from the active job for the user/plugin.
        """
        plugin = cls.get_plugin_instance(package)

        if plugin is None:
            return None

        job_config = DAO.job_config_cache.get(job_id)

        if job_config is None:
            # No active job means no config to run this plugin instance for this user
            return None

        # user from login
        ctx = cls.create_ctx(user, package)

        # do not validate because already save from db
        config = plugin.config(ctx, job_config)

        job_scheduler_id = cls.get_job_scheduler_id(job_id)

        logger = logging.getLogger(job_scheduler_id)
        # prevent log propagation to root logger
        logger.propagate = False
        # Ensure logger level is set (default to INFO if not set)
        if logger.level == logging.NOTSET:
            logger.setLevel(logging.INFO)

        try:

            retval = asyncio.run(plugin.run(ctx, config, logger, Renderer.render))
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
    def create_ctx(cls, user: User, package: Optional[str] = None):
        return ExecutionContext(user, package, cls.enforcer.enforce if cls.enforcer else None)

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
                assert plugin
                cls.manager.register(plugin, package)
            except Exception as e:
                # show error to terminal to check but keep running
                scheduler_logger.error(e, exc_info=True)
                # Raise exception to prevent saving invalid plugin to database
                raise RuntimeError(f"Failed to load plugin '{package}': {str(e)}") from e

        cls.register_plugin_permissions(package, plugin)
        return plugin

    def add_plugin(self, package: str, interval: int, description: Optional[str] = None) -> int:
        # load plugin override module to make sure new code if sharing the same module
        self.load_plugin(package, True)
        # Insert into DB
        return self.dao.add_plugin(package, interval, description)

    def add_job(
        self,
        session_id: int,
        plugin_id: int,
        config: dict[str, Any],
        description: Optional[str] = None,
    ):
        # Get plugin to check for validation
        plugin_model = self.dao.get_plugin(plugin_id)
        assert plugin_model is not None
        
        plugin_instance = self.get_plugin_instance(plugin_model.package)
        if plugin_instance and hasattr(plugin_instance, 'validate'):
            # Parse config and validate if plugin has validate method
            config_dict = json.loads(config)
            parsed_config = plugin_instance.config(config_dict)
            plugin_instance.validate(parsed_config)
        
        # Proceed with saving job
        job_id = self.dao.add_job(session_id, plugin_id, config, description)
        self.add_job_instance(job_id, False, plugin_model)

    def add_job_instance(self, job_id: int, active: bool, plugin: Plugin):

        job_scheduler_id = self.get_job_scheduler_id(job_id)
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
            # TODO: get user_id, and roles from database, the user of course owning the job
            args=[plugin.package, job_id, User(0, frozenset({ADMIN_ROLE}))],
            next_run_time=undefined if active else None,
            id=job_scheduler_id,
            name=job_scheduler_id,
            coalesce=True,
            max_instances=1,  # Single job for each id
            replace_existing=True,
        )

    def remove_job(self, job_id: int):
        self.dao.remove_job(job_id)
        # Remove the specific job from scheduler
        job_scheduler_id = self.get_job_scheduler_id(job_id)
        if self.scheduler.get_job(job_scheduler_id) is not None:
            self.scheduler.remove_job(job_scheduler_id)

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

    def activate_job(self, job_id: int):
        if not self.dao.activate_job(job_id):
            return

        # Resume the job
        job_scheduler_id = self.get_job_scheduler_id(job_id)
        self.scheduler.resume_job(job_scheduler_id)

    def deactivate_job(self, job_id: int):
        if not self.dao.deactivate_job(job_id):
            return

        # Pause the job
        job_scheduler_id = self.get_job_scheduler_id(job_id)
        self.scheduler.pause_job(job_scheduler_id)

    def delete_plugin(self, plugin_id: int):
        """
        Delete a plugin from the database and unload it from memory.
        Also removes all associated jobs.
        """

        # Get all jobs for this plugin
        package, deleted_job_ids = self.dao.delete_plugin(plugin_id)

        # Remove all jobs from scheduler and delete them
        for job_id in deleted_job_ids:
            job_scheduler_id = self.get_job_scheduler_id(job_id)
            if self.scheduler.get_job(job_scheduler_id) is not None:
                self.scheduler.remove_job(job_scheduler_id)

                # Remove logger handlers
                logger = logging.getLogger(job_scheduler_id)
                logger.handlers.clear()

        # Unload plugin from memory
        self.unload_plugin(package)
