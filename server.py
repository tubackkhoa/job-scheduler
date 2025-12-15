import importlib
import sys
from typing import Any, Optional
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import pluggy
from pydantic import BaseModel


PROJECT_NAME = "alpha-miner"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)


class MySpec:

    @hookspec
    def schema(cls) -> dict[str, Any]: ...

    @hookspec
    def config(cls, json: Optional[dict[str, Any]] = None) -> dict[str, Any]: ...

    @hookspec
    async def run(cls, config: BaseModel) -> bool: ...


pm = pluggy.PluginManager(PROJECT_NAME)
pm.add_hookspecs(MySpec)

plugin_items = [
    "plugins.sample_plugin@v0_1_0.Plugin",
    "plugins.sample_plugin@v0_2_0.Plugin",
    "plugins.lab_plugin@v0_1_0.LabPlugin",
    "plugins.stable_plugin@v0_1_0.StablePlugin",
    "plugins.prod_plugin@v0_1_0.ProdPlugin",
]

config_data = {}


def unload_module(module_path: str):
    # clear old code of the module
    modules_to_remove = [
        name
        for name in sys.modules
        if name == module_path or name.startswith(module_path + ".")
    ]
    for mod_name in modules_to_remove:
        del sys.modules[mod_name]


def load_plugin(name: str, override: bool = False, json: Optional[Any] = None):
    module_path, class_name = name.rsplit(".", 1)

    if override:
        # unregister hook
        existing = pm.get_plugin(name)
        if existing is not None:
            pm.unregister(existing, name)

        unload_module(module_path)

    # import module
    module = importlib.import_module(module_path)
    plugin: MySpec = getattr(module, class_name)
    config = plugin.config(json)

    pm.register(plugin, name)
    config_data[name] = {
        "version 1.0": config,
        "version 2.0": config,
    }
    return plugin


for name in plugin_items:
    load_plugin(name)

# validate implementation
pm.check_pending()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)


@app.get("/plugins")
def plugins():
    return plugin_items


@app.get("/schema/{name}")
def schema(name: str):
    plugin: MySpec | None = pm.get_plugin(name)
    if plugin != None:
        return {
            "schema": plugin.schema(),
            "configs": config_data[name],
        }


@app.post("/plugin/{name}")
def update_plugin(name: str):
    plugin = load_plugin(name, True)
    return {
        "schema": plugin.schema(),
        "configs": config_data[name],
    }


@app.post("/config/{name}/{version}")
def update_config(name: str, version: str, payload: dict = Body(...)):
    plugin: MySpec | None = pm.get_plugin(name)
    if not plugin:
        return {"error": "Plugin not found"}
    config_data[name][version] = plugin.config(payload)
    return payload
