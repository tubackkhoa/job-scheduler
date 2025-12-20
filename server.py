import asyncio
from fastapi import FastAPI, Body, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import logging

from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from create_data import create_data
from log_handler import JobLogHandler
from models import Job
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

# Schedule async send_log in the event loop safely from sync context
log_handler = JobLogHandler(manager.send_log, asyncio.get_running_loop())

db_connection = os.getenv("DB_CONNECTION")
assert db_connection
db_engine = create_engine(db_connection)

# this code is run in main loop of uvicorn
plugin_manager = PluginManager(
    db_engine,
    log_handler=log_handler,
    module_paths=os.getenv("MODULE_PATH", "").split(":"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- STARTUP ----
    plugin_manager.start()

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
def plugins():
    return plugin_manager.get_all_plugins()


@app.get("/schema/{user_id}/{plugin_id}")
def schema(user_id: int, plugin_id: int):
    plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
    assert plugin_item
    plugin = plugin_manager.get_plugin_instance(str(plugin_item.package))
    configs = plugin_manager.get_jobs_for_plugin_and_user(plugin_id, user_id)
    if plugin != None:
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


@app.post("/activate/{job_id}/{activation}")
def activate_config(job_id: int, activation: bool):
    if activation:
        plugin_manager.activate_job(job_id)
    else:
        plugin_manager.deactivate_job(job_id)
    return {"success": True}


@app.post("/delete/{job_id}")
def delete_job(job_id: int):
    plugin_manager.remove_job(job_id)
    return {"success": True}


@app.post("/config/{job_id}")
def update_config(job_id: int, payload: dict = Body(...)):
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
            plugin_manager.update_job(
                job_id, config.model_dump_json(), payload.get("description")
            )

        return config
    except Exception as e:
        # unexpected errors
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


# static site
static_files = os.getenv("STATIC_FILES")
if static_files:
    app.mount(
        "/",
        StaticFiles(directory=static_files, html=True),
        name="static",
    )
