import asyncio
import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Optional, cast

import pluggy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.util import undefined
from casbin.enforcer import Enforcer
from pydantic import BaseModel

from auth import UserContext
from enforcer import (
    ADMIN_ROLE,
    ExecutionContext,
)
from models import DAO
from plugins import CodeSchema
from renderer import Renderer


PROJECT_NAME = "job-scheduler"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)

scheduler_logger = logging.getLogger(PROJECT_NAME)
scheduler_logger.addHandler(logging.StreamHandler())

RenderFn = Callable[
    [str, Mapping[str, Any]],
    Awaitable[Any],
]


class PluginSpec:

    dir: Path

    @classmethod
    @hookspec
    def schema(cls, ctx: ExecutionContext) -> dict[str, Any]: ...

    @classmethod
    @hookspec
    def config(
        cls,
        ctx: ExecutionContext,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ) -> BaseModel: ...

    @classmethod
    @hookspec
    async def run(
        cls,
        ctx: ExecutionContext,
        config: BaseModel,
        logger: logging.Logger,
        render: RenderFn,
    ) -> Any: ...

    # events
    @classmethod
    @hookspec
    def on_active_job(cls, ctx: ExecutionContext, json: Optional[dict[str, Any]]): ...

    @classmethod
    @hookspec
    def on_deactive_job(cls, ctx: ExecutionContext, json: Optional[dict[str, Any]]): ...

    # methods that not require ctx to run
    @classmethod
    @hookspec
    def env(cls) -> dict[str, Any]: ...

    @classmethod
    @hookspec
    def roles(cls) -> dict[str, set[str]]: ...

    @classmethod
    @hookspec
    def routes(cls) -> list[tuple[str, CodeSchema]]: ...

    @classmethod
    @hookspec
    async def install(cls) -> bool: ...

    @classmethod
    @hookspec
    async def uninstall(cls) -> bool: ...


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
    hook = cast(PluginSpec, manager.hook)

    routes_cache: dict[str, tuple[set[str], Optional[CodeSchema]]] = {}
    _failed_plugins: dict[str, Exception] = {}

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
    async def reload_all_jobs(self):
        """
        Reload all jobs from the database into the scheduler.
        Useful for initial load or after a restart.
        """
        # Register all plugins from the database
        self._failed_plugins.clear()
        ctx = self.create_ctx(UserContext(0, frozenset({ADMIN_ROLE})))
        # trigger cache load, so that can get user role and job config in memory
        await self.dao.get_all_plugins(ctx)
        await self.dao.get_all_users(ctx)

        all_jobs = await self.dao.get_all_jobs()
        for job in all_jobs:
            if not job.plugin_id in self.dao.plugin_cache:
                continue
            interval, package, _ = self.dao.plugin_cache[job.plugin_id]
            # Plugin will be lazy load so that can reload and fix
            self.add_job_instance(job.id, job.active, interval, package)

    def start(self):
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    @classmethod
    def _iter_plugin_permissions(cls, package: str, plugin_cls: PluginSpec):
        mapping = plugin_cls.roles()
        if not isinstance(mapping, dict):
            return

        for permission_key, roles in mapping.items():
            permission = f"{package}:{permission_key}"
            for role in roles:
                if role != ADMIN_ROLE:
                    yield role, permission

    @classmethod
    def register_plugin_permissions(cls, package: str, plugin_cls: PluginSpec):
        if not cls.enforcer:
            return
        try:
            enforcer = cls.enforcer
            for role, permission in cls._iter_plugin_permissions(package, plugin_cls):
                if not enforcer.has_policy(role, permission):
                    enforcer.add_policy(role, permission)
        except Exception:
            scheduler_logger.exception(
                "Failed to register plugin permissions",
                extra={"package": package},
            )

    @classmethod
    def unregister_plugin_permissions(cls, package: str, plugin_cls: PluginSpec):
        if not cls.enforcer:
            return
        try:
            enforcer = cls.enforcer
            for role, permission in cls._iter_plugin_permissions(package, plugin_cls):
                if enforcer.has_policy(role, permission):
                    enforcer.remove_policy(role, permission)
        except Exception:
            scheduler_logger.exception(
                "Failed to unregister plugin permissions",
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
        if not cls.manager.has_plugin(package):
            try:
                scheduler_logger.info(f"Loading plugin: {package}")
                return cls.load_plugin(package)
            except Exception as e:
                scheduler_logger.exception(f"Error loading plugin: {e}")
                return None

        return cls.manager.get_plugin(package)

    @staticmethod
    def make_render(plugin: PluginSpec, ctx: ExecutionContext) -> RenderFn:
        env = plugin.env()  # ← hook point

        async def render(
            template: str,
            payload: Mapping[str, Any],
            **kwargs: Any,
        ):
            return await Renderer.render(ctx, template, payload, **env, **kwargs)

        return render

    @classmethod
    async def run_plugin_job(cls, package: str, job_id: int, user: UserContext):
        """
        Wrapper to run a plugin's 'run' method asynchronously,
        fetching config from the active job for the user/plugin.
        """
        plugin = cls.get_plugin_instance(package)

        if plugin is None:
            return None

        # only job is active can run
        job_config = DAO.job_config_cache.get(job_id)

        # user from login
        ctx = cls.create_ctx(user, package)

        job_scheduler_id = cls.get_job_scheduler_id(job_id)

        logger = logging.getLogger(job_scheduler_id)
        # prevent log propagation to root logger
        logger.propagate = False
        # Ensure logger level is set (default to INFO if not set)
        if logger.level == logging.NOTSET:
            logger.setLevel(logging.INFO)

        try:
            render_function = cls.make_render(plugin, ctx)
            # do not validate because already save from db
            config = plugin.config(ctx, job_config)
            retval = await plugin.run(ctx, config, logger, render_function)
            # logger.info(f"Job executed successfully (return value: {retval})")
            return retval
        except Exception as e:
            logger.exception(f"Job failed with exception: {e}")

    @classmethod
    def unload_plugin(cls, package: str):
        cls._failed_plugins.pop(package, None)

        existing_plugin = cls.manager.get_plugin(package)
        if existing_plugin:
            # clear data
            cls.unregister_plugin_permissions(package, existing_plugin)
            cls.routes_cache.pop(package, None)
            cls.manager.unregister(existing_plugin, package)

    @classmethod
    def create_ctx(cls, user: UserContext, package: Optional[str] = None):
        return ExecutionContext(user, package, cls.enforcer.enforce if cls.enforcer else None)

    @classmethod
    def load_plugin(cls, package: str, override: bool = False):

        module_path, _, class_name = package.rpartition(".")

        if override:
            cls.unload_plugin(package)
            cls.reload_module(module_path)

        # 🚫 Fast-fail if previously broken, when override it will reset fail plugin
        elif package in cls._failed_plugins:
            raise cls._failed_plugins[package]

        plugin: PluginSpec | None = cls.manager.get_plugin(package)
        if plugin is not None:
            return plugin

        try:
            module = importlib.import_module(module_path)
            plugin = getattr(module, class_name)
            assert plugin
            if module.__file__:
                plugin.dir = Path(module.__file__).resolve().parent
            cls.manager.register(plugin, package)
            cls.register_plugin_permissions(package, plugin)

            # update routes cache
            routes: set[str] = set()
            portal_code: Optional[CodeSchema] = None
            if hasattr(plugin, "routes"):
                for key, code in plugin.routes():
                    if not key:
                        portal_code = code
                    else:
                        routes.add(key)

            cls.routes_cache[package] = (routes, portal_code)

            return plugin

        except Exception as e:
            err = RuntimeError(f"Failed to load plugin '{package}': {e}")
            cls._failed_plugins[package] = err
            # show error to terminal to check but keep running
            scheduler_logger.exception(err)
            # Raise exception to prevent saving invalid plugin to database
            raise err

    async def add_plugin(
        self, package: str, interval: int, description: Optional[str] = None
    ) -> int:
        # load plugin override module to make sure new code if sharing the same module
        self.load_plugin(package, True)
        # Insert into DB
        return await self.dao.add_plugin(package, interval, description)

    async def add_job(
        self,
        session_id: int,
        plugin_id: int,
        config: dict[str, Any],
        description: Optional[str] = None,
    ):
        # Get plugin to check for validation, will call assert internal
        interval, package, _ = self.dao.plugin_cache[plugin_id]

        # Proceed with saving job
        job_id = await self.dao.add_job(session_id, plugin_id, config, description)
        self.add_job_instance(job_id, False, interval, package)

    def add_job_instance(self, job_id: int, active: bool, interval: int, package: str):

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
            seconds=interval,
            # TODO: get user_id, and roles from database, the user of course owning the job
            args=[package, job_id, UserContext(0, frozenset({ADMIN_ROLE}))],
            next_run_time=undefined if active else None,
            id=job_scheduler_id,
            name=job_scheduler_id,
            coalesce=True,
            max_instances=1,  # Single job for each id
            replace_existing=True,
        )

    async def remove_job(self, job_id: int):
        await self.dao.remove_job(job_id)
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

    async def activate_job(self, job_id: int):
        if not await self.dao.activate_job(job_id):
            return

        # Resume the job
        job_scheduler_id = self.get_job_scheduler_id(job_id)
        self.scheduler.resume_job(job_scheduler_id)

    async def deactivate_job(self, job_id: int):
        if not await self.dao.deactivate_job(job_id):
            return

        # Pause the job
        job_scheduler_id = self.get_job_scheduler_id(job_id)
        self.scheduler.pause_job(job_scheduler_id)

    async def delete_plugin(self, plugin_id: int):
        """
        Delete a plugin from the database and unload it from memory.
        Also removes all associated jobs.
        """

        # Get all jobs for this plugin
        package, deleted_job_ids = await self.dao.delete_plugin(plugin_id)

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
