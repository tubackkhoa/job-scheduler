# Plugin Development Guide

This document explains how to create, structure, and secure plugins for the Job-Scheduler system.

Plugins are modular extensions loaded via Pluggy and registered in the database. Each plugin lives in its own folder and exposes a `Plugin` class implementing the required hooks.

---

## 1. Plugin architecture overview

A plugin provides:

- UI integration (React portals/pages)
- Backend logic callable from templates
- Optional scheduled job execution
- Role/permission declarations
- Schema/config definition via Pydantic

Plugins are:

- Discovered via the `plugins/` directory
- Loaded dynamically using Pluggy
- Referenced in DB using:

  ```
  plugins.<plugin_name>@<version>.Plugin
  ```

Example:

```
plugins/blog@0_1_0.Plugin
```

---

## 2. Folder structure

Each plugin must be placed under:

```
plugins/<plugin_name>@<version>/
```

Example:

```
plugins/blog@0_1_0/
├── __init__.py
├── dao.py
├── model.py
└── plugin.py
```

Naming rules:

- snake_case plugin name
- version suffix with underscores:
  - `0_1_0`
  - `1_2_3`

- Avoid dots in folder names

---

## 3. Required files

### `__init__.py`

```python
from .plugin import Plugin

__all__ = ["Plugin"]
```

This exposes the Plugin class for dynamic loading.

---

### `plugin.py` (required)

This is the entry point.

It must define:

- Pydantic Config model
- `Plugin` class
- Pluggy hook implementations

---

### Optional files

| File       | Purpose           |
| ---------- | ----------------- |
| `dao.py`   | DB logic          |
| `model.py` | SQLAlchemy models |
| `data.py`  | Helpers/constants |

---

## 4. Required Pluggy hooks

Your Plugin class should implement the following hooks.

### routes()

Defines frontend routes and portal entrypoints.

```python
@hookimpl
def routes(cls) -> list[tuple[str, Any]]:
    return cls._routes
```

Each tuple:

```
(route_path, metadata)
```

Example:

```
("", portal_config)
("dashboard", dashboard_config)
("blog/:id", blog_page_config)
```

---

### env()

Provides functions accessible to templates.

```python
@hookimpl
def env(cls) -> dict[str, Any]:
    return {
        "get_posts": get_posts,
        "create_post": create_post,
    }
```

Use this to expose DAO functions safely.

---

### schema(ctx)

Returns the JSON schema used by the frontend form builder.

```python
@hookimpl
def schema(cls, ctx):
    return Config.model_json_schema()
```

---

### config(ctx, json, validate)

Parses and validates configuration.

```python
@hookimpl
def config(cls, ctx, json=None, validate=False):
    return Config.model_validate(json or {})
```

---

### run(ctx, config, logger, render)

Async job logic (executed by scheduler).

```python
@hookimpl
async def run(cls, ctx, config, logger, render):
    return True
```

Notes:

- Always async
- Use logger for output
- Use render() for templating

---

### roles()

Declares plugin-level permissions.

```python
@hookimpl
def roles(cls):
    return {
        "read": {"user"},
        "write": {"admin"},
    }
```

---

### install()

Runs when plugin is installed.

```python
@hookimpl
def install(cls) -> bool:
    return True
```

---

## 5. Config model (Pydantic)

Each plugin should define a Config model.

Example:

```python
class Config(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=ui_schema({
            "url": "{base_url}/assets/{package}/portal.js"
        })
    )
```

Use:

- `Field(...)` for validation
- `ui_schema(...)` for UI hints

---

## 6. Database usage (DAO pattern)

Recommended layout:

- SQLAlchemy models in `model.py`
- CRUD in `dao.py`

Example secured DAO function:

```python
@job_permission("blog")
def create_post(ctx, title: str, description: str, content: str):
```

Key rules:

- Always accept `ctx` as first param
- Use `job_permission` decorator
- Validate inputs
- Close DB sessions

---

## 7. Permissions & security

Always enforce permissions on write operations:

```
@job_permission("blog")
```

Use ExecutionContext:

- Identifies user/session
- Controls access to protected actions

Never:

- Trust user input blindly
- Hardcode credentials
- Skip permission checks on mutations

---

## 8. Frontend integration

Routes return metadata describing where UI is located:

Dev:

```
blog/Home.tsx
```

Prod:

```
{base_url}/assets/{package}/home.js
```

This allows dynamic UI loading.

---

## 9. Registering a plugin

Insert into DB:

| Field       | Value                                                         |
| ----------- | ------------------------------------------------------------- |
| package     | [plugins.blog@0_1_0.Plugin](mailto:plugins.blog@0_1_0.Plugin) |
| interval    | 60                                                            |
| description | Blog system                                                   |

Then restart server or reload plugin.

---

## 10. Versioning strategy

Use semantic-style versions:

```
@0_1_0
@0_2_0
@1_0_0
```

Never modify old versions.

Create a new folder instead.

---

## 11. Best practices

- Use type hints everywhere
- Keep business logic in DAO
- Keep Plugin class thin
- Use async for I/O
- Validate all inputs
- Log important events
- Keep DB sessions short-lived

---

## 12. Common mistakes

Avoid:

- Blocking calls inside `run()`
- Missing `ctx` in secured functions
- Large memory objects in class attributes
- Direct SQL without ORM
- No permission decorators

---

## 13. Minimal plugin template

```python
class Plugin:

    @hookimpl
    def env(cls):
        return {}

    @hookimpl
    def schema(cls, ctx):
        return Config.model_json_schema()

    @hookimpl
    def config(cls, ctx, json=None, validate=False):
        return Config.model_validate(json or {})

    @hookimpl
    def roles(cls):
        return {}

    @hookimpl
    async def run(cls, ctx, config, logger, render):
        return True
```

---

## 14. Testing plugins

Recommended:

- Unit test DAO functions
- Mock ExecutionContext
- Test schema generation
- Test permission failures
- Test async run()

---

## 15. Security checklist

Before releasing a plugin:

- All write ops protected with `job_permission`
- Inputs validated
- No raw SQL injection risks
- No secrets in code
- XSS-safe rendering
- Logs do not leak sensitive data
