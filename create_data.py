from sqlalchemy import Engine
from sqlalchemy.orm import Session
import importlib
from models import Base, Job, Plugin

plugin_data = [
    {
        "package": "plugins.sample_plugin@v0_1_0.Plugin",
        "interval": 1,
        "description": "Sample plugin version 0.1.0 running frequently.",
    },
    {
        "package": "plugins.sample_plugin@v0_2_0.Plugin",
        "interval": 3,
        "description": "Sample plugin version 0.2.0 with slower interval.",
    },
    {
        "package": "plugins.lab_plugin@v0_1_0.LabPlugin",
        "interval": 3,
        "description": "Lab plugin for experimental features.",
    },
    {
        "package": "plugins.stable_plugin@v0_1_0.StablePlugin",
        "interval": 3,
        "description": "Stable plugin for production-like environments.",
    },
    {
        "package": "plugins.prod_plugin@v0_1_0.ProdPlugin",
        "interval": 3,
        "description": "Production plugin with standard interval.",
    },
]


def create_data(engine: Engine, user_ids: list[int] = [1, 2]):
    Base.metadata.create_all(engine)
    with Session(engine) as session:

        session.bulk_insert_mappings(Plugin.__mapper__, plugin_data)
        session.flush()

        # Get inserted plugins in order (by insertion order, since bulk_insert preserves it)
        plugins = session.query(Plugin).order_by(Plugin.id).all()

        for user_id in user_ids:
            for plugin_ind, (plugin_row, plugin_item) in enumerate(
                zip(plugins, plugin_data), start=1
            ):
                # Dynamically load the plugin class to get default config
                module_path, class_name = plugin_item["package"].rsplit(".", 1)
                module = importlib.import_module(module_path)
                plugin_class = getattr(module, class_name)

                default_config = plugin_class.config()  # Get default Pydantic model
                job = Job(
                    user_id=user_id,
                    plugin_id=plugin_row.id,  # Use actual inserted plugin ID
                    config=default_config.model_dump_json(),
                    active=0,
                    description=f"{plugin_item['description']} version 0.{plugin_ind}",
                )
                session.add(job)

        session.commit()
