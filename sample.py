import asyncio
import importlib
import pluggy
import inspect

PROJECT_NAME = "alpha-miner"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)

class MySpec:
    @hookspec
    def init(self, config):
        """Return awaitables (coroutines)"""
        pass

    @hookspec
    def migrate(self, old_config, new_config):
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

plugin1_instance = pm.get_plugin("plugins.plugin1.Plugin1")
if plugin1_instance != None:
    # migrate config if version is change, for example mapping field from old_fields to new_fields
    plugin1_instance.migrate({"version":"1.0.1"})


async def main():    
    results = await asyncio.gather(*pm.hook.run())
    print(results)


asyncio.run(main())
