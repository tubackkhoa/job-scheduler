import importlib
import inspect
from casbin.fast_enforcer import FastEnforcer
from casbin.persist import Adapter
from casbin.enforcer import Enforcer
from functools import wraps
from jinja2 import pass_context
from jinja2.runtime import Context
from dataclasses import dataclass
from typing import (
    Callable,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypedDict,
    Union,
    Any,
    runtime_checkable,
)

from auth import User

ADMIN_ROLE = "admin"
USER_ROLE = "user"
GlobalPermissions = Literal["plugin", "job", "field"]
PERMISSION_KEYS: set[GlobalPermissions] = {"plugin", "job", "field"}

POLICIES = [
    [ADMIN_ROLE, "*"],
    [USER_ROLE, "job"],
    [USER_ROLE, "field"],
]


@runtime_checkable
class Function(Protocol):
    __permission__: GlobalPermissions
    __acl_name__: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


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


# declarative, static
def global_permission(permission_key: GlobalPermissions, *, name: Optional[str] = None):
    """
    Declarative permission decorator.

    - Attaches permission metadata
    - Does NOT enforce access
    - Does NOT wrap the function
    """

    def decorator(fn: Function) -> Function:
        # Attach metadata
        fn.__permission__ = permission_key
        fn.__acl_name__ = name or fn.__name__

        return fn

    return decorator


# require_permission: runtime enforcement
def require_permission(permission_key: Optional[str] = None):
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

            # Optional permission check, with : to avoid name collision
            if permission_key:
                ctx.require(f"{ctx.package}:{permission_key}")

            return fn(*args, **kwargs)

        wrapper.__permission__ = permission_key
        return wrapper

    return decorator
