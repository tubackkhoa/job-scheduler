from collections import defaultdict
from typing import Callable, Optional
from dataclasses import dataclass
from enforcer import Adapter, ExecutionContext, Function, create_enforcer, PermissionMap


class ACLResolver:
    def __init__(
        self,
        adapter: Optional[Adapter] = None,
        permission_map: Optional[PermissionMap] = None,
    ):
        self.enforcer = create_enforcer(adapter)
        self.permission_map = permission_map or defaultdict(set)

    def update_from_objects(self, *objects: object):
        """
        Scan objects (modules, instances, classes) for @permission-decorated callables.
        """
        for obj in objects:
            # 1️⃣ Direct callable
            if callable(obj):
                self._maybe_add_callable(obj)
                continue

            # 2️⃣ Scan object attributes
            for attr in vars(obj).values():
                self._maybe_add_callable(attr)

    def _maybe_add_callable(self, fn: object) -> None:
        """
        Add callable to ACL if it has permission metadata.
        """
        if callable(fn) and hasattr(fn, "__permission__"):
            self.permission_map[fn.__permission__].add(fn.__acl_item__)

    def get_allowed_functions(self, ctx: ExecutionContext) -> dict[str, Function]:
        allowed: dict[str, Function] = {}

        # ✅ Admin shortcut (policy-based, not role-based)
        is_admin = ctx.is_admin()

        # permission map can be update on the fly
        for permission, targets in self.permission_map.items():
            if not is_admin and not ctx.allowed(permission):
                continue
            for item in targets:
                allowed[item.name] = item.fn

        return allowed
