import logging
import pluggy
from pydantic import BaseModel, Field
from typing import List
import pandas as pd
from jinja2 import Environment, BaseLoader
from .data import (
    compute_accumulated_pnl,
    compute_performance_kpis,
    create_signals_for_backtest,
    generate_pnl_chart,
)

# --------------------------------------------------
# Pluggy setup
# --------------------------------------------------

PROJECT_NAME = "apluggy"
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)

# --------------------------------------------------
# Fixed prices (mock market)
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

# --------------------------------------------------
# Config schema
# --------------------------------------------------


class Config(BaseModel):
    base_assets: List[str] = Field(
        default_factory=list,
        json_schema_extra={"ui:field": "MultiSelect", "default": "BTC,ETH,SOL,BNB,LINK"},
    )
    fees: float = 0.001
    bootstrap_windows: List[int] = Field(
        default_factory=list,
        json_schema_extra={"ui:field": "MultiSelect", "default": [10, 20, 30, 60]},
    )
    report: str = Field(
        """

{# -------------------------------------------------- #}
{# 1. Generate signals programmatically (Option A)     #}
{# -------------------------------------------------- #}

{% set data_df = create_signals(base_assets) %}
{% set grouped = data_df.groupby("asset") %}

## Data
{{ data_df.head(10).to_markdown(index=False) }}

{# -------------------------------------------------- #}
{# 2. Run analytics                                   #}
{# -------------------------------------------------- #}

{% set performance_kpis = compute_performance_kpis(data_df, fees) %}
{% set accumulated_pnl = compute_accumulated_pnl(data_df, bootstrap_windows) %}

## Performance KPI
```json
{{ performance_kpis | tojson(indent=2) }}
```

{% set worst = data_df.nsmallest(10, "prediction") %}
{% set worst_cases = worst[["timestamp", "asset", "prediction"]] %}

## Worst case
{{ worst_cases.to_markdown(index=False) }}

{% set per_asset_analysis = [] %}
{% for asset, df in grouped %}
    {% set _ = per_asset_analysis.append(
        dict({"asset": asset}, **compute_performance_kpis(df, fees))
    )%}
{% endfor %}
{% set per_asset_analysis = DataFrame(per_asset_analysis) %}

## Per asset
{{ per_asset_analysis.to_markdown(index=False) }}

{% set chart = generate_pnl_chart(accumulated_pnl) %}

## PNL chart
```chart
{{chart | tojson }}
```
""",
        json_schema_extra={"ui:field": "Template", "type": "markdown"},
    )


# --------------------------------------------------
# Plugin
# --------------------------------------------------


class Plugin:
    _env = Environment(loader=BaseLoader(), autoescape=False)
    _env.globals.update(
        {
            "DataFrame": pd.DataFrame,
            "create_signals": create_signals_for_backtest,
            "compute_performance_kpis": compute_performance_kpis,
            "compute_accumulated_pnl": compute_accumulated_pnl,
            "generate_pnl_chart": generate_pnl_chart,
        }
    )

    @hookimpl
    @classmethod
    def env(cls):
        return cls._env

    @hookimpl
    @classmethod
    def schema(cls):
        return Config.model_json_schema()

    @hookimpl
    @classmethod
    def config(cls, json=None):
        return Config.model_validate(json or {})

    @hookimpl
    @classmethod
    async def run(cls, config: Config, logger: logging.Logger):
        # do something at background
        pass
