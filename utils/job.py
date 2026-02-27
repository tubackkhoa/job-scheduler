from enforcer import ExecutionContext, global_permission
from models import DAO
from plugin_manager import PluginManager


class JobUtil:

    def __init__(self, dao: DAO):
        self.dao = dao

    @global_permission("job")
    async def get_config(
        self,
        ctx: ExecutionContext,
        job_id: int,
    ):
        job = await self.dao.get_job(job_id)
        if not job:
            return {}
        plugin_item = self.dao.plugin_cache.get(job.plugin_id)
        if not plugin_item:
            return {}
        plugin = PluginManager.get_plugin_instance(plugin_item[1])
        if not plugin:
            return {}
        return plugin.config(ctx, job.config).model_dump(mode="json")
