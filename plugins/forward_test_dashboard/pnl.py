import pandas as pd
from datetime import datetime
from typing import Dict, Iterable, Tuple, List, Any

from .parsing import extract_model_key
from .formatters import fmt_pnl, fmt_status, fmt_latest, fmt_winrate, fmt_drawdown


def build_pnl_map(positions: Iterable[dict]) -> Dict[Tuple[str, str, str], float]:
    pnl_map = {}
    for pos in positions:
        symbol = pos.get("symbol", "")
        model_key = pos.get("modelKey", "")
        entry_time_str = pos.get("entryTime", "")
        pnl = pos.get("pnl", 0) or 0

        # Parse entryTime and round to hour
        try:
            from datetime import datetime

            entry_time = pd.to_datetime(entry_time_str)
            # Round to hour: 2026-01-20T09:00:21.405Z -> 2026-01-20 09:00:00
            entry_hour = entry_time.floor("h")
            entry_hour_naive = (
                entry_hour.tz_localize(None) if entry_hour.tz is not None else entry_hour
            )
            entry_hour_iso = entry_hour_naive.isoformat()

            key = (symbol, model_key, entry_hour_iso)
            pnl_map[key] = pnl
        except:
            continue

    return pnl_map


def build_pnl_table(
    models: List[Dict[str, Any]],
    jobs: List[Dict[str, Any]],
) -> tuple[pd.DataFrame, dict]:

    if not models:
        return pd.DataFrame(), {"total_models": 0, "total_pnl": 0.0}

    # Map model identity → job info
    identity_job = {}
    for job in jobs:
        model_key = extract_model_key(job)
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
                "Identity": identity,
                "Model": m.get("modelName"),
                "PNL": fmt_pnl(pnl),
                "Total Runtime": m.get("totalRunningTime") or "-",
                "Winrate": fmt_winrate(m.get("winrate")),
                "Max Drawdown": m.get("maxDrawdown"),
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
