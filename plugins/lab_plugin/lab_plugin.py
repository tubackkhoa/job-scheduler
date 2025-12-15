"""
Lab Plugin - Experimental environment for testing new configurations.
Hardcoded configuration for Lab worker.
"""

import pluggy

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


# Hardcoded Lab Configuration
LAB_CONFIG = {
    # Sigma Mode Selection
    "use_normalized_sigma": False,  # Raw Sigma (0-9999 range)
    
    # Strategy Configuration
    "data_source": "ohlcv_binance-futures",
    "timeframe": "1h",
    "max_execution_signals": 10,
    "total_trade_volume": 500,
    "token_blacklist": "",
    "token_whitelist": "",
    "direction_type": "all",  # All (Long + Short)
    
    # ML Filtering Thresholds
    "min_mu_threshold": 0.01,
    "max_mu_threshold": 1.1,
    "ranking_threshold_min": 0.1,
    "ranking_threshold_max": 3.0,
    "min_sigma_threshold": 0.0,
    "max_sigma_threshold": 1.0,
    
    # Ranking Method
    "ranking_method": "risk_adjusted",  # Risk-Adjusted (μ - 1.3√σ)
    
    # Take Profit / Stop Loss
    "alpha_tp": 2.0,
    "beta_sl": 4.0,
    
    # Worker Settings
    "model_type": "all",
    "reverse_direction": False,
    "max_trading_sessions": 0,  # Unlimited
}


class LabPlugin:
    @hookimpl
    def init(self, config):
        # Merge hardcoded config with any runtime config
        self.config = {**LAB_CONFIG, **(config or {})}

    @hookimpl
    def migrate(self, new_config):
        # Preserve hardcoded values, update with new config
        self.config = {**LAB_CONFIG, **(new_config or {})}

    @hookimpl
    async def run(self):
        return self.config