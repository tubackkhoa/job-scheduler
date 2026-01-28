import importlib
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from models import Base, Plugin, Job
from plugin_manager import PluginManager
from auth import UserContext
from enforcer import ADMIN_ROLE
from plugin_manager import PluginSpec

PLUGIN_DATA = [
    {
        "package": "alpha_miner.plugins.UatUserCustomConfigPlugin",
        "interval": 1,
        "description": "Mock user custom config plugin for testing.",
    },
]


async def create_data(
    engine: AsyncEngine,
    session_ids: list[int] = [1, 2],
    plugin_data=None,
):
    if plugin_data is None:
        plugin_data = PLUGIN_DATA

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Insert plugins (async-safe)
        plugins = []
        for item in plugin_data:
            plugin = Plugin(**item)
            session.add(plugin)
            plugins.append(plugin)

        await session.flush()  # populate plugin.id

        # Insert jobs
        for session_id in session_ids:
            for plugin_ind, (plugin_row, plugin_item) in enumerate(
                zip(plugins, plugin_data), start=1
            ):
                module_path, class_name = plugin_item["package"].rsplit(".", 1)
                module = importlib.import_module(module_path)
                plugin_class: PluginSpec = getattr(module, class_name)

                ctx = PluginManager.create_ctx(UserContext(0, frozenset({ADMIN_ROLE})))

                default_config = plugin_class.config(ctx)

                job = Job(
                    session_id=session_id,
                    plugin_id=plugin_row.id,
                    config=default_config.model_dump(),
                    active=True,
                    description=f"{plugin_item['description']} version 0.{plugin_ind}",
                )
                session.add(job)

        await session.commit()
