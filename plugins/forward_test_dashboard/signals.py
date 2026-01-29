import pandas as pd
from typing import List, Dict, Any

from .theme import THEME, color_span
from .parsing import parse_table_message
from .api import fetch_positions
from .pnl import build_pnl_map

async def build_signal_comparison(
    config: Dict[str, Any],
    models: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
) -> pd.DataFrame:
    
    model_keys = []
    identity_map = {}
    for m in models:
        identity = m.get("identity")
        if identity:
            model_keys.append(identity)
            identity_map[identity] = identity

    if not model_keys:
        return pd.DataFrame({"message": ["No models provided"]})

    # 3. Process messages into rows
    all_table_data = []

    for msg in messages:
        raw_text = msg.get("message", "")
        model_key = msg.get("model_key")
        
        # Parse the table message
        parsed = parse_table_message(raw_text)
        if not parsed:
            continue

        header = parsed["header"]
        rows = parsed["rows"]

        # Find important column indices
        pred_time_idx = -1
        base_asset_idx = -1
        new_mu_idx = -1
        gated_flag_idx = -1

        for i, col in enumerate(header):
            col_lower = col.lower()
            if col_lower == "pred_time":
                pred_time_idx = i
            elif col_lower == "base_asset":
                base_asset_idx = i
            elif col_lower == "new_mu":
                new_mu_idx = i
            elif col_lower in ["gated_flag", "effective_gated_flag"]:
                gated_flag_idx = i

        # Extract data from each row of the message
        for row in rows:
            if pred_time_idx < 0 or base_asset_idx < 0:
                continue

            # Extract values
            pred_time = row[pred_time_idx] if pred_time_idx < len(row) else ""
            base_asset = row[base_asset_idx] if base_asset_idx < len(row) else ""
            new_mu_str = row[new_mu_idx] if new_mu_idx >= 0 and new_mu_idx < len(row) else ""
            gated_flag = (
                row[gated_flag_idx] if gated_flag_idx >= 0 and gated_flag_idx < len(row) else ""
            )

            # Normalize timestamp: if only date (no time), append 00:00:00
            if pred_time and ' ' not in pred_time:
                pred_time = f"{pred_time} 00:00:00"

            # Parse new_mu to determine direction
            try:
                new_mu = float(new_mu_str) if new_mu_str and new_mu_str.lower() != "none" else 0
            except:
                new_mu = 0

            is_gated = gated_flag == "1" or gated_flag == "1.0" or gated_flag == "True"

            if new_mu > 0:
                direction = "LONG"
            elif new_mu < 0:
                direction = "SHORT"
            else:
                direction = "NONE"

            all_table_data.append(
                {
                    "pred_time": pred_time,
                    "base_asset": base_asset,
                    "direction": direction,
                    "new_mu": new_mu,
                    "is_gated": is_gated,
                    "_identity": model_key, # Link back to column identity
                }
            )

    if not all_table_data:
        return pd.DataFrame({"message": ["No valid signals parsed"]})

    df = pd.DataFrame(all_table_data)

    # 4. Filter empty timestamps & format
    df["pred_time"] = pd.to_datetime(df["pred_time"], errors="coerce")
    df = df.dropna(subset=["pred_time"])

    if df.empty:
        return pd.DataFrame({"message": ["No valid timestamps"]})

    # 5. Fetch PNL positions (same as before)
    start_time = df["pred_time"].min().isoformat() + "Z"
    
    positions = fetch_positions(
        config['webhook_url'],
        config['webhook_api_key'],
        start_time,
    )

    pnl_map = build_pnl_map(positions)

    # 6. Render Signal Cell
    def render_signal(row) -> str:
        # Normalize prediction hour
        pred_time = row["pred_time"]
        pred_hour = pred_time.floor("h")
        # Convert to naive datetime then to ISO string
        pred_hour_naive = pred_hour.tz_localize(None) if pred_hour.tz is not None else pred_hour
        hour = pred_hour_naive.isoformat()
        
        # PNL key: (Symbol, ModelIdentity, HourISO)
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

    # 7. Pivot table
    pivot = df.pivot_table(
        index=["pred_time", "base_asset"],
        columns="_identity",
        values="signal",
        aggfunc="first",
    )

    # Reorder columns based on input models list
    ordered_columns = [
        model["identity"]
        for model in models
        if model["identity"] in pivot.columns
    ]
    pivot = pivot[ordered_columns]
    pivot = pivot.fillna("-")
    
    # Sort by time desc
    pivot = pivot.sort_index(level="pred_time", ascending=False)

    # Flatten index for display
    pivot = pivot.reset_index()
    pivot["pred_time"] = pivot["pred_time"].dt.strftime("%Y-%m-%d %H:%M")
    pivot = pivot.rename(columns={"pred_time": "Time", "base_asset": "Symbol"})

    # Hide duplicate timestamps for cleaner view
    time_col = pivot["Time"].copy()
    for i in range(1, len(time_col)):
        if time_col.iloc[i] == time_col.iloc[i - 1]:
            pivot.at[i, "Time"] = ""

    return pivot

def coerce_float(value) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
