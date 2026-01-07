from typing import Any, Dict
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --------------------------------------------------
# Fixed "today" prices (can be adjusted anytime)
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
    result_df = con.execute(query).fetchdf()
    return result_df


def create_signals_for_backtest(symbols=["BTC", "ETH", "SOL", "LINK"]) -> pd.DataFrame:
    """
    Returns a full time-series suitable for Plugin backtesting
    """

    today_prices = {
        symbol: TODAY_PRICE_MAP[symbol] for symbol in symbols if symbol in TODAY_PRICE_MAP
    }

    if not today_prices:
        return pd.DataFrame()

    np.random.seed(42)
    num_days = 60
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    rows = []
    for symbol, start_price in today_prices.items():
        price = start_price

        for i in reversed(range(num_days)):
            timestamp = today - timedelta(days=i)
            price_change = np.random.normal(0, price * 0.01)
            price = max(0.0001, price - price_change)

            rows.append(
                {
                    "timestamp": timestamp,
                    "asset": symbol,  # 🔹 rename
                    "close": round(price, 6 if price < 1 else 2),
                    "volume": np.random.randint(1_000_000, 50_000_000),
                }
            )

    df = pd.DataFrame(rows)
    con.register("prices", df)

    signals_df = con.execute(
        """
        WITH indicators AS (
            SELECT
                timestamp,
                asset,
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


def compute_accumulated_pnl(df: pd.DataFrame, bootstrap_windows: list[int]) -> Dict:
    df = df.copy()
    df["returns"] = df.groupby("asset")["close"].pct_change()
    df["pnl"] = df["prediction"] * df["returns"]
    df["cum_pnl"] = df["pnl"].cumsum()

    return {w: df["cum_pnl"].rolling(w).mean().dropna().to_dict() for w in bootstrap_windows}


def generate_pnl_chart(accum_pnl: Dict) -> Dict:
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
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": datasets,
        },
        "options": {
            "responsive": True,
            "plugins": {"legend": {"display": True}},
        },
    }
