import importlib
from models import Job, Plugin
from plugin_manager import PluginSpec
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


plugin_data = [
    {"package": "plugins.sample_plugin@v0_1_0.Plugin", "interval": 5},
    {"package": "plugins.sample_plugin@v0_2_0.Plugin", "interval": 3},
    {"package": "plugins.lab_plugin@v0_1_0.LabPlugin", "interval": 3},
    {"package": "plugins.stable_plugin@v0_1_0.StablePlugin", "interval": 3},
    {"package": "plugins.prod_plugin@v0_1_0.ProdPlugin", "interval": 3},
]


engine = create_engine("sqlite:///data/apscheduler_events.db")
with Session(engine) as session:

    session.bulk_insert_mappings(Plugin.__mapper__, plugin_data)

    plugin_ind = 1
    for item in plugin_data:
        # import module
        module_path, class_name = item["package"].rsplit(".", 1)
        module = importlib.import_module(module_path)
        plugin: PluginSpec = getattr(module, class_name)
        config = plugin.config()
        print(config.model_dump_json())
        job = Job(
            user_id=1,
            plugin_id=plugin_ind,
            config=config.model_dump_json(),
            active=0,
            description="version 0.2",
        )
        session.add(job)
        plugin_ind += 1

    session.commit()
