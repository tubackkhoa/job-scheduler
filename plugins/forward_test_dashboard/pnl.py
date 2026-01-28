import pandas as pd
from datetime import datetime
from typing import Dict, Iterable, Tuple, List, Any

from .parsing import extract_model_key
from .formatters import fmt_pnl, fmt_status, fmt_latest, fmt_winrate, fmt_drawdown


def build_pnl_map(positions: Iterable[dict]) -> Dict[Tuple[str, str, str], float]:
    pnl_map = {}

    for p in positions:
        try:
            dt = datetime.fromisoformat(p["entryTime"].replace("Z", "+00:00")).replace(
                minute=0, second=0, microsecond=0
            )
            hour = dt.strftime("%Y-%m-%dT%H:%M:%S")

            key = (p["symbol"], p["modelKey"], hour)
            pnl_map[key] = p.get("pnl", 0.0)
        except Exception:
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
                "Model": m.get("modelName"),
                "Identity": identity,
                "PNL": fmt_pnl(pnl),
                "Total Runtime": m.get("totalRunningTime") or "-",
                "Winrate": fmt_winrate(m.get("winrate")),
                "Max Drawdown": fmt_drawdown(m.get("maxDrawdown")),
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
