from enforcer import ExecutionContext, global_permission, global_permissions
from models import DAO
from plugin_manager import PluginManager


class JobUtil:

    def __init__(self, dao: DAO):
        self.dao = dao
        # bind permission, because method instance only know at runtime
        global_permissions(self, "job", self.get_config)

    def get_config(
        self,
        ctx: ExecutionContext,
        job_id: int,
    ):
        job = self.dao.get_job(job_id)
        if not job:
            return {}
        plugin_item = self.dao.get_plugin(job.plugin_id)
        if not plugin_item:
            return {}
        plugin = PluginManager.get_plugin_instance(plugin_item.package)
        if not plugin:
            return {}
        config = plugin.config(ctx, job.config)
        return config.model_dump()
