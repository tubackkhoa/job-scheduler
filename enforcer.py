import importlib
import inspect
from casbin.fast_enforcer import FastEnforcer
from casbin_redis_adapter.adapter import Adapter
from casbin.enforcer import Enforcer
from functools import wraps
from jinja2 import pass_context
from dataclasses import dataclass
from typing import Literal, Optional, Set, TypedDict


class PermissionRule(TypedDict):
    subject: Literal["group", "role"]
    object: str
    permission: str
    action: str


# -----------------------------
# Casbin helper function
# -----------------------------


def has_role(ctx, role: str) -> bool:
    return role in ctx.roles or role in ctx.groups


# -----------------------------
# Enforcer factory
# -----------------------------


def create_enforcer() -> Enforcer:
    adapter = Adapter(
        host="localhost",
        port=6379,
        db=0,
        key="casbin_policy",
    )

    enforcer = FastEnforcer("model.conf", adapter)

    enforcer.enable_auto_save(False)
    enforcer.add_function("has_role", has_role)

    enforcer.load_policy()

    return enforcer


# -----------------------------
# Security model
# -----------------------------


@dataclass(frozen=True)
class Subject:
    user_id: str
    roles: Set[str]
    groups: Set[str]

    def __init__(
        self,
        user_id: str,
        roles: Optional[Set[str]] = None,
        groups: Optional[Set[str]] = None,
    ):
        object.__setattr__(self, "user_id", user_id)
        mapped_roles = {f"role:{role}" for role in (roles or set())}
        mapped_groups = {f"group:{group}" for group in (groups or set())}

        object.__setattr__(self, "roles", frozenset(mapped_roles))
        object.__setattr__(self, "groups", frozenset(mapped_groups))


class ExecutionContext:
    __slots__ = ("subject", "enforcer", "package")

    def __init__(self, subject: Subject, package: str, enforcer: Enforcer):
        self.subject = subject
        self.package = package
        self.enforcer = enforcer

    def allowed(self, permission_key: str, action: str = "execute") -> bool:
        allowed = self.enforcer.enforce(
            f"user:{self.subject.user_id}",
            permission_key,
            action,
            self.subject,
        )
        return allowed

    def require(self, permission_key: str, action: str = "execute"):
        if not self.allowed(permission_key, action):
            raise PermissionError(f"Permission denied: {permission_key}:{action}")


# -----------------------------
# Decorator
# -----------------------------


def require(permission_key: str, action: str = "execute"):
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
            allowed = ctx.allowed(
                permission,
                action,
            )

            if not allowed:
                raise PermissionError(f"Permission denied: {permission}:{action}")
            if accepts_ctx:
                kwargs["ctx"] = ctx
            return fn(*args, **kwargs)

        # metadata
        wrapper.__permission__ = permission_key
        wrapper.__action__ = action
        return wrapper

    return decorator
