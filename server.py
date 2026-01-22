import asyncio
import logging
import os

from typing import Annotated, Optional

import uvloop
from fastapi import (
    APIRouter,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine

from auth import User, get_user, require_auth
from enforcer import (
    GLOBAL_PERMISSION_REGISTRY,
    create_enforcer,
    freeze_permission_registry,
)
from log_handler import JobLogHandler
from log_service import LogService
from models import DAO, Job
from plugin_manager import PROJECT_NAME, PluginManager, scheduler_logger
from renderer import Renderer
from schemas import ConfigPayload, DownloadPayload, PluginCreatePayload, Settings, TemplatePayload
from package_downloader import download_package
from template_plugin import TemplatePlugin
from utils.job import JobUtil
from ws_manager import WSConnectionManager

# Configure logging to show INFO and above messages
logging.basicConfig(level=logging.DEBUG, handlers=[logging.NullHandler()])
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


manager = WSConnectionManager()


def get_plugin_manager(request: Request):
    return request.app.state.plugin_manager


def get_log_service(request: Request):
    return request.app.state.log_service


PluginManagerState = Annotated[PluginManager, Depends(get_plugin_manager)]
LogServiceState = Annotated[LogService, Depends(get_log_service)]
UserState = Annotated[User, Depends(get_user)]

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise log service and handler

    log_service = LogService(
        log_dir=settings.log_dir,
        max_file_size=settings.log_max_size,
        max_files=settings.log_max_files,
        retention_days=settings.log_retention_days,
        useIndexer=settings.use_log_indexer,
    )

    loop = asyncio.get_running_loop()
    log_handler = JobLogHandler(manager.send_log, loop, log_service=log_service)

    # These will be initialised once an event loop is running (inside lifespan)
    db_engine = create_engine(settings.db_connection)
    dao = DAO(db_engine)

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
    plugin_manager.reload_all_jobs()

    # ---- STARTUP ----
    plugin_manager.start()

    # store in app state
    app.state.plugin_manager = plugin_manager
    app.state.log_service = log_service

    yield

    # ---- SHUTDOWN ----
    plugin_manager.stop()

    # Immediate hard exit after 1 second for cleaning up
    await asyncio.sleep(1)
    os._exit(0)


api_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(require_auth)],
)

app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check(plugin_manager: PluginManagerState):

    from sqlalchemy import text

    try:
        # Check database connection
        with plugin_manager.dao.db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "plugin_manager": "initialized",
            "plugins_count": len(plugin_manager.get_plugin_names()),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Health check failed: {str(e)}",
        )


@app.websocket("/ws/logs/{job_id}")
async def websocket_logs_endpoint(websocket: WebSocket, job_id: int):
    scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
    await manager.connect(websocket, scheduler_job_id)
    try:
        while True:
            # Keep connection alive; you can also handle client messages here if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, scheduler_job_id)


# TODO: need checking for api based on ctx as well
@api_router.get("/authorization/state")
def auth_state(plugin_manager: PluginManagerState, user: UserState):
    if plugin_manager.enforcer:
        return {
            "policy": plugin_manager.enforcer.get_policy(),
            "user": user,
        }


@api_router.get("/plugins")
def plugins(
    plugin_manager: PluginManagerState,
    user: UserState,
):
    ctx = PluginManager.create_ctx(user)
    return plugin_manager.dao.get_all_plugins(ctx)


@api_router.post("/plugins")
def create_plugin(plugin_manager: PluginManagerState, payload: PluginCreatePayload = Body(...)):
    """
    Create a plugin record and load it into the PluginManager.

    Expected payload:
    {
      "package": "plugins.sample_plugin@v0_1_0.Plugin",
      "interval": 60,
      "description": "Sample plugin"
    }
    """
    # Load into manager
    try:
        plugin_id = plugin_manager.add_plugin(
            payload.package, payload.interval, payload.description
        )
        return {
            "id": plugin_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load plugin: {str(e)}",
        )


