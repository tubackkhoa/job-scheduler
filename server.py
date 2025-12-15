import importlib
import abc
from typing import Any
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import pluggy


PROJECT_NAME = "alpha-miner"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)


class MySpec(abc.ABC):
    @hookspec
    @abc.abstractmethod
    def init(self, config) -> dict[str, Any]:
        """Return awaitables (coroutines)"""
        pass

    @hookspec
    @abc.abstractmethod
    def migrate(self, new_config) -> dict[str, Any]:
        pass

    @hookspec
    @abc.abstractmethod
    def schema(self) -> dict[str, Any]:
        pass

    @hookspec
    @abc.abstractmethod
    def config(self) -> dict[str, Any]:
        pass

    @hookspec
    @abc.abstractmethod
    async def run(self) -> Any:
        pass


pm = pluggy.PluginManager(PROJECT_NAME)
pm.add_hookspecs(MySpec)

plugin_data = [
    {"package": "plugins.plugin1", "name": "Plugin1"},
    {
        "package": "plugins.plugin2",
        "name": "Plugin2",
    },
    {"package": "plugins.lab_plugin", "name": "LabPlugin"},
    {
        "package": "plugins.stable_plugin",
        "name": "StablePlugin",
    },
    {
        "package": "plugins.prod_plugin",
        "name": "ProdPlugin",
    },
]

config_data = {}

# 🔥 dynamically load all plugins
for plugin_item in plugin_data:
    module = importlib.import_module(plugin_item["package"])
    plugin_cls = getattr(module, plugin_item["name"])
    instance: MySpec = plugin_cls()
    if "config" in plugin_item:
        instance.init(plugin_item["config"])
    name = plugin_item["package"] + "." + plugin_item["name"]
    pm.register(instance, name)
    config_data[name] = {
        "version 1.0": instance.config(),
        "version 2.0": instance.config(),
    }

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
    return [
        plugin_item["package"] + "." + plugin_item["name"]
        for plugin_item in plugin_data
    ]


@app.get("/schema/{name}")
def schema(name: str):
    module_instance = pm.get_plugin(name)
    if module_instance != None:
        return {
            "schema": module_instance.schema(),
            "configs": config_data[name],
        }


@app.post("/config/{name}/{version}")
def update_config(name: str, version: str, payload: dict = Body(...)):
    plugin: MySpec | None = pm.get_plugin(name)
    if not plugin:
        return {"error": "Plugin not found"}
    result = plugin.migrate(payload)
    config_data[name][version] = result
    return result
