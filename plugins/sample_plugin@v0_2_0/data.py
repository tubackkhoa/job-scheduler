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


def create_signals(symbols=["BTC", "ETH", "SOL", "LINK"]):
    # --------------------------------------------------
    # 1. Resolve today prices from fixed map
    # --------------------------------------------------
    today_prices = {
        symbol: TODAY_PRICE_MAP[symbol]
        for symbol in symbols
        if symbol in TODAY_PRICE_MAP
    }

    if not today_prices:
        return pd.DataFrame()

    # --------------------------------------------------
    # 2. Generate random price history (anchored to today)
    # --------------------------------------------------
    np.random.seed(42)
    num_days = 60
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    rows = []
    for symbol, start_price in today_prices.items():
        price = start_price

        for i in reversed(range(num_days)):
            timestamp = today - timedelta(days=i)

            # backward random walk
            price_change = np.random.normal(0, price * 0.01)
            price = max(0.0001, price - price_change)

            rows.append(
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "close": round(price, 6 if price < 1 else 2),
                    "volume": np.random.randint(1_000_000, 50_000_000),
                }
            )

    df = pd.DataFrame(rows)

    # --------------------------------------------------
    # 3. DuckDB (in-memory)
    # --------------------------------------------------
    con = duckdb.connect(database=":memory:")
    con.register("prices_df", df)

    con.execute(
        """
        CREATE TABLE prices AS
        SELECT * FROM prices_df;
    """
    )

    # --------------------------------------------------
    # 4. MA crossover signals
    # --------------------------------------------------
    result = con.execute(
        """
        WITH indicators AS (
            SELECT
                timestamp,
                symbol,
                close,
                volume,
                AVG(close) OVER (
                    PARTITION BY symbol
                    ORDER BY timestamp
                    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                ) AS ma_5,
                AVG(close) OVER (
                    PARTITION BY symbol
                    ORDER BY timestamp
                    ROWS BETWEEN 14 PRECEDING AND CURRENT ROW
                ) AS ma_15
            FROM prices
        ),
        signals AS (
            SELECT *,
                LAG(ma_5) OVER (PARTITION BY symbol ORDER BY timestamp) AS prev_ma_5,
                LAG(ma_15) OVER (PARTITION BY symbol ORDER BY timestamp) AS prev_ma_15
            FROM indicators
        )
        SELECT
            timestamp,
            symbol,
            close,
            ma_5,
            ma_15,
            CASE
                WHEN prev_ma_5 <= prev_ma_15 AND ma_5 > ma_15 THEN 'BUY'
                WHEN prev_ma_5 >= prev_ma_15 AND ma_5 < ma_15 THEN 'SELL'
                ELSE 'HOLD'
            END AS signal
        FROM signals
        ORDER BY timestamp;
    """
    ).df()

    # --------------------------------------------------
    # 5. Latest signal per symbol
    # --------------------------------------------------
    return (
        result.sort_values("timestamp").groupby("symbol").tail(1).reset_index(drop=True)
    )