@api_router.post("/template/{package}")
def template(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload: TemplatePayload = Body(...),
):

    try:
        plugin_instance = plugin_manager.get_plugin_instance(package)

        # fallback to user plugin, usualy plugin package is namespace with dot while plugin template is just name
        if plugin_instance is None:
            plugin_instance = TemplatePlugin(f"{settings.user_plugin_path}/{package}")

        ctx = plugin_manager.create_ctx(user, package)
        # env will be extra to make sure params can not override
        result = Renderer.render(ctx, payload.template, payload.params, **plugin_instance.env())
        return Response(content=result, media_type="text/plain")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to render template: {str(e)}",
        )


@api_router.get("/schema/{session_id}/{plugin_id}")
def schema(
    plugin_manager: PluginManagerState,
    user: UserState,
    session_id: int,
    plugin_id: int,
):
    plugin_item = plugin_manager.dao.get_plugin(plugin_id)
    if not plugin_item:
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        ctx = plugin_manager.create_ctx(user, plugin_item.package)
        plugin = plugin_manager.get_plugin_instance(plugin_item.package)

        if plugin != None:
            jobs = plugin_manager.dao.get_jobs_by_plugin_and_session(ctx, plugin_id, session_id)
            for job in jobs:
                job.config = plugin.config(ctx, job.config).model_dump(mode="json")

            if len(jobs) == 0:
                # add empty config so that when saving it will be new job
                jobs.append(
                    Job(
                        active=False,
                        description="",
                        id=0,
                        config=plugin.config(ctx).model_dump(mode="json"),
                        plugin_id=plugin_id,
                        session_id=session_id,
                    )
                )

            # Built-in Jinja tags are provided by extensions
            return {
                "schema": plugin.schema(ctx),
                "jobs": jobs,
                "globals": Renderer.get_globals_doc(plugin.env()),
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load schema: {str(e)}")


@api_router.post("/activate/{job_id}/{activation}")
def activate_config(plugin_manager: PluginManagerState, job_id: int, activation: bool):
    if activation:
        plugin_manager.activate_job(job_id)
    else:
        plugin_manager.deactivate_job(job_id)
    return {"success": True}


@api_router.post("/delete/{job_id}")
def delete_job(plugin_manager: PluginManagerState, job_id: int):
    plugin_manager.remove_job(job_id)
    return {"success": True}


@api_router.post("/reload/{package}")
def reload_plugin(plugin_manager: PluginManagerState, package: str):
    try:
        plugin_manager.load_plugin(package, True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload plugin: {str(e)}")


@api_router.post("/download/{name}")
def download_module(
    plugin_manager: PluginManagerState, name: str, payload: DownloadPayload = Body(...)
):
    try:
        version_or_vsi = payload.version
        success = download_package(
            scheduler_logger, plugin_manager.plugin_path, name, version_or_vsi
        )
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download module: {str(e)}")


@api_router.put("/install/{package}")
def install_module(plugin_manager: PluginManagerState, package: str):
    try:
        plugin = plugin_manager.get_plugin_instance(package)
        assert plugin
        return {"success": plugin.install()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to install plugin: {str(e)}")


@api_router.put("/uninstall/{package}")
def uninstall_module(plugin_manager: PluginManagerState, package: str):
    try:
        plugin = plugin_manager.get_plugin_instance(package)
        assert plugin
        return {"success": plugin.uninstall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to uninstall plugin: {str(e)}")


@api_router.delete("/plugins/{plugin_id}")
def delete_plugin(plugin_manager: PluginManagerState, plugin_id: int):
    """
    Delete a plugin from the database and unload it from memory.
    Also removes all associated jobs.
    """
    try:
        plugin_manager.delete_plugin(plugin_id)
        return {"success": True, "message": f"Plugin with id {plugin_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plugin: {str(e)}")


@api_router.post("/config/{job_id}")
def update_config(
    plugin_manager: PluginManagerState,
    user: UserState,
    job_id: int,
    payload: ConfigPayload = Body(...),
):
    try:
        if job_id == 0:
            # Validate required fields for new job creation
            if payload.plugin_id is None:
                raise HTTPException(status_code=400, detail="pluginId is required when job_id is 0")
            if payload.session_id is None:
                raise HTTPException(
                    status_code=400, detail="sessionId is required when job_id is 0"
                )
            plugin_id = payload.plugin_id
            session_id = payload.session_id
        else:
            job_item = plugin_manager.dao.get_job(job_id)
            if not job_item:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            plugin_id = job_item.plugin_id

        plugin_item = plugin_manager.dao.get_plugin(plugin_id)
        if not plugin_item:
            raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")
        plugin = plugin_manager.get_plugin_instance(plugin_item.package)
        if not plugin:
            raise HTTPException(status_code=404, detail="Plugin not found")

        ctx = plugin_manager.create_ctx(user, plugin_item.package)
        # validate before saving
        config = plugin.config(ctx, payload.config, True)
        if job_id == 0:
            plugin_manager.add_job(
                session_id,
                plugin_id,
                config.model_dump(mode="json"),
                payload.description,
            )
        else:
            plugin_manager.dao.update_job(
                job_id, config.model_dump(mode="json"), payload.description
            )

        return config
    except HTTPException:
        # Re-raise HTTP exceptions for FastAPI to handle properly
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@api_router.get("/logs/{job_id}")
def search_logs(
    log_service: LogServiceState,
    job_id: int,
    search: Optional[str] = None,
    offset: Optional[int] = None,
    limit: int = 1000,
    sort: str = "desc",
):
    """
    Search logs for a job_id.
    Query params:
    - job_id: job identifier (format: plugin_id/session_id/job_id, e.g., "5/1/10")
    - search: text to search for (optional)
    - offset: start from this offset (optional)
    - limit: max results (default 1000)
    - sort: sort order - "asc" (oldest first) or "desc" (newest first, default)
    """
    try:
        scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
        result = log_service.search_logs(
            job_id=scheduler_job_id,
            search_text=search,
            offset=offset,
            limit=limit,
            sort=sort,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search logs: {str(e)}")


@api_router.get("/logs/{job_id}/signals")
def search_logs_with_following(
    log_service: LogServiceState,
    job_id: int,
    keyword: str,
    n_following: int = 25,
    limit: int = 100,
    sort: str = "desc",
):
    try:
        scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
        result = log_service.search_logs_with_following(
            job_id=scheduler_job_id,
            keyword=keyword,
            n_following=n_following,
            limit=limit,
            sort=sort,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search logs with following: {str(e)}"
        )


@api_router.post("/logs/{job_id}/clear")
def clear_logs(log_service: LogServiceState, job_id: int):
    scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
    result = log_service.clear_logs(scheduler_job_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# support template plugin, install by user
@api_router.get("/user/template/{package}")
def template_plugin(plugin_manager: PluginManagerState, user: UserState, package: str):
    tpl_plugin = TemplatePlugin(f"{settings.user_plugin_path}/{package}")
    ctx = plugin_manager.create_ctx(user)
    config = tpl_plugin.config(ctx)
    return {
        "schema": tpl_plugin.schema(ctx),
        "jobs": [
            Job(
                active=False,
                description=tpl_plugin.description,
                id=0,
                config=config.model_dump(mode="json"),
                plugin_id=package,
            )
        ],
        "globals": Renderer.get_globals_doc(tpl_plugin.env()),
    }


@api_router.post("/user/template/{package}")
def template_plugin_update(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload: ConfigPayload = Body(...),
):
    try:
        tpl_plugin = TemplatePlugin(f"{settings.user_plugin_path}/{package}")
        ctx = plugin_manager.create_ctx(user)
        tpl_plugin.save(ctx, payload.description, payload.config)
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to run template plugin: {str(e)}",
        )


@api_router.post("/user/template/run/{package}")
def template_plugin_run(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload=Body(...),
):
    try:
        tpl_plugin = TemplatePlugin(f"{settings.user_plugin_path}/{package}")
        ctx = plugin_manager.create_ctx(user)
        config = tpl_plugin.config(ctx, payload)
        result = tpl_plugin.run(ctx, config)
        return Response(content=result, media_type="text/plain")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to run template plugin: {str(e)}",
        )


app.include_router(api_router)

# static site
if settings.static_files:
    app.mount(
        "/",
        StaticFiles(directory=settings.static_files, html=True),
        name="static",
    )
