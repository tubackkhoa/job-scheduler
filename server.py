import asyncio
import importlib
import sys
from typing import Any, Optional
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import pluggy
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

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

    def __init__(self, plugin_items: list[Any]) -> None:
        self.pm = pluggy.PluginManager(PROJECT_NAME)
        self.config_data = {}
        self.scheduler = BackgroundScheduler()
        self.pm.add_hookspecs(MySpec)
        for item in plugin_items:
            self.load_plugin(item["package"], interval=item.get("interval"))

        # validate implementation
        self.pm.check_pending()

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()

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
        return [name for name, _ in self.pm.list_name_plugin()]

    def get_plugin(self, name: str) -> Optional[MySpec]:
        return self.pm.get_plugin(name)

    def run_sync_wrapper(self, name: str, version: str):
        plugin = self.get_plugin(name)
        if plugin is not None:
            config = self.config_data[name][version]
            return asyncio.run(plugin.run(config))

    def load_plugin(
        self,
        name: str,
        override: bool = False,
        json: Optional[Any] = None,
        interval=3,
    ):
        module_path, class_name = name.rsplit(".", 1)

        if override:
            # unregister hook
            existing = self.pm.get_plugin(name)
            if existing is not None:
                self.pm.unregister(existing, name)

            # cancel job
            self.scheduler.remove_job(name + "/version 1.0")

            # unload module
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

        self.scheduler.add_job(
            self.run_sync_wrapper,
            "interval",
            seconds=interval,
            args=[name, "version 1.0"],
            id=name + "/version 1.0",  # unique config id
        )

        return plugin


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
