import hashlib
import inspect
from pathlib import Path
from typing import Any, Mapping
from collections import OrderedDict
from jinja2 import DictLoader, FileSystemBytecodeCache
from jinja2.sandbox import SandboxedEnvironment
from datetime import datetime, timedelta, timezone

from enforcer import GLOBAL_PERMISSION_REGISTRY, ExecutionContext
from schemas import settings

# make sure cache folder exist
Path(settings.jinja_cache_path).mkdir(parents=True, exist_ok=True)


# only remain a small hot item incase of cache miss - but rare
class LRUDict(OrderedDict):
    def __init__(self, maxsize: int = 256):
        super().__init__()
        self.maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        else:
            if len(self) >= self.maxsize:
                self.popitem(last=False)
        super().__setitem__(key, value)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value


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


def pick(items: list[Any], *fields: str):
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append({f: item.get(f) for f in fields})
        else:
            result.append({f: getattr(item, f, None) for f in fields})
    return result


def in_clause(values: list[object]):
    return "()" if not values else f"({','.join(map(repr, values))})"


class Renderer:
    _templates = LRUDict()
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
    _sandbox.policies["json.dumps_kwargs"] = {"sort_keys": False}

    _sandbox.filters.update(
        {
            "in_clause": in_clause,
            "pick": pick,
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
        cls._templates[key] = template_str
        template = cls._sandbox.get_template(key)

        return await template.render_async(
            payload,
            **kwargs,
            this=payload,
            ctx=ctx,
        )
