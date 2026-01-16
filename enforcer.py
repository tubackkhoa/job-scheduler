import importlib
import inspect
from casbin.fast_enforcer import FastEnforcer
from casbin_redis_adapter.adapter import Adapter
from casbin.enforcer import Enforcer
from functools import wraps
from jinja2 import pass_context
from dataclasses import dataclass
from typing import Literal, Optional, Set, TypedDict


@dataclass(frozen=True)
class Subject:
    user_id: str
    roles: frozenset[str]

    def __init__(
        self,
        user_id: str,
        roles: Optional[Set[str]] = None,
    ):
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(
            self,
            "roles",
            frozenset(f"role:{r}" for r in roles or ()),
        )


class ExecutionContext:
    __slots__ = ("subject", "package", "_user", "_allowed")

    def __init__(self, subject: Subject, package: str, enforcer: Enforcer):
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "package", package)
        object.__setattr__(self, "_user", f"user:{subject.user_id}")

        object.__setattr__(
            self,
            "_allowed",
            lambda permission: enforcer.enforce(
                self._user,
                permission,
                self.subject,
            ),
        )

    def __setattr__(self, name, value):
        # 🔒 block mutation after initialization
        if name in self.__slots__ and hasattr(self, name):
            raise AttributeError("ExecutionContext is immutable")
        super().__setattr__(name, value)

    def allowed(self, permission: str) -> bool:
        return self._allowed(permission)

    def is_admin(self):
        return self.allowed("system.admin")

    def require(self, permission: str):
        # ✅ Admin short-circuit (policy-based, wildcard-aware)
        if self.is_admin():
            return

        if not self.allowed(permission):
            raise PermissionError(f"Permission denied: {permission}")


# -----------------------------
# Casbin helper function
# -----------------------------
def has_role(subject: Subject, role: str) -> bool:
    return role in subject.roles


# -----------------------------
# Enforcer factory
# -----------------------------


def create_enforcer(adapter: Adapter) -> Enforcer:

    enforcer = FastEnforcer("model.conf", adapter)

    enforcer.enable_auto_save(False)
    enforcer.add_function("has_role", has_role)

    enforcer.load_policy()

    enforcer.add_policy(
        "role:admin",
        "system.admin",
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
