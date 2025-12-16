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


class PluginManager:

    pm = pluggy.PluginManager(PROJECT_NAME)
    config_data = {}

    def __init__(self, plugin_items: list[str]) -> None:
        self.pm.add_hookspecs(MySpec)
        for name in plugin_items:
            self.load_plugin(name)

        # validate implementation
        self.pm.check_pending()

    def unload_module(self, module_path: str):
        # clear old code of the module
        modules_to_remove = [
            name
            for name in sys.modules
            if name == module_path or name.startswith(module_path + ".")
        ]
        for mod_name in modules_to_remove:
            del sys.modules[mod_name]

    def get_plugin_names(self):
        return [item[0] for item in self.pm.list_name_plugin()]

    def get_plugin(self, name: str):
        plugin: MySpec | None = self.pm.get_plugin(name)
        return plugin

    def load_plugin(
        self, name: str, override: bool = False, json: Optional[Any] = None
    ):
        module_path, class_name = name.rsplit(".", 1)

        if override:
            # unregister hook
            existing = self.pm.get_plugin(name)
            if existing is not None:
                self.pm.unregister(existing, name)

            self.unload_module(module_path)

        # import module
        module = importlib.import_module(module_path)
        plugin: MySpec = getattr(module, class_name)
        config = plugin.config(json)

        self.pm.register(plugin, name)
        self.config_data[name] = {
            "version 1.0": config,
            "version 2.0": config,
        }
        return plugin


plugin_manager = PluginManager(
    [
        "plugins.sample_plugin@v0_1_0.Plugin",
        "plugins.sample_plugin@v0_2_0.Plugin",
        "plugins.lab_plugin@v0_1_0.LabPlugin",
        "plugins.stable_plugin@v0_1_0.StablePlugin",
        "plugins.prod_plugin@v0_1_0.ProdPlugin",
    ]
)

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
    plugin_manager.config_data[name][version] = plugin.config(payload)
    return plugin_manager.config_data[name][version]
