import importlib
import inspect
from casbin.fast_enforcer import FastEnforcer
from casbin.persist import Adapter
from casbin.enforcer import Enforcer
from functools import wraps
from jinja2 import pass_context
from jinja2.runtime import Context
from dataclasses import dataclass
from typing import Callable, Literal, Optional, Set, Tuple, TypedDict, Union, Any

from auth import User

ADMIN_ROLE = "admin"
USER_ROLE = "user"
GlobalPermissions = Literal["plugin", "job", "field"]
Function = Callable[..., Any]
GlobalItem = Function | tuple[str, Function]
PERMISSION_KEYS: set[GlobalPermissions] = {"plugin", "job", "field"}

POLICIES = [
    [ADMIN_ROLE, "*"],
    [USER_ROLE, "job"],
    [USER_ROLE, "field"],
]


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

    enforcer.add_policies(POLICIES)

    return enforcer


# require must always pass ctx so that it can handle in more detail, but permission is optional to check
def require(permission_key: Optional[str] = None):
    def decorator(fn):
        @wraps(fn)
        @pass_context
        def wrapper(*args, **kwargs):
            # Locate Jinja Context in args
            for idx, arg in enumerate(args):
                if isinstance(arg, Context):
                    jinja_ctx = arg
                    break
            else:
                raise RuntimeError("Jinja Context is required")

            # Extract ExecutionContext
            try:
                ctx: ExecutionContext = jinja_ctx["ctx"]
            except KeyError as e:
                raise RuntimeError("ExecutionContext (ctx) is required") from e

            # Replace Jinja Context with ExecutionContext
            args = list(args)
            args[idx] = ctx

            # Optional permission check
            if permission_key:
                permission = (
                    permission_key
                    if permission_key in PERMISSION_KEYS
                    else f"{ctx.package}.{permission_key}"
                )
                ctx.require(permission)

            return fn(*args, **kwargs)

        wrapper.__permission__ = permission_key
        return wrapper

    return decorator
