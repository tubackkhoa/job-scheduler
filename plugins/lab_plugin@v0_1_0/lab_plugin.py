"""
Lab Plugin - Experimental environment for testing new configurations.
Hardcoded configuration for Lab worker.
"""

import logging
import pluggy
from pydantic import BaseModel, Field, field_validator

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class LabConfig(BaseModel):
    # Sigma Mode Selection
    use_normalized_sigma: bool = False  # Raw Sigma (0-9999 range)

    # Strategy Configuration
    data_source: str = "ohlcv_binance-futures"
    timeframe: str = "1h"
    max_execution_signals: int = Field(10, ge=0, le=30)
    total_trade_volume: int = 500
    token_blacklist: str = ""
    token_whitelist: str = ""
    direction_type: str = "all"  # All (Long + Short)

    # ML Filtering Thresholds
    min_mu_threshold: float = 0.01
    max_mu_threshold: float = 1.1
    ranking_threshold_min: float = 0.1
    ranking_threshold_max: float = 3.0
    min_sigma_threshold: float = 0.0
    max_sigma_threshold: float = 1.0

    # Ranking Method
    ranking_method: str = "risk_adjusted"  # Risk-Adjusted (μ - 1.3√σ)

    # Take Profit / Stop Loss
    alpha_tp: float = 2.0
    beta_sl: float = 4.0

    # Worker Settings
    model_type: str = "all"
    reverse_direction: bool = False
    max_trading_sessions: int = 0  # Unlimited

    @field_validator("timeframe")
    def validate_timeframe(cls, v: str) -> str:
        # simple validation – can be extended with full Timeframe enum check
        if v not in ["1h", "4h", "1d"]:
            raise ValueError(
                "timeframe must be one of the supported values [1h, 4h, 1d]"
            )
        return v


logger = logging.getLogger(__name__)


class LabPlugin:

    @hookimpl
    @classmethod
    def schema(cls):
        return LabConfig.model_json_schema()

    @hookimpl
    @classmethod
    def config(cls, json=None):
        return LabConfig.model_validate(json or {})

    @hookimpl
    @classmethod
    async def run(cls, config: LabConfig):
        logger.debug(f"running with config: {config}")
        return True
