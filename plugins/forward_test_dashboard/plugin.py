import pluggy
import logging
from typing import Any, Callable, Dict
from jinja2 import Environment

from .pnl import build_pnl_table
from .signals import build_signal_comparison
from .api import get_running_models
from .config import Config
from .formatters import fmt_pnl, fmt_status, fmt_latest

PROJECT_NAME = "alpha-miner"
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Plugin:
    _env = {
        "get_running_models": get_running_models,
        "build_pnl_table": build_pnl_table,
        "build_signal_comparison": build_signal_comparison,
        "fmt_pnl": fmt_pnl,
        "fmt_status": fmt_status,
        "fmt_latest": fmt_latest,
    }

    @hookimpl
    def install(self) -> bool:
        return True

    @hookimpl
    def env(self) -> Dict[str, Any]:
        return self._env

    @hookimpl
    def schema(self, ctx):
        return Config.model_json_schema()

    @hookimpl
    async def run(
        self,
        ctx,
        config: Config,
        logger: logging.Logger,
        render: Callable[[str, Environment, dict], Any],
    ):
        logger.info(f"ForwardTestDashboard: {config.webhook_url}")
        return True
