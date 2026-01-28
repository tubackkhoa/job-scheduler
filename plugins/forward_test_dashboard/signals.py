import pandas as pd
from typing import List, Dict, Any
from log_service import LogService


from .theme import THEME, color_span
from .parsing import parse_table_message
from .api import fetch_positions
from .pnl import build_pnl_map
from .config import Config

logger = LogService(useIndexer=False)


def extract_signals(job_id: int, keyword: str) -> pd.DataFrame:
    scheduler_id = f"job-scheduler.job.{job_id}"
    result = logger.search_logs_with_following(
        job_id=scheduler_id,
        keyword=keyword,
        n_following=2,
        limit=50,
        sort="desc",
    )

    records = []

    for group in result.get("groups", []):
        msg = group["following_entries"][-1].get("message", "")
        parsed = parse_table_message(msg)
        if not parsed:
            continue

        df = pd.DataFrame(parsed["rows"], columns=parsed["header"])
        if {"pred_time", "base_asset"}.issubset(df.columns):

            if "new_mu" in df.columns:
                df["new_mu"] = pd.to_numeric(df["new_mu"], errors="coerce").fillna(0)
            else:
                df["new_mu"] = 0

            df["direction"] = "NONE"
            df.loc[df["new_mu"] > 0, "direction"] = "LONG"
            df.loc[df["new_mu"] < 0, "direction"] = "SHORT"

            if "gated_flag" in df.columns:
                df["is_gated"] = df["gated_flag"].isin(["1", "True", "1.0"])
            else:
                df["is_gated"] = False

            records.append(df)

    result_df = pd.concat(records, ignore_index=True) if records else pd.DataFrame()

    if not result_df.empty and "is_gated" in result_df.columns:
        # 🔥 THIS is the critical line
        result_df["is_gated"] = result_df["is_gated"].astype(object)

    return result_df


def coerce_float(value) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        import numpy as np

        if isinstance(value, (np.integer, np.floating)):
            return float(value)
    except Exception:
        pass
    return 0.0


def build_signal_comparison(
    config: Config,
    models: List[Dict[str, Any]],
    jobs: List[Dict[str, Any]],
) -> pd.DataFrame:

    # Map identity → job
    identity_job = {}
    for job in jobs:
        cfg = job.get("config") or {}
        if isinstance(cfg, str):
            import json

            cfg = json.loads(cfg)

        model_key = cfg.get("model_key")
        if model_key:
            identity_job[model_key] = job

    records = []

    for m in models:
        identity = m.get("identity")
        job = identity_job.get(identity)
        if not job:
            continue

        df = extract_signals(job["id"], config.signal_keyword)
        if df.empty:
            continue

        df["_identity"] = identity
        records.append(df)

    if not records:
        return pd.DataFrame({"message": ["No signals found"]})

    df = pd.concat(records, ignore_index=True)
    df["pred_time"] = pd.to_datetime(df["pred_time"], errors="coerce")
    df = df.dropna(subset=["pred_time"])

    if df.empty:
        return pd.DataFrame({"message": ["No valid timestamps"]})

    start_time = df["pred_time"].min().isoformat() + "Z"

    positions = fetch_positions(
        config.webhook_url,
        config.webhook_api_key,
        start_time,
    )

    pnl_map = build_pnl_map(positions)

    def render_signal(row) -> str:
        # Normalize prediction hour
        pred_time = row["pred_time"]
        if isinstance(pred_time, pd.Timestamp):
            hour = pred_time.floor("h").to_pydatetime().strftime("%Y-%m-%dT%H:%M:%S")
        else:
            hour = ""

        key = (row["base_asset"], row["_identity"], hour)

        # Safely coerce PNL
        pnl = coerce_float(pnl_map.get(key))

        # Marker if order exists
        marker = "*" if key in pnl_map else ""
        symbol = f"{marker}{row['base_asset']}"

        # Direction-colored symbol
        direction = row.get("direction")
        if direction == "LONG":
            sym = color_span(symbol, THEME["positive"], bold=True)
        elif direction == "SHORT":
            sym = color_span(symbol, THEME["negative"], bold=True)
        else:
            sym = color_span(symbol, THEME["neutral"], bold=True)

        # PNL formatting
        if pnl > 0:
            pnl_str = color_span(f"↗ +${pnl:.4f}", THEME["positive"])
        elif pnl < 0:
            pnl_str = color_span(f"↘ ${pnl:.4f}", THEME["negative"])
        else:
            pnl_str = color_span("$0.0000", THEME["neutral"])

        txt = f"{sym} {pnl_str}"

        # Gated signals are struck through
        return f"~~{txt}~~" if bool(row.get("is_gated")) else txt

    df["signal"] = df.apply(render_signal, axis=1)

    pivot = df.pivot_table(
        index=["pred_time", "base_asset"],
        columns="_identity",
        values="signal",
        aggfunc="first",
    ).fillna("-")

    pivot = pivot.reset_index()
    pivot["pred_time"] = pivot["pred_time"].dt.strftime("%Y-%m-%d %H:%M")

    pivot = pivot.rename(columns={"pred_time": "Time", "base_asset": "Symbol"})

    # visually group repeated times
    for i in range(1, len(pivot)):
        if pivot.loc[i, "Time"] == pivot.loc[i - 1, "Time"]:
            pivot.loc[i, "Time"] = ""

    return pivot.sort_index(ascending=False)
