import pandas as pd


def build_pnl_map(positions):
    df = pd.DataFrame(positions)
    if df.empty:
        return {}

    df["entry_hour"] = (
        pd.to_datetime(df["entryTime"]).dt.floor("h").dt.tz_localize(None).astype(str)
    )

    return {(r.symbol, r.modelKey, r.entry_hour): r.pnl for r in df.itertuples()}
