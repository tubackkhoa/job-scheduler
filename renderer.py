import hashlib
import inspect
from pathlib import Path
from typing import Any, Mapping
from jinja2 import DictLoader, FileSystemBytecodeCache
from jinja2.sandbox import SandboxedEnvironment
from datetime import datetime, timedelta, timezone

from enforcer import GLOBAL_PERMISSION_REGISTRY, ExecutionContext
from schemas import settings

# make sure cache folder exist
Path(settings.jinja_cache_path).mkdir(parents=True, exist_ok=True)


def describe_callable(obj: Any) -> dict[str, Any]:
    """Extract documentation and signature for a callable or object."""
    if callable(obj):
        try:
            signature = str(inspect.signature(obj))
        except (ValueError, TypeError):
            signature = None

        return {
            "type": "function",
            "doc": inspect.getdoc(obj),
            "signature": signature,
        }

    try:
        cls = obj if isinstance(obj, type) else type(obj)
        doc = f"{cls.__module__}.{cls.__qualname__}"
    except Exception:
        doc = str(obj)

    return {
        "type": "variable",
        "doc": doc,
    }


class Renderer:
    _templates: dict[str, str] = {}
    _sandbox = SandboxedEnvironment(
        enable_async=True,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        optimized=True,
        bytecode_cache=FileSystemBytecodeCache(
            directory=settings.jinja_cache_path,
        ),
        loader=DictLoader(_templates),
    )

    _sandbox.globals.update({"datetime": datetime, "timedelta": timedelta, "timezone": timezone})

    _sandbox.filters.update(
        {
            "in_clause": lambda values: (
                "()" if not values else f"({','.join(map(repr, values))})"
            ),
        }
    )

    _globals_doc = {
        "this": {
            "type": "variable",
            "doc": "The payload object passed to the render function.",
        },
        "ctx": {"type": "variable", "doc": "Execution context for the current render"},
    }

    @staticmethod
    def _key(template_str: str) -> str:
        return hashlib.blake2b(template_str.encode(), digest_size=16).hexdigest()

    @classmethod
    def update(cls):
        cls._sandbox.globals.update(GLOBAL_PERMISSION_REGISTRY)
        cls._globals_doc.update(
            {name: describe_callable(value) for name, value in GLOBAL_PERMISSION_REGISTRY.items()}
        )

    @classmethod
    def get_globals_doc(cls, extra_globals: Mapping[str, Any]):
        return {
            **cls._globals_doc,
            **{k: describe_callable(v) for k, v in extra_globals.items()},
        }

    @classmethod
    async def render(
        cls,
        ctx: ExecutionContext,
        template_str: str,
        payload: Mapping[str, Any],
        **kwargs: Any,
    ) -> str:
        key = cls._key(template_str)

        # Insert template only once
        if key not in cls._templates:
            cls._templates[key] = template_str

        template = cls._sandbox.get_template(key)

        return await template.render_async(
            payload,
            **kwargs,
            this=payload,
            ctx=ctx,
        )
