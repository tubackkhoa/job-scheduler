import pluggy
import logging
from typing import Any, Callable, Dict, Optional
from jinja2 import Environment
from .pnl import build_pnl_table
from .signals import build_signal_comparison
from .stats import build_stats_table
from .api import get_running_models, fetch_stats_running_models
from .config import Config
from .formatters import fmt_pnl, fmt_status, fmt_latest, fmt_winrate, fmt_drawdown
from enforcer import GLOBAL_PERMISSION_REGISTRY

async def fetch_signal_messages(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dao = GLOBAL_PERMISSION_REGISTRY.get("dao")
    if not dao:
        return []
    
    model_keys = [m.get("identity") for m in models if m.get("identity")]
    if not model_keys:
        return []

    return await dao.get_signal_messages_by_keys(model_keys, limit=1000)

PROJECT_NAME = "alpha-miner"
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Plugin:
    _env = {
        "get_running_models": get_running_models,
        "fetch_stats_running_models": fetch_stats_running_models,
        "build_pnl_table": build_pnl_table,
        "build_stats_table": build_stats_table,
        "build_signal_comparison": build_signal_comparison,
        "fetch_signal_messages": fetch_signal_messages,
        "fmt_pnl": fmt_pnl,
        "fmt_status": fmt_status,
        "fmt_latest": fmt_latest,
        "fmt_winrate": fmt_winrate,
        "fmt_drawdown": fmt_drawdown,
    }

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
