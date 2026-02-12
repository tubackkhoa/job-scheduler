import pluggy
import logging
from typing import Any, Callable, Dict, Optional
from jinja2 import Environment
from .api import (
    fetch_positions,
    get_running_models,
    fetch_stats_running_models,
    update_model_config,
    get_equity_curve_forward_test,
    fetch_positions,
)
from .config import Config
from schemas import settings


# {% set model_keys = models | map(attribute='map(attribute='name')') %}
# {{ map(attribute='name') }}


hookimpl = pluggy.HookimplMarker("job-scheduler")


class Plugin:
    _env = {
        "get_running_models": get_running_models,
        "fetch_positions": fetch_positions,
        "get_equity_curve_forward_test": get_equity_curve_forward_test,
        "fetch_stats_running_models": fetch_stats_running_models,
        "update_model_config": update_model_config,
        "get_equity_curve_forward_test": get_equity_curve_forward_test,
        "fetch_positions": fetch_positions,
    }
    _routes: list[tuple[str, Any]] = [
        # empty route will be use as portal
        ("", Config.model_config.get("json_schema_extra")),
        (
            "dashboard",
            (
                {
                    "url": (
                        "forwardtest/Dashboard.tsx"
                        if settings.env == "dev"
                        else "{base_url}/assets/{package}/dashboard.js"
                    )
                }
            ),
        ),
        (
            "marketplace",
            (
                {
                    "url": (
                        "forwardtest/MarketPlace.tsx"
                        if settings.env == "dev"
                        else "{base_url}/assets/{package}/marketplace.js"
                    )
                }
            ),
        ),
    ]

    @classmethod
    @hookimpl
    def routes(cls) -> list[tuple[str, Any]]:
        # using function so that it will delete memory because page can be huge
        return cls._routes

    @classmethod
    @hookimpl
    def install(cls) -> bool:
        return True

    @classmethod
    @hookimpl
    def env(cls) -> Dict[str, Any]:
        return cls._env

    @classmethod
    @hookimpl
    def schema(cls, ctx):
        return Config.model_json_schema()

    @classmethod
    @hookimpl
    def config(
        cls,
        ctx,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ):

        return Config.model_validate(json or {})

    @classmethod
    @hookimpl
    def roles(cls):
        return {}

    @classmethod
    @hookimpl
    async def run(
        cls,
        ctx,
        config: Config,
        logger: logging.Logger,
        render: Callable[[str, Environment, dict], Any],
    ):
        logger.info(f"ForwardTestDashboard: {config.webhook_url}")
        return True
