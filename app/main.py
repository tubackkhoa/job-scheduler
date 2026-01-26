from app.deps import PluginManagerState
from app.routers import auth, plugins, logs, templates, users, jobs, ws, signals, stats

import asyncio
import logging
import os


from fastapi.responses import FileResponse
import uvloop
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
)
from fastapi.concurrency import asynccontextmanager
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
from models import DAO
from plugin_manager import PROJECT_NAME, PluginManager
from renderer import Renderer
from schemas import settings


from utils.job import JobUtil
from ws_manager import WSConnectionManager

# Configure logging to show INFO and above messages
logging.basicConfig(level=logging.DEBUG, handlers=[logging.NullHandler()])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise log service and handler
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    ws_manager = WSConnectionManager()

    log_service = LogService(
        log_dir=settings.log_dir,
        max_file_size=settings.log_max_size,
        max_files=settings.log_max_files,
        retention_days=settings.log_retention_days,
        useIndexer=settings.use_log_indexer,
    )

    loop = asyncio.get_running_loop()
    log_handler = JobLogHandler(ws_manager.send_log, loop, log_service=log_service)

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
    # static enforcer
    PluginManager.enforcer = create_enforcer(adapter)
    # prevent calling global registry in other plugin, so that we can mistake assign global permission for roles created by a plugin
    job_util = JobUtil(dao)
    # this is for class binding, only know at instatiate time
    # bind_class_registry(dao, job_util)
    GLOBAL_PERMISSION_REGISTRY.update({"dao": dao, "util": job_util})
    freeze_permission_registry()
    # reload from global
    Renderer.update()

    # create plugin_instance
    plugin_manager = PluginManager(
        dao,
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check(plugin_manager: PluginManagerState):
    try:
        # Check database connection
        async with plugin_manager.dao.session_factory().bind.connect() as conn:  # type: ignore
            await conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "plugin_manager": "initialized",
            "plugins": len(plugin_manager.dao.plugin_cache),
            "active_jobs": len(plugin_manager.dao.job_config_cache),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Health check failed: {str(e)}",
        )


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
app.include_router(api_router)

# websocket
app.include_router(ws.router)

# static site
if settings.static_files:
    app.mount(
        "/assets",
        StaticFiles(directory=f"{settings.static_files}/assets"),
        name="assets",
    )

    # SPA fallback (LAST)
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        return FileResponse(f"{settings.static_files}/index.html")
