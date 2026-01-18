from typing import Callable, Optional, Dict
from enforcer import Adapter, ExecutionContext, GlobalItem, create_enforcer, GlobalPermissions


class ACLResolver:
    def __init__(
        self,
        permission_map: Dict[GlobalPermissions, set[GlobalItem]],
        adapter: Optional[Adapter] = None,
    ):
        self.enforcer = create_enforcer(adapter)
        self.permission_map = permission_map

    def get_allowed_functions(self, ctx: ExecutionContext) -> dict[str, Callable]:
        allowed: dict[str, Callable] = {}

        # ✅ Admin shortcut (policy-based, not role-based)
        is_admin = ctx.is_admin()

        # permission map can be update on the fly
        for permission, targets in self.permission_map.items():
            if not is_admin and not ctx.allowed(permission):
                continue
            for item in targets:
                if isinstance(item, tuple):
                    name, fn = item
                else:
                    fn = item
                    name = fn.__name__

                allowed[name] = fn

        return allowed
