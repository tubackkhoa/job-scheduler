import pluggy
import logging
from typing import Any, Callable, Dict, Optional
from jinja2 import Environment
from .api import (
    get_running_models,
    fetch_stats_running_models,
    update_model_config,
    get_equity_curve_forward_test,
)
from .config import Config
from pathlib import Path


# {% set model_keys = models | map(attribute='map(attribute='name')') %}
# {{ map(attribute='name') }}


PROJECT_NAME = "alpha-miner"
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Plugin:
    _env = {
        "get_running_models": get_running_models,
        "get_equity_curve_forward_test": get_equity_curve_forward_test,
        "fetch_stats_running_models": fetch_stats_running_models,
        "update_model_config": update_model_config,
        "get_equity_curve_forward_test": get_equity_curve_forward_test,
    }
    _routes: list[tuple[str, Any]] = [
        (
            "dashboard",
            {
                "code": Path(__file__).with_name("dashboard.js").read_text(),
            },
        ),
    ]

    @hookimpl
    @classmethod
    def routes(cls) -> list[tuple[str, Any]]:
        # using function so that it will delete memory because page can be huge
        return cls._routes

    @hookimpl
    @classmethod
    def install(cls) -> bool:
        return True

    @hookimpl
    @classmethod
    def env(cls) -> Dict[str, Any]:
        return cls._env

    @hookimpl
    @classmethod
    def schema(cls, ctx):
        return Config.model_json_schema()

    @hookimpl
    @classmethod
    def config(
        cls,
        ctx,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ):
        if isinstance(json, str):
            import json as json_module

            json = json_module.loads(json)
        return Config.model_validate(json or {})

    @hookimpl
    @classmethod
    def roles(cls):
        return {"admin"}

    @hookimpl
    @classmethod
    async def run(
        cls,
        ctx,
        config: Config,
        logger: logging.Logger,
        render: Callable[[str, Environment, dict], Any],
    ):
        logger.info(f"ForwardTestDashboard: {config.webhook_url}")
        return True
