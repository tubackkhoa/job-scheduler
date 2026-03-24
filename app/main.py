from typing import AsyncIterator
from jinja2 import TemplateError
from app.deps import PluginManagerState
from app.routers import (
    auth,
    plugins,
    logs,
    templates,
    users,
    jobs,
    ws,
    signals,
    stats,
)

import asyncio
import logging
import os
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from auth import require_auth
from enforcer import (
    GLOBAL_PERMISSION_REGISTRY,
    create_enforcer,
    freeze_permission_registry,
)
from log_handler import JobLogHandler
from log_service import LogService
from dao import DAO
from plugin_manager import PROJECT_NAME, PluginManager
from renderer import Renderer
from schemas import settings
from ws_manager import WSConnectionManager

import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Configure logging to show INFO and above messages
logging.basicConfig(level=logging.DEBUG, handlers=[logging.NullHandler()])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialise log service and handler
    ws_manager = WSConnectionManager()

    log_service = LogService(
        log_dir=settings.log_dir,
        max_file_size=settings.log_max_size,
        max_files=settings.log_max_files,
        retention_days=settings.log_retention_days,
        useIndexer=settings.use_log_indexer,
    )

    # These will be initialised once an event loop is running (inside lifespan)
    engine = create_async_engine(
        settings.db_connection,
        echo=False,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    dao = DAO(session_factory)

    log_handler = JobLogHandler()
    log_handler.add_hook(ws_manager.send_log)  # websocket broad cast
    log_handler.add_hook(log_service.write_log)  # write log to file
    log_handler.add_hook(dao.save_signal_message)  # save to db

    adapter = None
    if settings.redis_host:
        # using redis adapter on the fly
        from casbin_redis_adapter.adapter import Adapter

        adapter = Adapter(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db or 0,
            key=f"{PROJECT_NAME}:job_policy",
        )

    # prevent calling global registry in other plugin, so that we can mistake assign global permission for roles created by a plugin
    # this is for class binding, only know at instatiate time
    # bind_class_registry(dao, job_util)
    GLOBAL_PERMISSION_REGISTRY.update({"dao": dao})
    freeze_permission_registry()
    # reload from global
    Renderer.update()

    # create plugin_instance
    plugin_manager = PluginManager(
        dao,
        enforcer=create_enforcer(adapter),
        log_handler=log_handler,
        module_paths=settings.module_path.split(":") if settings.module_path else None,
        plugin_path=settings.plugin_path,
    )

    # Trade models API functions (no db_engine needed, use api_url/api_key directly)
    await plugin_manager.reload_all_jobs()

    # ---- STARTUP ----
    plugin_manager.start()

    # store in app state
    app.state.plugin_manager = plugin_manager
    app.state.log_service = log_service
    app.state.ws_manager = ws_manager

    yield

    # ---- SHUTDOWN ----
    plugin_manager.stop()

    # Immediate hard exit after 1 second for cleaning up
    await asyncio.sleep(1)
    os._exit(0)


app = FastAPI(lifespan=lifespan)

# Compress responses
if settings.min_gzip_size:
    app.add_middleware(GZipMiddleware, minimum_size=settings.min_gzip_size)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    expose_headers=["X-Model-Name"],
)


# override only HTTPException and UndefinedError, generic Exception will be log and only return Internal Server Error
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return PlainTextResponse(
        status_code=exc.status_code,
        content=exc.detail,
    )


# handle for some Error extends from Exception
@app.exception_handler(OSError)
@app.exception_handler(TemplateError)
@app.exception_handler(RuntimeError)
async def other_exception_handler(_: Request, exc: Exception):
    return PlainTextResponse(
        status_code=400,
        content=str(exc),
    )


@app.get("/health")
async def health_check(plugin_manager: PluginManagerState):

    # Check database connection
    async with plugin_manager.dao.session_factory() as session:
        await session.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "database": "connected",
        "plugin_manager": "initialized",
        "plugins": len(plugin_manager.dao.plugin_cache),
        "active_jobs": len(plugin_manager.dao.job_config_cache),
    }


app.include_router(auth.router)

# authorized routers
api_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(require_auth)],
)
api_router.include_router(plugins.router)
api_router.include_router(logs.router)
api_router.include_router(templates.router)
api_router.include_router(users.router)
api_router.include_router(jobs.router)
api_router.include_router(signals.router)
api_router.include_router(stats.router)

if settings.chatbot_enabled:
    from app.routers import chatbot

    api_router.include_router(chatbot.router)

app.include_router(api_router)

# websocket
app.include_router(ws.router)


# Add plugin assets route (must be declared AFTER app is created)
@app.get("/assets/{package}/{asset_path:path}")
def plugin_assets(
    plugin_manager: PluginManagerState,
    package: str,
    asset_path: str,
):
    plugin = plugin_manager.get_plugin_instance(package)
    if not plugin:
        raise HTTPException(status_code=404, detail="Asset not found")

    plugin_assets_dir = (plugin.dir / "assets").resolve()
    file_path = (plugin_assets_dir / asset_path).resolve()

    # Prevent path traversal

    file_path.relative_to(plugin_assets_dir)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")

    return FileResponse(file_path)


# static site
if settings.static_files:
    from pathlib import Path

    static_dir = Path(settings.static_files).resolve()
    assets_dir = static_dir / "assets"
    index_file = static_dir / "index.html"

    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}")
    def spa_fallback(path: str):
        requested = (static_dir / path).resolve()
        try:
            requested.relative_to(static_dir)
            if requested.is_file():
                return FileResponse(requested)
        except ValueError:
            pass

        return FileResponse(index_file)
