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
R = TypeVar("R", covariant=True)


GLOBAL_PERMISSION_REGISTRY: dict[str, Callable] = {}


# make GLOBAL_PERMISSION_REGISTRY frozen, other module can only access reference so can not change it later
def freeze_permission_registry():
    global GLOBAL_PERMISSION_REGISTRY
    if not isinstance(GLOBAL_PERMISSION_REGISTRY, MappingProxyType):
        GLOBAL_PERMISSION_REGISTRY = MappingProxyType(GLOBAL_PERMISSION_REGISTRY)  # type: ignore


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


def _resolve_ctx(args):
    for i, arg in enumerate(args):
        if isinstance(arg, ExecutionContext):
            return arg, args
        if isinstance(arg, Context):
            ctx = arg["ctx"]
            args = tuple(ctx if j == i else a for j, a in enumerate(args))
            return ctx, args
    raise RuntimeError("ExecutionContext is required")


def _with_execution_policy(
    fn: Callable[P, R], permission_key: GlobalPermissions | str | None, global_scope: bool = False
) -> Callable[P, R]:
    @pass_context
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Locate Jinja Context
        ctx, args = _resolve_ctx(args)

        if permission_key:
            permission = permission_key if global_scope else f"{ctx.package}:{permission_key}"
            ctx.require(permission)

        return fn(*args, **kwargs)

    return wrapper


# declarative, static
def global_permission(
    permission_key: GlobalPermissions, name: Optional[str] = None
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        wrapped = _with_execution_policy(fn, permission_key, True)
        wrapped.__permission__ = permission_key

        # register into GLOBAL_PERMISSION_REGISTRY for globals
        key = name or fn.__name__

        if key in GLOBAL_PERMISSION_REGISTRY:
            raise RuntimeError(f"Duplicate permission name: {key}")

        GLOBAL_PERMISSION_REGISTRY[key] = wrapped

        return wrapped

    return decorator


# job_permission: runtime enforcement
def job_permission(permission_key: Optional[str] = None):
    def decorator(fn: Callable):
        return _with_execution_policy(fn, permission_key)

    return decorator


def _apply_permissions(obj, decorator, *names):
    for name in names:
        attr = getattr(obj, name) if isinstance(name, str) else name
        key = name if isinstance(name, str) else attr.__name__
        setattr(obj, key, decorator(attr))


def global_permissions(obj: object, permission_key: GlobalPermissions, *names: str | Callable):
    _apply_permissions(obj, lambda fn: global_permission(permission_key, fn.__name__)(fn), *names)


def job_permissions(obj: object, permission_key: Optional[str] = None, *names: str | Callable):
    _apply_permissions(obj, job_permission(permission_key), *names)
