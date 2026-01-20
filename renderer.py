from weakref import WeakKeyDictionary
from functools import lru_cache
from jinja2 import Environment
from jinja2.sandbox import SandboxedEnvironment

from enforcer import GLOBAL_PERMISSION_REGISTRY


class Renderer:
    _sandbox_cache = WeakKeyDictionary()

    @classmethod
    def _get_sandbox(cls, env: Environment) -> SandboxedEnvironment:
        sandbox = cls._sandbox_cache.get(env)
        if sandbox is not None:
            return sandbox

        sandbox = SandboxedEnvironment(
            loader=env.loader,
            autoescape=env.autoescape,
            undefined=env.undefined,
            extensions=list(env.extensions.keys()),
            trim_blocks=env.trim_blocks,
            lstrip_blocks=env.lstrip_blocks,
            keep_trailing_newline=env.keep_trailing_newline,
            enable_async=env.is_async,
            finalize=env.finalize,
        )

        sandbox.globals.update(GLOBAL_PERMISSION_REGISTRY)
        sandbox.globals.update(env.globals)

        sandbox.filters.update(env.filters)
        sandbox.tests.update(env.tests)

        cls._sandbox_cache[env] = sandbox
        return sandbox

    @classmethod
    def render(cls, ctx, template_str, env, payload):
        sandbox = cls._get_sandbox(env)

        # cache compiled templates per sandbox
        template = cls._compile(sandbox, template_str)

        return template.render(payload, this=payload, ctx=ctx)

    @staticmethod
    @lru_cache(maxsize=1024)
    def _compile(sandbox: SandboxedEnvironment, template_str: str):
        return sandbox.from_string(template_str)
