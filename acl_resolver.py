from typing import Optional
from enforcer import Adapter, ExecutionContext, Function, create_enforcer


class ACLResolver:
    def __init__(
        self,
        adapter: Optional[Adapter] = None,
    ):
        self.enforcer = create_enforcer(adapter)
        self.functions: set[Function] = set()

    def add_functions(self, *objects: Function):
        """
        Scan objects (modules, instances, classes) for @permission-decorated callables.
        """
        for fn in objects:
            if not hasattr(fn, "__permission__"):
                raise ValueError(f"{fn.__name__} is missing @permission decorator")
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
