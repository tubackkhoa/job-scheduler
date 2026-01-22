import inspect
from typing import Any, Iterable
from functools import lru_cache
from jinja2.sandbox import SandboxedEnvironment

from enforcer import GLOBAL_PERMISSION_REGISTRY, ExecutionContext


def tolist(obj: Iterable, *include: str) -> list[dict]:
    if include:
        include_set = set(include)
        return [{k: v for k, v in item.to_dict().items() if k in include_set} for item in obj]
    return [item.to_dict() for item in obj]


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
    _sandbox = SandboxedEnvironment(
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    _sandbox.filters.update(
        {
            "in_clause": lambda values: (
                "()" if not values else f"({','.join(map(repr, values))})"
            ),
            "tolist": tolist,
        }
    )

    _globals_doc = {
        "this": {
            "type": "variable",
            "doc": "The payload object passed to the render function.",
        },
        "ctx": {"type": "variable", "doc": "Execution context for the current render"},
    }

    @classmethod
    def update(cls):
        cls._sandbox.globals.update(GLOBAL_PERMISSION_REGISTRY)
        cls._globals_doc.update(
            {name: describe_callable(value) for name, value in GLOBAL_PERMISSION_REGISTRY.items()}
        )
        cls._compile.cache_clear()

    @classmethod
    def get_globals_doc(cls, extra_globals: dict[str, Any]):
        return {
            **cls._globals_doc,
            **{k: describe_callable(v) for k, v in extra_globals.items()},
        }

    @classmethod
    def render(
        cls, ctx: ExecutionContext, template_str: str, payload: dict[str, Any], **kwargs: Any
    ) -> str:
        # cache compiled templates for this sandbox
        # first argument must be payload, then later can access this
        template = cls._compile(template_str)
        return template.render(payload, **kwargs, this=payload, ctx=ctx)

    @staticmethod
    @lru_cache(maxsize=1024)
    def _compile(template_str: str):
        return Renderer._sandbox.from_string(template_str)
