import importlib
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import pluggy


PROJECT_NAME = "alpha-miner"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)

class MySpec:
    @hookspec
    def init(self, config):
        """Return awaitables (coroutines)"""
        pass

    @hookspec
    def migrate(self, new_config):
        pass

    @hookspec
    def schema(self):
        pass

    @hookspec
    def config(self):
        pass

    @hookspec
    async def run(self):
        pass

pm = pluggy.PluginManager(PROJECT_NAME)
pm.add_hookspecs(MySpec)

plugin_data = [
    {
        "package": "plugins.plugin1",
        "name": "Plugin1",
        "config": {
            "version":"1.0"
        }
    },
    {
        "package": "plugins.plugin2",
        "name": "Plugin2",
        "config": {
            "version":"2.0"
        }
    }
]

# 🔥 dynamically load all plugins
for plugin_item in plugin_data:
    module = importlib.import_module(plugin_item["package"])
    plugin_cls = getattr(module, plugin_item["name"])
    instance = plugin_cls()
    instance.init(plugin_item["config"])
    pm.register(instance, plugin_item["package"] + '.' + plugin_item["name"])

# validate implementation
pm.check_pending()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/plugins")
def plugins():    
    return [plugin_item["package"] + '.' + plugin_item["name"] for plugin_item in plugin_data]

@app.get("/schema/{name}")
def schema(name:str):    
    module_instance = pm.get_plugin(name)
    if module_instance != None:
        return {
            "schema": module_instance.schema(),
            "data": module_instance.config(),
        }

@app.post("/config/{name}")
async def run_plugin(name: str, payload: dict = Body(...)):
    plugin = pm.get_plugin(name)
    if not plugin:
        return {"error": "Plugin not found"}

    result = plugin.migrate(payload)
    return result