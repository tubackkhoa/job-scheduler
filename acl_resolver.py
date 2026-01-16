import importlib
from typing import Any, Callable, Optional, TypedDict, Dict, Set, Literal, Union
from enforcer import ExecutionContext, create_enforcer
from utils import (
    list_trade_models,
    create_trade_model,
    deactivate_trade_model,
)
from models import DAO

# for global env
PERMISSION_MAP: Dict[str, set[str | Callable]] = {
    "plugin": {"get_all_plugins"},
    "job": {
        "apply_value_version_all_jobs",
        "get_jobs_by_plugin_and_session",
        list_trade_models,
        create_trade_model,
        deactivate_trade_model,
    },
    "field": {
        "create_value_version",
        "get_value_version",
        "get_value_versions",
        "update_value_version",
    },
}


class ACLResolver:
    def __init__(self, dao: DAO):
        self.enforcer = create_enforcer()
        # default role
        self.enforcer.add_policy(
            "role:admin",
            "system.admin",
            "execute",
        )
        self.dao = dao

    def get_allowed_functions(self, ctx: ExecutionContext) -> dict[str, Callable]:
        allowed: dict[str, Callable] = {}

        # ✅ Admin shortcut (policy-based, not role-based)
        is_admin = ctx.allowed("system.admin", action="execute")

        for permission, functions in PERMISSION_MAP.items():
            if is_admin or ctx.allowed(permission, action="execute"):
                for target in functions:
                    if callable(target):
                        allowed[target.__name__] = target
                    else:
                        allowed[target] = getattr(self.dao, target)

        return allowed
