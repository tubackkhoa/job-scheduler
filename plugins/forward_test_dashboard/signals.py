import pandas as pd
from .parsing import parse_table_message
from log_service import LogService

logger = LogService(useIndexer=False)


def extract_signals(job_id: int, keyword: str) -> pd.DataFrame:
    scheduler_id = f"job-scheduler.job.{job_id}"
    result = logger.search_logs_with_following(
        job_id=scheduler_id,
        keyword=keyword,
        n_following=2,
        limit=50,
        sort="desc",
    )

    records = []

    for group in result.get("groups", []):
        msg = group["following_entries"][-1].get("message", "")
        parsed = parse_table_message(msg)
        if not parsed:
            continue

        df = pd.DataFrame(parsed["rows"], columns=parsed["header"])
        if {"pred_time", "base_asset"}.issubset(df.columns):

            if "new_mu" in df.columns:
                df["new_mu"] = pd.to_numeric(df["new_mu"], errors="coerce").fillna(0)
            else:
                df["new_mu"] = 0

            df["direction"] = "NONE"
            df.loc[df["new_mu"] > 0, "direction"] = "LONG"
            df.loc[df["new_mu"] < 0, "direction"] = "SHORT"

            if "gated_flag" in df.columns:
                df["is_gated"] = df["gated_flag"].isin(["1", "True", "1.0"])
            else:
                df["is_gated"] = False

            records.append(df)

    result_df = pd.concat(records, ignore_index=True) if records else pd.DataFrame()

    if not result_df.empty and "is_gated" in result_df.columns:
        # 🔥 THIS is the critical line
        result_df["is_gated"] = result_df["is_gated"].astype(object)

    return result_df
