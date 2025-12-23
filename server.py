import asyncio
from typing import Annotated
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


PluginManagerState = Annotated[PluginManager, Depends(get_plugin_manager)]


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

    # Initialise log handler and plugin manager once we have a running event loop
    loop = asyncio.get_running_loop()
    log_handler = JobLogHandler(manager.send_log, loop)

    plugin_manager = PluginManager(
        db_engine,
        log_handler=log_handler,
        module_paths=os.getenv("MODULE_PATH", "").split(":"),
    )

    # ---- STARTUP ----
    plugin_manager.start()

    # store in app state
    app.state.plugin_manager = plugin_manager

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


@app.websocket("/ws/logs/{plugin_id}/{user_id}")
async def websocket_logs_endpoint(websocket: WebSocket, plugin_id: int, user_id: int):
    job_id = f"{plugin_id}/{user_id}"
    await manager.connect(websocket, job_id)
    try:
        while True:
            # Keep connection alive; you can also handle client messages here if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)


@app.get("/plugins")
def plugins(plugin_manager: PluginManagerState):
    # plugin_manager: PluginManager = app.state.plugin_manager
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

    package = payload["package"]
    interval = payload["interval"]
    description = payload.get("description")

    # Load into manager
    try:
        plugin_manager.load_plugin(package)
        # Insert into DB
        with Session(plugin_manager.db_engine) as session:
            plugin_row = Plugin(
                package=package,
                interval=interval,
                description=description,
            )

            session.add(plugin_row)
            session.flush()  # get ID
            plugin_id = plugin_row.id
            session.commit()
            return {
                "id": plugin_id,
            }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load plugin: {str(e)}",
        )


# TODO: change logic of /config/{job_id} instead

# @app.post("/jobs/default")
# def create_default_jobs(plugin_manager: PluginManagerState, payload: dict = Body(...)):
#     """
#     Create jobs using the plugin's default config for one or more users.

#     Expected payload:
#     {
#       "pluginId": 1,
#       "userIds": [1, 2],          # optional, defaults to [1]
#       "description": "optional",  # optional
#       "active": true              # optional, default true
#     }
#     """
#     from sqlalchemy.orm import Session

#     plugin_id = payload.get("pluginId")
#     if plugin_id is None:
#         raise HTTPException(status_code=400, detail="pluginId is required")

#     user_ids = payload.get("userIds") or [1]
#     if not isinstance(user_ids, list):
#         raise HTTPException(status_code=400, detail="userIds must be a list")

#     description = payload.get("description")
#     active = bool(payload.get("active", True))

#     plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
#     if not plugin_item:
#         raise HTTPException(status_code=404, detail=f"Plugin with id {plugin_id} not found")

#     plugin = plugin_manager.get_plugin_instance(str(plugin_item.package))
#     if not plugin:
#         # try to load once
#         plugin_manager.load_plugin(str(plugin_item.package), True)
#         plugin = plugin_manager.get_plugin_instance(str(plugin_item.package))
#     if not plugin:
#         raise HTTPException(status_code=500, detail="Failed to load plugin instance")

#     # default config from plugin
#     try:
#         default_config = plugin.config()  # pydantic model
#         config_json = default_config.model_dump_json()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to get default config: {str(e)}")

#     created_jobs = []
#     with Session(plugin_manager.db_engine) as session:
#         for user_id in user_ids:
#             job = Job(
#                 user_id=int(user_id),
#                 plugin_id=plugin_item.id,
#                 config=config_json,
#                 active=1 if active else 0,
#                 description=description,
#             )
#             session.add(job)
#             session.flush()

#             # schedule job
#             plugin_manager.add_job_instance(job, plugin_item)
#             if active:
#                 plugin_manager.activate_job(job.id)

#             created_jobs.append(
#                 {
#                     "id": job.id,
#                     "user_id": job.user_id,
#                     "plugin_id": job.plugin_id,
#                     "config": job.config,
#                     "description": job.description,
#                     "active": job.active,
#                 }
#             )

#         session.commit()

#     return {
#         "plugin": {
#             "id": plugin_item.id,
#             "package": plugin_item.package,
#             "interval": plugin_item.interval,
#             "description": plugin_item.description,
#         },
#         "jobs": created_jobs,
#     }


@app.get("/schema/{user_id}/{plugin_id}")
def schema(plugin_manager: PluginManagerState, user_id: int, plugin_id: int):
    plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
    assert plugin_item

    try:
        plugin = plugin_manager.get_plugin_instance(str(plugin_item.package))
        if plugin != None:
            configs = plugin_manager.get_jobs_for_plugin_and_user(plugin_id, user_id)
            if len(configs) == 0:
                # add empty config so that when saving it will be new job
                configs.append(
                    Job(
                        active=0,
                        description="",
                        id=0,
                        config=plugin.config().model_dump_json(),
                        plugin_id=plugin_id,
                        user_id=user_id,
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
            plugin_id = int(job_item.plugin_id)  # type: ignore

        plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
        assert plugin_item
        plugin = plugin_manager.get_plugin_instance(str(plugin_item.package))
        if not plugin:
            return {"error": "Plugin not found"}
        config = plugin.config(payload.get("config"))
        if job_id == 0:
            plugin_manager.add_job(
                payload["userId"],
                plugin_id,
                config.model_dump_json(),
                payload.get("description"),
            )
        else:
            plugin_manager.update_job(job_id, config.model_dump_json(), payload.get("description"))

        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


# static site
static_files = os.getenv("STATIC_FILES")
if static_files:
    app.mount(
        "/",
        StaticFiles(directory=static_files, html=True),
        name="static",
    )
