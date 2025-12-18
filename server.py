import asyncio
from fastapi import FastAPI, Body, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
from log_handler import JobLogHandler
from models import Job
from plugin_manager import PluginManager
from ws_manager import WSConnectionManager

# Configure logging to show INFO and above messages
logging.basicConfig(level=logging.DEBUG, handlers=[logging.NullHandler()])

manager = WSConnectionManager()

# Schedule async send_log in the event loop safely from sync context
log_handler = JobLogHandler(manager.send_log, asyncio.get_event_loop())


# this code is run in main loop of uvicorn
plugin_manager = PluginManager(log_handler=log_handler)
plugin_manager.start()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/logs")
async def websocket_logs_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; you can also handle client messages here if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


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
