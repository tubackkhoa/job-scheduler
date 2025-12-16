from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import logging

from plugin_manager import PluginManager

# Configure logging to show INFO and above messages
logging.basicConfig(level=logging.INFO)

plugin_manager = PluginManager(
    [
        {"package": "plugins.sample_plugin@v0_1_0.Plugin", "interval": 5},
        {"package": "plugins.sample_plugin@v0_2_0.Plugin", "interval": 3},
        {"package": "plugins.lab_plugin@v0_1_0.LabPlugin", "interval": 3},
        {"package": "plugins.stable_plugin@v0_1_0.StablePlugin", "interval": 3},
        {"package": "plugins.prod_plugin@v0_1_0.ProdPlugin", "interval": 3},
    ]
)

plugin_manager.start()


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)


@app.get("/plugins")
def plugins():
    return plugin_manager.get_plugin_names()


@app.get("/schema/{name}")
def schema(name: str):
    plugin = plugin_manager.get_plugin(name)
    if plugin != None:
        return {
            "schema": plugin.schema(),
            "configs": plugin_manager.config_data[name],
        }


@app.post("/plugin/{name}")
def update_plugin(name: str):
    plugin = plugin_manager.load_plugin(name, True)
    return {
        "schema": plugin.schema(),
        "configs": plugin_manager.config_data[name],
    }


@app.post("/config/{name}/{version}")
def update_config(name: str, version: str, payload: dict = Body(...)):
    plugin = plugin_manager.get_plugin(name)
    if not plugin:
        return {"error": "Plugin not found"}
    config = plugin.config(payload)
    plugin_manager.config_data[name][version] = config
    return config
