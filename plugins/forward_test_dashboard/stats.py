import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

from .parsing import extract_model_key
from .formatters import fmt_pnl, fmt_status, fmt_latest, fmt_winrate, fmt_drawdown


def format_utc_time(iso_string: str) -> str:
    """Convert ISO datetime string to 'YYYY-MM-DD HH:MM UTC' format."""
    if not iso_string:
        return "-"
    try:
        # Parse ISO string and convert to UTC
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_string  # Return original if parsing fails


def build_stats_table(
    stats: List[Dict[str, Any]],
    jobs: List[Dict[str, Any]],
) -> tuple[pd.DataFrame, dict]:    
    if not stats:
        return pd.DataFrame(), {
            "total_models": 0,
            "total_pnl": 0.0,
            "total_positions": 0
        }
    
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
    total_positions = 0
    
    for stat in stats:
        identity = stat.get("identity")
        pnl = stat.get("totalPnl") or 0.0
        positions = int(stat.get("totalPositions") or 0)
        
        total_pnl += pnl
        total_positions += positions
        
        # Convert lastPosition to format compatible with fmt_latest
        last_pos = stat.get("lastPosition")
        last_pos_formatted = None
        last_pos_time = None
        if last_pos:
            last_pos_formatted = {
                "symbol": last_pos.get("symbol", ""),
                "direction": last_pos.get("side", ""),  # side -> direction
                "pnl": last_pos.get("pnl", 0.0)
            }
            last_pos_time = last_pos.get("time")
        
        rows.append({
            "Model": stat.get("modelName"),
            "Identity": identity,
            "Total PNL": fmt_pnl(pnl),
            "PNL 1H": fmt_pnl(stat.get("pnlDelta1h") or 0.0),
            "PNL 4H": fmt_pnl(stat.get("pnlDelta4h") or 0.0),
            "PNL 1D": fmt_pnl(stat.get("pnlDelta1d") or 0.0),
            "Total Positions": positions,
            "Total Runtime": stat.get("totalRunningTime") or "-",
            "Winrate": fmt_winrate(stat.get("winrate")),
            "Max Drawdown": fmt_drawdown(stat.get("maxDrawdown")),
            "Latest Position": fmt_latest(last_pos_formatted),
            "Latest Position Time": format_utc_time(last_pos_time),
            "Status": fmt_status(identity_job.get(identity)),
            "Started": format_utc_time(stat.get("startedAt")),
        })
    
    df = pd.DataFrame(rows)
    
    return df, {
        "total_models": len(df),
        "total_pnl": total_pnl,
        "total_positions": total_positions,
    }
