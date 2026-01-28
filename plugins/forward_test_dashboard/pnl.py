import pandas as pd
from typing import List, Dict, Any
from .formatters import fmt_pnl, fmt_status, fmt_latest


def build_pnl_map(positions):
    df = pd.DataFrame(positions)
    if df.empty:
        return {}

    df["entry_hour"] = (
        pd.to_datetime(df["entryTime"], utc=True)
        .dt.floor("h")
        .dt.tz_convert(None)
        .dt.strftime("%Y-%m-%dT%H:%M:%S")
    )

    return {(r.symbol, r.modelKey, r.entry_hour): r.pnl for r in df.itertuples()}


def build_pnl_table(
    models: List[Dict[str, Any]],
    jobs: List[Dict[str, Any]],
) -> tuple[pd.DataFrame, dict]:

    if not models:
        return pd.DataFrame(), {"total_models": 0, "total_pnl": 0.0}

    # Map model identity → job info
    identity_job = {}
    for job in jobs:
        cfg = job.get("config") or {}
        if isinstance(cfg, str):
            import json

            cfg = json.loads(cfg)

        model_key = cfg.get("model_key")
        if model_key:
            identity_job[model_key] = {
                "state": "active" if job.get("active") else "inactive",
                "label": job.get("description") or "No description",
            }

    rows = []
    total_pnl = 0.0

    for m in models:
        identity = m.get("identity")
        pnl = m.get("totalPnl") or 0.0
        total_pnl += pnl

        rows.append(
            {
                "Model": m.get("modelName"),
                "Identity": identity,
                "PNL": fmt_pnl(pnl),
                "Last Position Time": m.get("latestPositionAt") or "-",
                "Status": fmt_status(identity_job.get(identity)),
                "Latest Position": fmt_latest(m.get("latestPostion")),
                "Created At": m.get("createdAt"),
            }
        )

    df = pd.DataFrame(rows)

    return df, {
        "total_models": len(df),
        "total_pnl": total_pnl,
    }
