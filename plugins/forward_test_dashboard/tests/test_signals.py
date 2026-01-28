import pandas as pd
from signals import extract_signals


class FakeLogService:
    """Mock LogService to avoid hitting real logs"""

    def search_logs_with_following(self, **kwargs):
        return {
            "groups": [
                {
                    "following_entries": [
                        {
                            "message": """
                            ranking table ::::
                            pred_time base_asset new_mu gated_flag
                            2026-01-01 00:00:00 BTC  0.12  0
                            2026-01-01 01:00:00 ETH -0.34  1
                            2026-01-01 02:00:00 SOL  0     0
                            """
                        }
                    ]
                }
            ]
        }


def test_extract_signals_basic(monkeypatch):
    # Monkeypatch the logger used in signals.py
    from signals import logger

    monkeypatch.setattr(
        logger, "search_logs_with_following", FakeLogService().search_logs_with_following
    )

    df = extract_signals(job_id=123, keyword="ranking table")

    assert not df.empty
    assert set(df["base_asset"]) == {"BTC", "ETH", "SOL"}

    # Direction logic
    assert df.loc[df["base_asset"] == "BTC", "direction"].iloc[0] == "LONG"
    assert df.loc[df["base_asset"] == "ETH", "direction"].iloc[0] == "SHORT"
    assert df.loc[df["base_asset"] == "SOL", "direction"].iloc[0] == "NONE"

    # Gating
    assert df.loc[df["base_asset"] == "ETH", "is_gated"].iloc[0] is True
    assert df.loc[df["base_asset"] == "BTC", "is_gated"].iloc[0] is False


def test_extract_signals_missing_optional_columns(monkeypatch):
    """Should not crash if gated_flag or new_mu is missing"""

    from signals import logger

    monkeypatch.setattr(
        logger,
        "search_logs_with_following",
        lambda **_: {
            "groups": [
                {
                    "following_entries": [
                        {
                            "message": """
                            ranking table ::::
                            pred_time base_asset
                            2026-01-01 BTC
                            """
                        }
                    ]
                }
            ]
        },
    )

    df = extract_signals(job_id=1, keyword="ranking")

    assert not df.empty
    assert df["direction"].iloc[0] == "NONE"
    assert df["is_gated"].iloc[0] is False


def test_extract_signals_empty_logs(monkeypatch):
    from signals import logger

    monkeypatch.setattr(
        logger,
        "search_logs_with_following",
        lambda **_: {"groups": []},
    )

    df = extract_signals(job_id=1, keyword="ranking")
    assert df.empty
