from dataclasses import dataclass
from functools import wraps
from types import MappingProxyType
from typing import Any, Callable, Literal, Optional, ParamSpec, Protocol, TypeVar, runtime_checkable

from casbin.enforcer import Enforcer
from casbin.fast_enforcer import FastEnforcer
from casbin.persist import Adapter
from jinja2 import pass_context
from jinja2.runtime import Context

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


P = ParamSpec("P")
R = TypeVar("R")


@runtime_checkable
class PermissionedFunction(Protocol[P, R]):
    __permission__: GlobalPermissions
    __acl_name__: str

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


GLOBAL_PERMISSION_REGISTRY: dict[str, PermissionedFunction] = {}


# make GLOBAL_PERMISSION_REGISTRY frozen, other module can only access reference so can not change it later
def freeze_permission_registry():
    global GLOBAL_PERMISSION_REGISTRY
    GLOBAL_PERMISSION_REGISTRY = MappingProxyType(GLOBAL_PERMISSION_REGISTRY)


class ExecutionContext:
    __slots__ = ("user", "package", "_allowed")

    def __init__(self, user: User, package: Optional[str], enforcer: Enforcer):
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

    enforcer = FastEnforcer("enforcer.conf", adapter)

    enforcer.enable_auto_save(False)
    enforcer.add_function("has_role", has_role)

    if enforcer.adapter:
        enforcer.load_policy()

    enforcer.add_policies(POLICIES)

    return enforcer


def _with_execution_policy(
    fn: Callable[P, R], permission_key: GlobalPermissions | str, global_scope: bool = False
) -> Callable[P, R]:
    @pass_context
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Locate Jinja Context
        for idx, arg in enumerate(args):
            if isinstance(arg, ExecutionContext):
                ctx = arg
                break
            if isinstance(arg, Context):
                ctx = arg["ctx"]
                # Replace Jinja Context with ExecutionContext
                args = tuple(ctx if i == idx else arg for i, arg in enumerate(args))
                break

        if not ctx:
            raise RuntimeError("ExecutionContext is required")

        if permission_key:
            permission = permission_key if global_scope else f"{ctx.package}:{permission_key}"
            ctx.require(permission)

        return fn(*args, **kwargs)

    return wrapper


# declarative, static
def global_permission(
    permission_key: GlobalPermissions, name: Optional[str] = None
) -> Callable[[Callable[P, R]], PermissionedFunction[P, R]]:
    def decorator(fn: Callable[P, R]) -> PermissionedFunction[P, R]:
        fn = _with_execution_policy(fn, permission_key, True)

        fn.__permission__ = permission_key

        # register into GLOBAL_PERMISSION_REGISTRY for globals
        key = name or fn.__name__

        if key in GLOBAL_PERMISSION_REGISTRY:
            raise RuntimeError(f"Duplicate permission name: {key}")
        print("register", key)
        GLOBAL_PERMISSION_REGISTRY[key] = fn

        return fn

    return decorator


# job_permission: runtime enforcement
def job_permission(permission_key: Optional[str] = None):
    def decorator(fn: Callable):
        return _with_execution_policy(fn, permission_key)

    return decorator
