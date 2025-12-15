"""
Production Plugin - Live trading with critical configurations.
Hardcoded configuration for Production worker.
"""

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


class ProdPlugin:

    _config = ProdConfig()

    @hookimpl
    def init(self, config):
        self._config = self._config.model_validate(config)
        return self._config

    @hookimpl
    def migrate(self, new_config):
        # transform config first
        self._config = self._config.model_validate(new_config)
        return self._config

    @hookimpl
    def schema(self):
        return self._config.model_json_schema()

    @hookimpl
    def config(self):
        return self._config

    @hookimpl
    async def run(self):
        return self._config
