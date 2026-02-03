import random

import pandas as pd

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
)[["Model", "Identity", "PNL", "Job Status", "Latest", "Created At"]]
