import asyncio
from typing import Annotated, Optional
from fastapi import (
    Depends,
    FastAPI,
    Body,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import logging

from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from create_data import create_data
from log_handler import JobLogHandler
from log_service import LogService
from models import Job, Plugin
from plugin_manager import PluginManager
from ws_manager import WSConnectionManager
import os
import dotenv
import uvloop

dotenv.load_dotenv()
# Configure logging to show INFO and above messages
logging.basicConfig(level=logging.DEBUG, handlers=[logging.NullHandler()])
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

manager = WSConnectionManager()


# define state transform for app
def get_plugin_manager(request: Request) -> PluginManager:
    return request.app.state.plugin_manager


def get_log_service(request: Request) -> LogService:
    return request.app.state.log_service


PluginManagerState = Annotated[PluginManager, Depends(get_plugin_manager)]
LogServiceState = Annotated[LogService, Depends(get_log_service)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # These will be initialised once an event loop is running (inside lifespan)
    db_connection = os.getenv("DB_CONNECTION")
    assert db_connection
    if ":memory:" in db_connection:
        from sqlalchemy.pool import StaticPool

        # single connection for testing
        db_engine = create_engine(
            db_connection,
            poolclass=StaticPool,
        )
        create_data(db_engine)
    else:
        db_engine = create_engine(db_connection)

    # Initialise log service and handler
    log_service = LogService(
        log_dir=os.getenv("LOG_DIR", "logs"),
        max_file_size=int(os.getenv("LOG_MAX_SIZE", 10 * 1024 * 1024)),
        max_files=int(os.getenv("LOG_MAX_FILES", 10)),
        retention_days=int(os.getenv("LOG_RETENTION_DAYS", 7)),
    )

    loop = asyncio.get_running_loop()
    log_handler = JobLogHandler(manager.send_log, loop, log_service=log_service)

    plugin_manager = PluginManager(
        db_engine,
        log_handler=log_handler,
        module_paths=os.getenv("MODULE_PATH", "").split(":"),
    )
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
        db_engine = plugin_manager.db_engine
        with db_engine.connect() as conn:
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


@app.get("/plugins")
def plugins(plugin_manager: PluginManagerState):
    return plugin_manager.get_all_plugins()


@app.post("/plugins")
def create_plugin(plugin_manager: PluginManagerState, payload: dict = Body(...)):
    """
    Create a plugin record and load it into the PluginManager.

    Expected payload:
    {
      "package": "plugins.sample_plugin@v0_1_0.Plugin",
      "interval": 60,
      "description": "Sample plugin"
    }
    """
    from sqlalchemy.orm import Session

    required_keys = {"package", "interval"}
    if not required_keys.issubset(payload):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: package, interval",
        )

    # Load into manager
    try:
        plugin_id = plugin_manager.add_plugin(
            payload["package"], int(payload["interval"]), payload.get("description")
        )
        return {
            "id": plugin_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load plugin: {str(e)}",
        )


@app.post("/template/{package}")
def template(plugin_manager: PluginManagerState, package: str, payload: dict = Body(...)):
    plugin_instance = plugin_manager.get_plugin_instance(package)
    template_str = payload.get("template", "")
    if plugin_instance is None:
        return {"result": template_str}

    try:
        template_engine = plugin_instance.env().from_string(template_str)
        result = template_engine.render(**payload["params"])
        return {"result": result}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load plugin: {str(e)}",
        )


@app.get("/schema/{session_id}/{plugin_id}")
def schema(plugin_manager: PluginManagerState, session_id: int, plugin_id: int):
    plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
    assert plugin_item

    try:
        plugin = plugin_manager.get_plugin_instance(plugin_item.package)
        if plugin != None:
            configs = plugin_manager.get_jobs_for_plugin_and_user(plugin_id, session_id)
            if len(configs) == 0:
                # add empty config so that when saving it will be new job
                configs.append(
                    Job(
                        active=False,
                        description="",
                        id=0,
                        config=plugin.config().model_dump_json(),
                        plugin_id=plugin_id,
                        session_id=session_id,
                    )
                )
            return {
                "schema": plugin.schema(),
                "configs": configs,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load schema: {str(e)}")


@app.post("/activate/{job_id}/{activation}")
def activate_config(plugin_manager: PluginManagerState, job_id: int, activation: bool):
    if activation:
        plugin_manager.activate_job(job_id)
    else:
        plugin_manager.deactivate_job(job_id)
    return {"success": True}


@app.post("/delete/{job_id}")
def delete_job(plugin_manager: PluginManagerState, job_id: int):
    plugin_manager.remove_job(job_id)
    return {"success": True}


@app.post("/reload/{package}")
def reload_plugin(plugin_manager: PluginManagerState, package: str):
    try:
        plugin_manager.load_plugin(package, True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload plugin: {str(e)}")


@app.post("/config/{job_id}")
def update_config(plugin_manager: PluginManagerState, job_id: int, payload: dict = Body(...)):
    try:
        if job_id == 0:
            plugin_id = payload["pluginId"]
        else:
            job_item = plugin_manager.get_job_by_id(job_id)
            assert job_item
            plugin_id = job_item.plugin_id

        plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
        assert plugin_item
        plugin = plugin_manager.get_plugin_instance(plugin_item.package)
        if not plugin:
            return {"error": "Plugin not found"}
        config = plugin.config(payload.get("config"))
        if job_id == 0:
            # Accept both userId (legacy) and sessionId (new)
            session_id = payload.get("sessionId") or payload.get("userId")
            if not session_id:
                raise HTTPException(status_code=400, detail="sessionId or userId is required")
            plugin_manager.add_job(
                session_id,
                plugin_id,
                config.model_dump_json(),
                payload.get("description"),
            )
        else:
            plugin_manager.update_job(job_id, config.model_dump_json(), payload.get("description"))

        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@app.get("/api/logs/{job_id}")
def search_logs(
    log_service: LogServiceState,
    job_id: int,
    search: Optional[str] = None,
    offset: Optional[int] = None,
    limit: int = 1000,
):
    """
    Search logs for a job_id.
    Query params:
    - job_id: job identifier (format: plugin_id/session_id/job_id, e.g., "5/1/10")
    - search: text to search for (optional)
    - offset: start from this offset (optional)
    - limit: max results (default 1000)
    """
    try:
        scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
        result = log_service.search_logs(
            job_id=scheduler_job_id,
            search_text=search,
            offset=offset,
            limit=limit,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search logs: {str(e)}")


# static site
static_files = os.getenv("STATIC_FILES")
if static_files:
    app.mount(
        "/",
        StaticFiles(directory=static_files, html=True),
        name="static",
    )
