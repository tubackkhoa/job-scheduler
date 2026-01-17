import importlib
import inspect
from casbin.fast_enforcer import FastEnforcer
from casbin.persist import Adapter
from casbin.enforcer import Enforcer
from functools import wraps
from jinja2 import pass_context
from dataclasses import dataclass
from typing import Literal, Optional, Set, TypedDict

from auth import User

ADMIN_ROLE = "admin"


class ExecutionContext:
    __slots__ = ("user", "package", "_allowed")

    def __init__(self, user: User, package: str, enforcer: Enforcer):
        object.__setattr__(self, "user", user)
        object.__setattr__(self, "package", package)

        # preven closure access and change later, user is frozen already
        def _allowed(permission: str, _call=enforcer.enforce):
            return _call(user.id, permission, user.roles)

        object.__setattr__(self, "_allowed", _allowed)

    def __setattr__(self, name, value):
        # 🔒 block mutation after initialization
        if name in self.__slots__ and hasattr(self, name):
            raise AttributeError("ExecutionContext is immutable")
        super().__setattr__(name, value)

    def allowed(self, permission: str) -> bool:
        return self._allowed(permission)

    def is_admin(self):
        return ADMIN_ROLE in self.user.roles

    def require(self, permission: str):
        if not self.allowed(permission):
            raise PermissionError(f"Permission denied: {permission}")


# -----------------------------
# Casbin helper function
# -----------------------------
def has_role(roles: set[str], role: str) -> bool:
    return role in roles


# -----------------------------
# Enforcer factory
# -----------------------------


def create_enforcer(adapter: Optional[Adapter] = None) -> Enforcer:

    enforcer = FastEnforcer("model.conf", adapter)

    enforcer.enable_auto_save(False)
    enforcer.add_function("has_role", has_role)

    if enforcer.adapter:
        enforcer.load_policy()

    enforcer.add_policy(
        ADMIN_ROLE,
        "*",
    )

    return enforcer


# -----------------------------
# Security model
# -----------------------------


# -----------------------------
# Decorator
# -----------------------------


def require(permission_key: str):
    def decorator(fn):
        sig = inspect.signature(fn)
        accepts_ctx = "ctx" in sig.parameters

        @wraps(fn)
        @pass_context
        def wrapper(jinja_ctx, *args, **kwargs):
            ctx: ExecutionContext = jinja_ctx.get("ctx")
            if ctx is None:
                raise RuntimeError("ExecutionContext (ctx) is required")
            permission = f"{ctx.package}.{permission_key}"
            ctx.require(permission)

            if accepts_ctx:
                kwargs["ctx"] = ctx
            return fn(*args, **kwargs)

        # metadata
        wrapper.__permission__ = permission_key
        return wrapper

    return decorator
