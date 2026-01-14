from sqlalchemy import Engine
from sqlalchemy.orm import Session
import importlib
from models import Base, Job, Plugin
from plugin_manager import PluginSpec

PLUGIN_DATA = [
    {
        "package": "alpha_miner.plugins.UatUserCustomConfigPlugin",
        "interval": 1,
        "description": "Mock user custom config plugin for testing.",
    },
]


def create_data(engine: Engine, session_ids: list[int] = [1, 2], plugin_data=PLUGIN_DATA):
    Base.metadata.create_all(engine)
    with Session(engine) as session:

        session.bulk_insert_mappings(Plugin.__mapper__, plugin_data)
        session.flush()

        # Get inserted plugins in order (by insertion order, since bulk_insert preserves it)
        plugins = session.query(Plugin).order_by(Plugin.id).all()

        for session_id in session_ids:
            for plugin_ind, (plugin_row, plugin_item) in enumerate(
                zip(plugins, plugin_data), start=1
            ):
                # Dynamically load the plugin class to get default config
                module_path, class_name = plugin_item["package"].rsplit(".", 1)
                module = importlib.import_module(module_path)
                plugin_class: PluginSpec = getattr(module, class_name)

                default_config = plugin_class.config()  # Get default Pydantic model
                job = Job(
                    session_id=session_id,
                    plugin_id=plugin_row.id,  # Use actual inserted plugin ID
                    config=default_config.model_dump_json(),
                    active=True,
                    description=f"{plugin_item['description']} version 0.{plugin_ind}",
                )
                session.add(job)

        session.commit()
