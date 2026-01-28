import random
from typing import Any, Dict
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --------------------------------------------------
# Fixed "today" prices
# --------------------------------------------------
TODAY_PRICE_MAP = {
    "BTC": 43000.0,
    "ETH": 2300.0,
    "BNB": 310.0,
    "SOL": 95.0,
    "XRP": 0.62,
    "ADA": 0.48,
    "DOGE": 0.08,
    "AVAX": 35.0,
    "DOT": 7.2,
    "LINK": 14.5,
}

con = duckdb.connect(database=":memory:")


def register_table(table: str, data: list[Any]):
    df = pd.DataFrame(data)
    con.register(table, df)


def execute_query(query: str):
    return con.execute(query).fetchdf()


# --------------------------------------------------
# OHLCV signal generation
# --------------------------------------------------
def create_signals_for_backtest(
    symbols=[],
    num_days: int = 60,
) -> pd.DataFrame:
    """
    Returns OHLCV time-series + signals
    """

    today_prices = {s: TODAY_PRICE_MAP[s] for s in symbols if s in TODAY_PRICE_MAP}

    if not today_prices:
        return pd.DataFrame()

    np.random.seed(42)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    rows = []

    for asset, start_price in today_prices.items():
        price = start_price

        for i in reversed(range(num_days)):
            timestamp = today - timedelta(days=i)

            open_price = price

            delta = np.random.normal(0, price * 0.015)
            close_price = max(0.0001, open_price + delta)

            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.005)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.005)))

            volume = np.random.randint(1_000_000, 50_000_000)

            price = close_price

            rows.append(
                {
                    "timestamp": timestamp,
                    "asset": asset,
                    "open": round(open_price, 6 if open_price < 1 else 2),
                    "high": round(high_price, 6 if high_price < 1 else 2),
                    "low": round(low_price, 6 if low_price < 1 else 2),
                    "close": round(close_price, 6 if close_price < 1 else 2),
                    "volume": volume,
                }
            )

    prices_df = pd.DataFrame(rows)
    con.register("prices", prices_df)

    signals_df = con.execute(
        """
        WITH indicators AS (
            SELECT
                timestamp,
                asset,
                open,
                high,
                low,
                close,
                volume,
                AVG(close) OVER (
                    PARTITION BY asset
                    ORDER BY timestamp
                    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                ) AS ma_5,
                AVG(close) OVER (
                    PARTITION BY asset
                    ORDER BY timestamp
                    ROWS BETWEEN 14 PRECEDING AND CURRENT ROW
                ) AS ma_15
            FROM prices
        ),
        signals AS (
            SELECT *,
                LAG(ma_5) OVER (PARTITION BY asset ORDER BY timestamp) AS prev_ma_5,
                LAG(ma_15) OVER (PARTITION BY asset ORDER BY timestamp) AS prev_ma_15
            FROM indicators
        )
        SELECT
            timestamp,
            asset,
            open,
            high,
            low,
            close,
            volume,
            CASE
                WHEN prev_ma_5 <= prev_ma_15 AND ma_5 > ma_15 THEN  1.0
                WHEN prev_ma_5 >= prev_ma_15 AND ma_5 < ma_15 THEN -1.0
                ELSE 0.0
            END AS prediction
        FROM signals
        ORDER BY asset, timestamp
        """
    ).fetchdf()

    return signals_df


# --------------------------------------------------
# Performance metrics
# --------------------------------------------------
def compute_performance_kpis(df: pd.DataFrame, fees: float) -> Dict:
    df = df.copy()
    df["returns"] = df.groupby("asset")["close"].pct_change()
    df["pnl"] = df["prediction"] * df["returns"] - fees * abs(
        df.groupby("asset")["prediction"].diff()
    )

    pnl = df["pnl"].dropna()
    sharpe = pnl.mean() / pnl.std() * np.sqrt(252) if pnl.std() else 0.0

    return {
        "avg_daily_pnl": pnl.mean(),
        "sharpe": sharpe,
        "max_dd": (pnl.cumsum().cummax() - pnl.cumsum()).max(),
        "winrate": (pnl > 0).mean(),
        "turnover": abs(df["prediction"].diff()).mean(),
        "exposure": abs(df["prediction"]).mean(),
    }


