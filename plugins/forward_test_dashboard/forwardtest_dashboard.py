"""
Forward Test Dashboard Plugin - Database-Backed Version

This plugin retrieves signal data from forward_test_trade_history table
and performance data from forward_test_performance table.
"""

import msgspec.json as ms
import pluggy
import logging
import pandas as pd
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone
from jinja2 import Environment

# from .pnl import build_pnl_table
# from .signals import build_signal_comparison
# from .stats import build_stats_table
from .api import get_running_models, fetch_stats_running_models
from .forwardtest_plugin_components.config import Config

# from .formatters import fmt_pnl, fmt_status, fmt_latest, fmt_winrate, fmt_drawdown
from .theme import THEME, color_span
from .database.db_repository import ForwardTestRepository
from enforcer import GLOBAL_PERMISSION_REGISTRY
from .forwardtest_plugin_components.actions import (
    update_model_config,
    register_model_config,
    get_running_models,
    get_running_models_list,
)
from .forwardtest_plugin_components.actions import get_equity_curve_forward_test_fromdb

logger = logging.getLogger(__name__)


# ============================================================================
# Database-backed functions (NEW)
# ============================================================================


def fetch_signals_from_db(
    model_names: Optional[List[str]] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Fetch signal data from forward_test_trade_history table.

    Args:
        model_names: Optional list of model names to filter
        start_time: Optional start time filter
        end_time: Optional end time filter
        limit: Maximum records to return

    Returns:
        List of trade history records
    """
    try:
        with ForwardTestRepository() as repo:
            return repo.get_trade_history(
                model_names=model_names,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
    except Exception as e:
        logger.error(f"Error fetching signals from DB: {e}")
        return []


def fetch_performance_from_db(
    identities: Optional[List[str]] = None,
    pred_time: Optional[datetime] = None,
    status_filter: Optional[str] = "running",
) -> List[Dict[str, Any]]:
    """
    Fetch performance data from forward_test_performance table.

    This is the DB equivalent of fetch_stats_running_models().

    Args:
        identities: Optional list of identities to filter
        pred_time: Optional time to get snapshot at
        status_filter: Optional status filter (default: 'running')

    Returns:
        List of performance records (same format as API stats)
    """
    try:
        with ForwardTestRepository() as repo:
            if pred_time:
                records = repo.get_performance_at_time(
                    pred_time=pred_time,
                    model_names=identities,
                )
            else:
                records = repo.get_latest_performance(
                    identities=identities,
                    status_filter=status_filter,
                )

            # Transform to match API format for compatibility with build_stats_table
            # Note: DB stores winrate as percentage (49.03), API expects decimal (0.4903)
            def normalize_winrate(val):
                if val is None:
                    return None
                # DB stores as percentage, convert to decimal
                return val / 100.0 if val > 1 else val

            return [
                {
                    "identity": r.get("identity"),
                    "modelName": r.get("model_name"),
                    "totalPnl": r.get("total_pnl"),
                    "pnlDelta1h": r.get("pnl_delta_1h"),
                    "pnlDelta4h": r.get("pnl_delta_4h"),
                    "pnlDelta1d": r.get("pnl_delta_1d"),
                    "winrate": normalize_winrate(r.get("winrate")),
                    "maxDrawdown": r.get("max_drawdown"),
                    "totalPositions": r.get("total_positions"),
                    "totalRunningTime": r.get("total_running_time"),
                    "startedAt": r.get("started_at").strftime("%Y-%m-%d %H:%M:%S"),
                    "lastPosition": _parse_last_position(r.get("last_position")),
                }
                for r in records
            ]
    except Exception as e:
        logger.error(f"Error fetching performance from DB: {e}")
        return []


def _parse_last_position(last_pos) -> Optional[Dict[str, Any]]:
    """Parse last_position field which may be JSON string."""
    if not last_pos:
        return None

    if isinstance(last_pos, str):
        try:
            last_pos = ms.decode(last_pos)
        except:
            return None

    if isinstance(last_pos, dict):
        return {
            "symbol": last_pos.get("symbol", ""),
            "side": last_pos.get("side", last_pos.get("direction", "")),
            "pnl": _coerce_float(last_pos.get("pnl", 0.0)),
            "time": last_pos.get("time"),
        }
    return None


def _coerce_float(value) -> float:
    """Safely convert value to float."""
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_signal_comparison_from_db(
    config: Dict[str, Any],
    models: List[Dict[str, Any]],
    start_time: Optional[datetime] = None,
    # end_time: Optional[datetime] = None, # Note: signature in plugin.py uses limit, but we might need end_time internally or just derive it
    limit: int = 1000,
) -> pd.DataFrame:
    """
    Build signal comparison table using data directly from DB.
    Matches the format and logic of build_signal_comparison in signals.py.
    """
    # 1. Map identities
    model_keys = []
    for m in models:
        identity = m.get("identity")
        if identity:
            model_keys.append(identity)

    if not model_keys:
        return pd.DataFrame({"message": ["No models provided"]})

    # 2. Fetch trade history
    trades = fetch_signals_from_db(model_names=model_keys, start_time=start_time, limit=limit)

    if not trades:
        return pd.DataFrame({"message": ["No signals found in DB"]})

    # 3. Fetch price deltas for PNL calculation
    # Collect all needed assets and time range
    assets = set()
    timestamps = []

    # Pre-process trades into a more usable list
    processed_trades = []

    for t in trades:
        t_time = t.get("pred_time")
        if not t_time:
            continue

        # Ensure naive datetime for consistent comparison
        if hasattr(t_time, "tzinfo") and t_time.tzinfo:
            t_time = t_time.replace(tzinfo=None)

        timestamps.append(t_time)
        assets.add(t.get("base_asset"))

        # Determine direction
        new_mu = _coerce_float(t.get("new_mu", 0))
        if new_mu > 0:
            direction = "LONG"
        elif new_mu < 0:
            direction = "SHORT"
        else:
            direction = "NONE"

        gated_flag = t.get("gated_flag")
        # Handle various boolean/string representations of gated_flag
        if isinstance(gated_flag, str):
            is_gated = gated_flag.lower() in ("1", "1.0", "true", "yes")
        else:
            is_gated = bool(gated_flag)

        processed_trades.append(
            {
                "pred_time": t_time,
                "base_asset": t.get("base_asset"),
                "direction": direction,
                "new_mu": new_mu,
                "is_gated": is_gated,
                "_identity": t.get("model_name"),  # This maps to column identity
            }
        )

    if not processed_trades:
        return pd.DataFrame({"message": ["No valid trades to process"]})

    # Fetch PNL data
    pnl_map = {}
    if assets and timestamps:
        min_time = min(timestamps)
        max_time = max(timestamps)
        # Fetch a bit wider range just in case
        try:
            with ForwardTestRepository() as repo:
                pnl_map = repo.get_price_deltas(
                    start_time=min_time, end_time=max_time, assets=list(assets)
                )
        except Exception as e:
            logger.error(f"Failed to fetch price deltas: {e}")
            pnl_map = {}

    # 4. Connect and Render
    df = pd.DataFrame(processed_trades)

    def render_signal(row) -> str:
        t = row["pred_time"]
        t_hour = t.replace(minute=0, second=0, microsecond=0)

        asset = row["base_asset"]
        key = (t_hour, asset)

        price_delta = pnl_map.get(key, 0.0)

        direction = row["direction"]
        pnl = 0.0

        if direction == "LONG":
            pnl = price_delta
        elif direction == "SHORT":
            pnl = -price_delta

        # Only show PNL if we actually found a price delta or if logic dictates?
        # signals.py: marker = "*" if key in pnl_map else ""
        # Here we only have estimated PNL.

        has_pnl = key in pnl_map
        marker = ""  # No order fetch here, so maybe optional? User said "get pnl... from db"

        symbol = f"{row['base_asset']}"

        # Color symbol
        if direction == "LONG":
            sym_span = color_span(symbol, THEME["positive"], bold=True)
        elif direction == "SHORT":
            sym_span = color_span(symbol, THEME["negative"], bold=True)
        else:
            sym_span = color_span(symbol, THEME["neutral"], bold=True)

        # PNL formatting
        if has_pnl:
            if pnl > 0:
                pnl_str = color_span(
                    f"↗ +{pnl:.4f}", THEME["positive"]
                )  # Using % for delta? signals.py used $ pnl.
                # signals.py: pnl_str = color_span(f"↗ +${pnl:.4f}", THEME["positive"])
                # Wait, signals.py shows raw PNL value (USD presumably).
                # We only have % change.
                # User request: "pnl ... tính bằng db ... precalculate delta change"
                # "Show signal comparison... format y hệt code ở Plugin"
                # If I only have %, I should probably show %?
                # Or maybe assume $1 position?
                # Let's show % since we don't know position size.
                pnl_str = color_span(f"↗ {pnl:+.4f}", THEME["positive"])
            elif pnl < 0:
                pnl_str = color_span(f"↘ {pnl:+.4f}", THEME["negative"])
            else:
                pnl_str = color_span("0.00%", THEME["neutral"])
        else:
            pnl_str = ""

        txt = f"{sym_span} {pnl_str}".strip()

        if row["is_gated"]:
            return f"~~{txt}~~"
        return txt

    df["signal"] = df.apply(render_signal, axis=1)

    # 5. Pivot
    pivot = df.pivot_table(
        index=["pred_time", "base_asset"],
        columns="_identity",
        values="signal",
        aggfunc="first",
    )

    # Reorder columns
    ordered_columns = [mid for mid in model_keys if mid in pivot.columns]
    pivot = pivot[ordered_columns]
    pivot = pivot.fillna("-")

    # Sort
    pivot = pivot.sort_index(level="pred_time", ascending=False)

    # Flatten
    pivot = pivot.reset_index()
    pivot["pred_time"] = pivot["pred_time"].dt.strftime("%Y-%m-%d %H:%M")
    pivot = pivot.rename(columns={"pred_time": "Time", "base_asset": "Symbol"})

    # Clean up duplicate times
    time_col = pivot["Time"].copy()
    for i in range(1, len(time_col)):
        if time_col.iloc[i] == time_col.iloc[i - 1]:
            pivot.at[i, "Time"] = ""

    return pivot


def build_stats_table_from_db(
    stats: List[Dict[str, Any]],
    jobs: Optional[List[Dict[str, Any]]] = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Build stats table from forward_test_performance database records.

    This is a drop-in replacement for build_stats_table().
    Uses the same output format.

    Usage in Jinja2 (replaces old template):
        Old: {% set stats = fetch_stats_running_models(webhook_url, webhook_api_key) %}
             {% set df, summary = build_stats_table(stats, job_list) %}
        New: {% set stats = fetch_performance_from_db() %}
             {% set df, summary = build_stats_table_from_db(stats, job_list) %}

    Args:
        stats: List of performance records from fetch_performance_from_db()
        jobs: Optional list of jobs for status mapping

    Returns:
        Tuple of (DataFrame with stats, summary dict)
    """
    # This function now works with the transformed records from fetch_performance_from_db
    # which matches the API format, so we can reuse build_stats_table directly
    return build_stats_table(stats, jobs or [])


def get_models_from_db(
    status_filter: Optional[str] = "running",
) -> List[Dict[str, Any]]:
    """
    Get list of models from forward_test_performance table.

    This is the DB equivalent of get_running_models().

    Usage in Jinja2 (replaces old template):
        Old: {% set models = get_running_models(webhook_url, webhook_api_key) %}
        New: {% set models = get_models_from_db() %}

    Args:
        status_filter: Optional status filter (default: 'running')

    Returns:
        List of model info dicts (compatible with existing code)
    """
    try:
        with ForwardTestRepository() as repo:
            records = repo.get_latest_performance(status_filter=status_filter)

            # Normalize winrate from percentage to decimal
            def normalize_winrate(val):
                if val is None:
                    return None
                return val / 100.0 if val > 1 else val

            # Transform to model format compatible with existing code
            return [
                {
                    "identity": r.get("identity"),
                    "modelName": r.get("model_name"),
                    "model_name": r.get("model_name"),
                    "status": r.get("status"),
                    "startedAt": r.get("started_at"),
                    "createdAt": r.get("started_at"),  # For sorting compatibility
                    "totalPnl": r.get("total_pnl"),
                    "winrate": normalize_winrate(r.get("winrate")),
                }
                for r in records
            ]
    except Exception as e:
        logger.error(f"Error getting models from DB: {e}")
        return []


# ============================================================================
# Legacy functions (kept for backward compatibility)
# ============================================================================


async def fetch_signal_messages(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Legacy function: Fetch signal messages from DAO (log-based).
    Kept for backward compatibility.
    """
    dao = GLOBAL_PERMISSION_REGISTRY.get("dao")
    if not dao:
        return []

    model_keys = [m.get("identity") for m in models if m.get("identity")]
    if not model_keys:
        return []

    return await dao.get_signal_messages_by_keys(model_keys, limit=1000)


# ============================================================================
# Plugin Class
# ============================================================================

PROJECT_NAME = "alpha-miner"
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class ForwardTestDashboardPlugin:
    """
    Forward Test Dashboard Plugin - Database-Backed Version.

    Provides both new DB-backed functions and legacy API-based functions
    for backward compatibility.
    """

    _env = {
        # New DB-backed functions
        "fetch_signals_from_db": fetch_signals_from_db,
        "fetch_performance_from_db": fetch_performance_from_db,
        "build_signal_comparison_from_db": build_signal_comparison_from_db,
        "build_stats_table_from_db": build_stats_table_from_db,
        "get_models_from_db": get_models_from_db,
        # Legacy functions (backward compatibility)
        "get_running_models": get_running_models,
        "fetch_stats_running_models": fetch_stats_running_models,
        # "build_pnl_table": build_pnl_table,
        # "build_stats_table": build_stats_table,
        # "build_signal_comparison": build_signal_comparison,
        "fetch_signal_messages": fetch_signal_messages,
        "update_model_config": update_model_config,
        "register_model_config": register_model_config,
        "get_running_models": get_running_models,
        "get_running_models_list": get_running_models_list,
        "get_equity_curve_forward_test": get_equity_curve_forward_test_fromdb,
        # Formatters
        # "fmt_pnl": fmt_pnl,
        # "fmt_status": fmt_status,
        # "fmt_latest": fmt_latest,
        # "fmt_winrate": fmt_winrate,
        # "fmt_drawdown": fmt_drawdown,
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
        return Config.model_validate(json or {})

    @hookimpl
    @classmethod
    def roles(cls):
        return {}

    @hookimpl
    @classmethod
    async def run(
        cls,
        ctx,
        config: Config,
        logger: logging.Logger,
        render: Callable[[str, Environment, dict], Any],
    ):
        logger.info(f"ForwardTestDashboard (DB-backed): initialized")
        return True
