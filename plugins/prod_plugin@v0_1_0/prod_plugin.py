"""
Production Plugin - Live trading with critical configurations.
Hardcoded configuration for Production worker.
"""

import logging
import pluggy
from pydantic import BaseModel

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class ProdConfig(BaseModel):
    # Sigma Mode Selection
    use_normalized_sigma: bool = False  # Raw Sigma (0-9999 range)

    # Strategy Configuration
    data_source: str = "ohlcv_binance-futures"
    timeframe: str = "1h"
    max_execution_signals: int = 10
    total_trade_volume: int = 500
    token_blacklist: str = ""
    token_whitelist: str = ""
    direction_type: str = "all"  # All (Long + Short)

    # ML Filtering Thresholds (most conservative for production)
    min_mu_threshold: float = 0.03
    max_mu_threshold: float = 0.9
    ranking_threshold_min: float = 0.2
    ranking_threshold_max: float = 2.0
    min_sigma_threshold: float = 0.0
    max_sigma_threshold: float = 0.6

    # Ranking Method
    ranking_method: str = "risk_adjusted"  # Risk-Adjusted (μ - 1.3√σ)

    # Take Profit / Stop Loss
    alpha_tp: float = 2.0
    beta_sl: float = 4.0

    # Worker Settings
    model_type: str = "all"
    reverse_direction: bool = False
    max_trading_sessions: int = 0  # Unlimited


logger = logging.getLogger(__name__)


class ProdPlugin:

    @hookimpl
    @classmethod
    def schema(cls):
        return ProdConfig.model_json_schema()

    @hookimpl
    @classmethod
    def config(cls, json):
        return ProdConfig.model_validate(json or {})

    @hookimpl
    @classmethod
    async def run(cls, config: ProdConfig):
        logger.info(f"running with config: {config}")
        return True
