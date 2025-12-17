from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from plugin_manager import PluginManager

# Configure logging to show INFO and above messages
logging.basicConfig(level=logging.ERROR)

user_id = 1

plugin_manager = PluginManager()
plugin_manager.start()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)


@app.get("/plugins")
def plugins():
    return plugin_manager.get_all_plugins()


@app.get("/schema/{plugin_id}")
def schema(plugin_id: int):
    plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
    assert plugin_item
    plugin = plugin_manager.get_plugin_instance(str(plugin_item.package))
    if plugin != None:
        return {
            "schema": plugin.schema(),
            "configs": plugin_manager.get_jobs_for_plugin_and_user(plugin_id, user_id),
        }


@app.post("/activate/{job_id}/{activation}")
def activate_config(job_id: int, activation: bool):
    if activation:
        plugin_manager.activate_job(job_id)
    else:
        plugin_manager.deactivate_job(job_id)
    return {"success": True}


@app.post("/config/{job_id}")
def update_config(job_id: int, payload: dict = Body(...)):
    job_item = plugin_manager.get_job_by_id(job_id)
    assert job_item
    plugin_item = plugin_manager.get_plugin_by_id(job_item.plugin_id)  # type: ignore
    assert plugin_item
    plugin = plugin_manager.get_plugin_instance(str(plugin_item.package))
    if not plugin:
        return {"error": "Plugin not found"}
    try:
        config = plugin.config(payload)
        plugin_manager.update_job(job_id, config.model_dump_json())
        return config
    except Exception as e:
        # unexpected errors
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )
