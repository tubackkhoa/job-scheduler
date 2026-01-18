from functools import partial
import json
from enforcer import ExecutionContext, global_permission, require_permission
from models import DAO
from plugin_manager import PluginManager
from plugins.schema import SecureBaseModel


class JobUtil:

    def __init__(self, dao: DAO):
        self.dao = dao

    @global_permission("job")
    @require_permission()
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
        config = plugin.config(json.loads(job.config))
        SecureBaseModel.bind_ctx(config, ctx)
        return config.model_dump()
