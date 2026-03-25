import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Optional, cast

import pluggy
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.util import undefined
from casbin.enforcer import Enforcer
from pydantic import BaseModel

from auth import UserContext
from enforcer import (
    ADMIN_ROLE,
    ExecutionContext,
)
from dao import DAO
from plugins import CodeSchema
from renderer import Renderer
from schemas import settings
import redis.asyncio as aioredis

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

    def __init__(
        self,
        dao: DAO,
        enforcer: Optional[Enforcer] = None,
        module_paths: Optional[list[str]] = None,
        plugin_path="plugins",
        log_handler: Optional[logging.Handler] = None,
        scheduler_kwargs: Optional[dict] = None,
        redis_client: Optional[aioredis.Redis] = None,
    ) -> None:

        self.redis_client = redis_client
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

        self.enforcer = enforcer
        # static pluggy manager, so that all pluginmanager share the same plugins
        self.manager = pluggy.PluginManager(PROJECT_NAME)
        self.manager.add_hookspecs(PluginSpec)
        self.hook = cast(PluginSpec, self.manager.hook)

        self.routes_cache: dict[str, tuple[set[str], Optional[CodeSchema]]] = {}
        self._failed_plugins: dict[str, Exception] = {}

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
            package, _ = self.dao.plugin_cache[job.plugin_id]
            # Plugin will be lazy load so that can reload and fix
            self.add_job_instance(job.id, job.active, job.cron_expr, package)

    def start(self):
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    @staticmethod
    def _iter_plugin_permissions(package: str, plugin_cls: PluginSpec):
        mapping = plugin_cls.roles()
        if not isinstance(mapping, dict):
            return

        for permission_key, roles in mapping.items():
            permission = f"{package}:{permission_key}"
            for role in roles:
                if role != ADMIN_ROLE:
                    yield role, permission

    def register_plugin_permissions(self, package: str, plugin_cls: PluginSpec):
        if not self.enforcer:
            return
        try:
            enforcer = self.enforcer
            for role, permission in self._iter_plugin_permissions(package, plugin_cls):
                if not enforcer.has_policy(role, permission):
                    enforcer.add_policy(role, permission)
        except Exception:
            scheduler_logger.exception(
                "Failed to register plugin permissions",
                extra={"package": package},
            )

    def unregister_plugin_permissions(self, package: str, plugin_cls: PluginSpec):
        if not self.enforcer:
            return
        try:
            enforcer = self.enforcer
            for role, permission in self._iter_plugin_permissions(package, plugin_cls):
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

    def get_plugin_names(self):
        return [name for name, _ in self.manager.list_name_plugin()]

    def get_plugin_instance(self, package: str) -> Optional[PluginSpec]:
        if not self.manager.has_plugin(package):
            try:
                scheduler_logger.info(f"Loading plugin: {package}")
                return self.load_plugin(package)
            except Exception as e:
                scheduler_logger.exception(f"Error loading plugin: {e}")
                return None

        return self.manager.get_plugin(package)

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

    async def run_plugin_job(self, package: str, job_id: int):
        plugin = self.get_plugin_instance(package)

        if plugin is None:
            return None

        lock = None
        acquired = False

        # === REDIS LOCK ===
        if self.redis_client:
            lock = self.redis_client.lock(f"job:lock:{job_id}", timeout=settings.job_lock_timeout)
            acquired = await lock.acquire(blocking=False)

            if not acquired:
                return

        try:
            user = UserContext(0, frozenset({ADMIN_ROLE}))
            ctx = self.create_ctx(user, package)
            render_function = self.make_render(plugin, ctx)

            job_config = self.dao.job_config_cache.get(job_id)
            config = plugin.config(ctx, job_config)
            logger = logging.getLogger(self.get_job_scheduler_id(job_id))
            return await plugin.run(ctx, config, logger, render_function)

        except Exception as e:
            scheduler_logger.exception(f"Job {job_id} failed: {e}")

        finally:
            # ✅ ALWAYS release lock
            if lock:
                try:
                    await lock.release()
                except Exception as e:
                    scheduler_logger.error(f"Job {job_id} failed to release lock: {e}")

    def unload_plugin(self, package: str):
        self._failed_plugins.pop(package, None)

        existing_plugin = self.manager.get_plugin(package)
        if existing_plugin:
            # clear data
            self.unregister_plugin_permissions(package, existing_plugin)
            self.routes_cache.pop(package, None)
            self.manager.unregister(existing_plugin, package)

    def create_ctx(self, user: UserContext, package: Optional[str] = None):
        return ExecutionContext(user, package, self.enforcer.enforce if self.enforcer else None)

    def load_plugin(self, package: str, override: bool = False):

        module_path, _, class_name = package.rpartition(".")

        if override:
            self.unload_plugin(package)
            self.reload_module(module_path)

        # 🚫 Fast-fail if previously broken, when override it will reset fail plugin
        elif package in self._failed_plugins:
            raise self._failed_plugins[package]

        plugin: PluginSpec | None = self.manager.get_plugin(package)
        if plugin is not None:
            return plugin

        try:
            module = importlib.import_module(module_path)
            plugin = getattr(module, class_name, None)
            if plugin is None:
                raise RuntimeError(f"Plugin class '{class_name}' not found in '{module_path}'")
            if module.__file__:
                plugin.dir = Path(module.__file__).resolve().parent
            self.manager.register(plugin, package)
            self.register_plugin_permissions(package, plugin)

            # update routes cache
            routes: set[str] = set()
            portal_code: Optional[CodeSchema] = None
            if hasattr(plugin, "routes"):
                for key, code in plugin.routes():
                    if not key:
                        portal_code = code
                    else:
                        routes.add(key)

            self.routes_cache[package] = (routes, portal_code)

            return plugin

        except Exception as e:
            err = RuntimeError(f"Failed to load plugin '{package}': {e}")
            self._failed_plugins[package] = err
            # show error to terminal to check but keep running
            scheduler_logger.exception(err)
            # Raise exception to prevent saving invalid plugin to database
            raise err

    async def add_plugin(self, package: str, description: Optional[str] = None) -> int:
        # load plugin override module to make sure new code if sharing the same module
        self.load_plugin(package, True)
        # Insert into DB
        return await self.dao.add_plugin(package, description)

    @staticmethod
    def create_trigger(cron_expr: Optional[str]) -> CronTrigger:
        values: list = (cron_expr or settings.default_cron).split()
        # default second is None
        if len(values) == 5:
            values.insert(0, None)
        sec, minute, hour, dom, month, dow = values
        return CronTrigger(
            second=sec,
            minute=minute,
            hour=hour,
            day=dom,
            month=month,
            day_of_week=dow,
        )

    async def add_job(
        self,
        session_id: int,
        plugin_id: int,
        config: dict[str, Any],
        description: Optional[str] = None,
        cron_expr: str = settings.default_cron,
    ):
        # Get plugin to check for validation, will call assert internal
        package, _ = self.dao.plugin_cache[plugin_id]

        # Proceed with saving job
        job_id = await self.dao.add_job(session_id, plugin_id, config, description)
        self.add_job_instance(job_id, False, cron_expr, package)

    def add_job_instance(self, job_id: int, active: bool, cron_expr: str, package: str):

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
            trigger=self.create_trigger(cron_expr),
            # TODO: get user_id, and roles from database, the user of course owning the job
            args=[
                package,
                job_id,
            ],
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

    async def activate_job(self, job_id: int):
        if not await self.dao.activate_job(job_id):
            return

        # Resume the job
        job_scheduler_id = self.get_job_scheduler_id(job_id)
        self.scheduler.resume_job(job_scheduler_id)

    async def reschedule_job(self, job_id: int, cron_expr: str):
        job_scheduler_id = self.get_job_scheduler_id(job_id)
        self.scheduler.reschedule_job(job_scheduler_id, trigger=self.create_trigger(cron_expr))

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
