# Plugin Permission System - Comprehensive Guide

## 📋 Overview

The Job Scheduler uses a **Casbin RBAC** (Role-Based Access Control)
permission system with:

- Permission Decorators: `@global_permission`, `@job_permission`
- Execution Context sandboxing
- Secure Fields (field-level permissions)
- Multi-version Plugins
- Jinja2 Template system with permission checks

---

## System Architecture

User → Auth → ExecutionContext → Casbin Enforcer → Plugin Execution

Core flow:

1.  User logs in
2.  `ExecutionContext` is created
3.  PluginManager runs plugin with context
4.  Permission decorators validate access
5.  Casbin enforcer evaluates RBAC policies

---

## Core Components

### User & Roles

```python
@dataclass(frozen=True)
class User:
    id: int
    roles: frozenset[str]
```

Roles are immutable for security.

Default roles:

- admin
- user

---

## Why `frozen=True` Matters

Security through immutability.

Benefits:

- Prevents role mutation attacks
- Thread-safe
- Hashable for caching
- Predictable permission evaluation

Comparison:

Type Mutable Hashable

---

set yes no
frozenset no yes

---

## ExecutionContext

The central permission container.

```python
class ExecutionContext:
    __slots__ = ("user", "package", "_allowed")

    def allowed(self, permission: str) -> bool:
        return self._allowed(permission)

    def require(self, permission: str):
        if not self.allowed(permission):
            raise PermissionError()
```

Key properties:

- immutable
- package scoped
- permission validator

---

## Immutability Design

Security layers:

1.  frozen User dataclass
2.  frozenset roles
3.  ExecutionContext slots
4.  custom setattr protection
5.  closure protected permission function

---

## Casbin Enforcer

Casbin handles RBAC policies.

Example model:

    [request_definition]
    r = sub, obj, ctx

    [policy_definition]
    p = sub, obj

Default policies:

- admin → \*
- user → job
- user → field

---

## Permission Types

### Global Permissions

Used for system-level actions.

Example:

```python
@global_permission("job")
def get_all_plugins(ctx: ExecutionContext):
    return session.query(Plugin).all()
```

Global permissions:

- plugin
- job
- field

---

### Job Permissions

Plugin scoped.

```python
@job_permission("fetch_data")
def fetch_data(ctx: ExecutionContext):
    return ctx.user
```

Permission format:

    {package}:{permission}

Example:

    sample_plugin:fetch_data

---

## Secure Fields

Used for config values requiring restricted access.

```python
class Config(SecureBaseModel):
    js_template: str = SecureField(
        "",
        read="code_read",
        write="code_write"
    )
```

Checks are applied during:

- attribute access
- validation
- schema generation
- serialization

---

## Plugin Development

### Plugin Structure

    plugins/
    ├── sample_plugin/
    ├── sample_plugin@v0_1_0/
    └── sample_plugin@v0_2_0/

Versioned folders represent plugin releases.

---

## Plugin Hooks

Example plugin:

```python
class Plugin:

    @hookimpl
    def env(cls):
        return {}

    @hookimpl
    def schema(cls, ctx):
        return Config.model_json_schema()

    @hookimpl
    def roles(cls):
        return {
            "fetch_data": {"data", "admin"}
        }

    @hookimpl
    async def run(cls, ctx, config, logger, render):
        logger.info("Running plugin")
        return True
```

---

## Permission Flow

1.  User requests job execution
2.  PluginManager creates ExecutionContext
3.  Plugin method called
4.  Decorator checks permission
5.  Casbin evaluates policy
6.  Allow or deny

---

## Template Rendering

Templates are rendered with injected context.

Example:

    {{ dao.get_value_version(id).value }}

Available in templates:

- DAO functions
- Plugin env functions
- context permissions

---

## Best Practices

DO:

- Use ExecutionContext in all secured functions
- Use decorators instead of manual checks
- Use SecureField for sensitive data
- Define plugin roles clearly

DON'T:

- bypass decorators
- hardcode admin checks
- expose secrets
- allow mutable permission state

---

## Common Security Patterns

### DAO Global Permission

```python
@global_permission("job")
def get_jobs(ctx: ExecutionContext):
    return session.query(Job).all()
```

### Plugin Permission

```python
@job_permission("fetch_external_data")
def fetch(ctx: ExecutionContext):
    return api_call()
```

### Secure Config

```python
class Config(SecureBaseModel):
    api_key = SecureField("", read="admin", write="admin")
```

---

## Key Takeaways

Concept Purpose

---

ExecutionContext user + plugin scope
global_permission system operations
job_permission plugin operations
SecureField field security
roles() permission mapping
plugin versions safe upgrades

---

## Related Files

- enforcer.py
- enforcer.conf
- auth.py
- plugin_manager.py
- plugins/schema.py
- models.py
