import importlib
from typing import Any, Callable, Optional, TypedDict, Dict, Set, Literal, Union
from enforcer import Adapter, Enforcer, ExecutionContext, create_enforcer
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
    def __init__(self, dao: DAO, adapter: Optional[Adapter] = None):
        self.enforcer = create_enforcer(adapter)
        self.dao = dao

    def get_allowed_functions(self, ctx: ExecutionContext) -> dict[str, Callable]:
        allowed: dict[str, Callable] = {}

        # ✅ Admin shortcut (policy-based, not role-based)
        is_admin = ctx.is_admin()

        for permission, targets in PERMISSION_MAP.items():
            if not is_admin and not ctx.allowed(permission):
                continue

            for target in targets:
                if callable(target):
                    allowed[target.__name__] = target
                else:
                    allowed[target] = getattr(self.dao, target)

        return allowed
