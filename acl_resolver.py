from collections import defaultdict
from typing import Callable, Optional
from dataclasses import dataclass
from enforcer import ACLItem, Adapter, ExecutionContext, Function, create_enforcer, PermissionMap


class ACLResolver:
    def __init__(
        self,
        adapter: Optional[Adapter] = None,
    ):
        self.enforcer = create_enforcer(adapter)
        self.functions: set[Function] = set()

    def add_functions(self, *objects: object):
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
            self.functions.add(fn)

    def get_allowed_functions(self, ctx: ExecutionContext) -> dict[str, Function]:
        allowed: dict[str, Function] = {}

        # ✅ Admin shortcut (policy-based, not role-based)
        is_admin = ctx.is_admin()

        # permission map can be update on the fly
        for fn in self.functions:
            if not is_admin and not ctx.allowed(fn.__permission__):
                continue
            # add to globals environment
            allowed[fn.__acl_name__] = fn

        return allowed