# --------------------------------------------------
# Accumulated PnL
# --------------------------------------------------
def compute_accumulated_pnl(
    df: pd.DataFrame,
    bootstrap_windows: list[int],
) -> Dict:
    df = df.copy()
    df["returns"] = df.groupby("asset")["close"].pct_change()
    df["pnl"] = df["prediction"] * df["returns"]
    df["cum_pnl"] = df["pnl"].cumsum()

    return {w: df["cum_pnl"].rolling(w).mean().dropna().to_dict() for w in bootstrap_windows}


# --------------------------------------------------
# Chart.js PnL line chart
# --------------------------------------------------
def generate_pnl_chart_data(accum_pnl: Dict) -> Dict:
    datasets = []
    labels = None

    for window, pnl_dict in accum_pnl.items():
        series = pd.Series(pnl_dict)

        if labels is None:
            labels = series.index.astype(str).tolist()

        datasets.append(
            {
                "label": f"Window {window}",
                "data": series.values.tolist(),
                "tension": 0.1,
            }
        )

    return {
        "labels": labels,
        "datasets": datasets,
    }


def generate_ohlcv_chart_data(df: pd.DataFrame, symbol: str) -> dict:
    filtered_df = df[df["asset"] == symbol]

    ohlc = []
    volume = []
    volume_colors = []
    signals = []

    for row in filtered_df.itertuples():
        # convert pandas Timestamp to epoch ms
        timestamp: pd.Timestamp = row.timestamp  # type: ignore
        ts_ms = timestamp.value // 10**6

        ohlc.append(
            {
                "x": ts_ms,
                "o": row.open,
                "h": row.high,
                "l": row.low,
                "c": row.close,
            }
        )

        volume.append(
            {
                "x": ts_ms,
                "y": row.volume,
            }
        )

        # Conditional color: green if close > open, else red (with some transparency)
        color = "rgba(0, 200, 0, 0.5)" if row.close > row.open else "rgba(200, 0, 0, 0.5)"  # type: ignore
        volume_colors.append(color)

        if row.prediction != 0:
            signals.append(
                {
                    "x": ts_ms,
                    "y": row.close,
                }
            )

    return {
        "datasets": [
            {
                "label": symbol,
                "data": ohlc,
                "yAxisID": "price",
            },
            {
                "label": "Volume",
                "type": "bar",
                "data": volume,
                "yAxisID": "volume",
                "backgroundColor": volume_colors,
            },
            {
                "label": "Signal",
                "type": "scatter",
                "data": signals,
                "yAxisID": "price",
                "pointRadius": 5,
            },
        ]
    }


assets = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE"]
directions = ["LONG", "SHORT"]
statuses = ["active", "inactive", "none"]

rows = []

for i in range(50):
    asset = random.choice(assets)
    rows.append(
        {
            "Model": f"{asset} Strategy v{i+1}",
            "Identity": f"{asset.lower()}_{i:02d}",
            "PNL": round(random.uniform(-200, 500), 4),
            "Last Position Time": (
                None
                if random.random() < 0.2
                else f"2026-01-{random.randint(18,21)} {random.randint(0,23):02d}:00 UTC"
            ),
            "Job Status": random.choice(statuses),
            "Job Description": f"{asset} automated strategy",
            "Latest Symbol": f"{asset}USDT",
            "Latest Direction": random.choice(directions),
            "Latest PNL": round(random.uniform(-20, 40), 4),
            "Created At": f"2026-01-{random.randint(1,10):02d} 00:00 UTC",
        }
    )

display_df = pd.DataFrame(rows)
display_df = display_df.assign(
    Latest=display_df.apply(
        lambda r: (
            None
            if r["Latest Symbol"] is None
            else {
                "symbol": r["Latest Symbol"],
                "direction": r["Latest Direction"],
                "pnl": r["Latest PNL"],
            }
        ),
        axis=1,
    )
)
