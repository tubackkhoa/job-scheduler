import importlib
from typing import Any, Optional, TypedDict, Dict, Set, Literal, Union
from enforcer import ExecutionContext, create_enforcer
from utils import (
    list_trade_models,
    create_trade_model,
    deactivate_trade_model,
)
from models import DAO


PERMISSION_MAP: Dict[str, Any] = {
    # plugin
    "plugin.get_all_plugins": "get_all_plugins",
    # job
    "job.apply_value_version_all_jobs": "apply_value_version_all_jobs",
    "job.get_jobs_by_plugin_and_session": "get_jobs_by_plugin_and_session",
    "job.list_trade_models": list_trade_models,
    "job.create_trade_model": create_trade_model,
    "job.deactivate_trade_model": deactivate_trade_model,
    # field
    "field.create_value_version": "create_value_version",
    "field.get_value_version": "get_value_version",
    "field.get_value_versions": "get_value_versions",
    "field.update_value_version": "update_value_version",
}


class ACLResolver:
    def __init__(self, dao: DAO):
        self.enforcer = create_enforcer()
        self.dao = dao

    def get_allowed_functions(self, ctx: ExecutionContext) -> Dict[str, Any]:
        allowed: Dict[str, Any] = {}

        # ✅ Admin shortcut (policy-based, not role-based)
        is_admin = ctx.allowed("system.admin", action="execute")

        for permission, target in PERMISSION_MAP.items():
            if is_admin or ctx.allowed(permission, action="execute"):
                if callable(target):
                    allowed[permission] = target
                else:
                    allowed[permission] = getattr(self.dao, target)

        return allowed
