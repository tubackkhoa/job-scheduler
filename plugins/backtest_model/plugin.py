import logging
from pathlib import Path
import pluggy
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, List, Optional, cast
import pandas as pd
from schemas import settings
from enforcer import ExecutionContext


from plugins import ui_schema, CodeSchema

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
    model_config = ConfigDict(
        json_schema_extra=ui_schema(
            {
                **(
                    {"url": "forwardtest/Portal.tsx"}
                    if settings.env == "dev"
                    else {"code": Path(__file__).with_name("portal.js").read_text()}
                )
            }
        )
    )
    base_assets: List[str] = Field(
        default_factory=list,
        json_schema_extra=ui_schema(
            {
                "ui:field": "Select",
                "default": "BTC,ETH,SOL,BNB,LINK",
                "ui:options": {"multiple": True},
            }
        ),
    )
    fees: float = 0.001
    bootstrap_windows: List[int] = Field(
        default_factory=list,
        json_schema_extra=ui_schema(
            {
                "ui:field": "Select",
                "default": [10, 20, 30, 60],
                "ui:options": {"multiple": True, "size": 6},
            }
        ),
    )
    report: str = Field(
        """
```module
function generateRandomRows(
  symbol,
  candles = 200,
  startPrice = 100,
) {
  const rows = [];
  let price = startPrice;
  let ts = Date.now() - candles * 60_000;

  for (let i = 0; i < candles; i++) {
    const open = price;
    const change = (Math.random() - 0.5) * 0.02;
    const close = open * (1 + change);
    const high = Math.max(open, close) * (1 + Math.random() * 0.003);
    const low = Math.min(open, close) * (1 - Math.random() * 0.003);

    price = close;

    rows.push({
      timestamp: ts,
      asset: symbol,
      open,
      high,
      low,
      close,
      volume: Math.random() * 100,
      prediction: [-1, 0, 1][Math.floor(Math.random() * 3)],
    });

    ts += 60_000;
  }

  return rows;
}
return [
      ...generateRandomRows('BTC', 300, 42000),
      ...generateRandomRows('ETH', 300, 2800),
      ...generateRandomRows('SOL', 300, 120),
      ...generateRandomRows('AVAX', 300, 35),
      ...generateRandomRows('LINK', 300, 15),
      ...generateRandomRows('DOGE', 300, 0.12),
    ]
```
        """,
        json_schema_extra=ui_schema(
            {
                "ui:field": "Template",
                "type": "markdown",
                **(
                    {"url": "LightweighChart.tsx"}
                    if settings.env == "dev"
                    else {"code": Path(__file__).with_name("lightweight_chart.js").read_text()}
                ),
            }
        ),
    )


# --------------------------------------------------
# Plugin
# --------------------------------------------------


class Plugin:

    _env = {
        "DataFrame": pd.DataFrame,
    }

    _routes: list[tuple[str, CodeSchema]] = [
        # empty route will be use as portal
        ("", cast(CodeSchema, Config.model_config.get("json_schema_extra"))),
        (
            "dashboard",
            (
                {"url": "backtest/Dashboard.tsx"}
                if settings.env == "dev"
                else {"code": Path(__file__).parent.joinpath("backtest/dashboard.js").read_text()}
            ),
        ),
        # (
        #     "dashboard/jobs/:job_jd",
        #     {
        #         "url": "backtest/Job.tsx"
        #         # "code": Path(__file__).parent.joinpath("backtest/job.js").read_text()
        #     },
        # ),
    ]

    @classmethod
    @hookimpl
    def env(cls):
        return cls._env

    @classmethod
    @hookimpl
    def schema(cls, ctx: ExecutionContext):
        return Config.model_json_schema()

    @classmethod
    @hookimpl
    def roles(cls):
        return {}

    @classmethod
    @hookimpl
    def routes(cls) -> list[tuple[str, CodeSchema]]:
        # using function so that it will delete memory because page can be huge
        return cls._routes

    @classmethod
    @hookimpl
    def config(
        cls,
        ctx: ExecutionContext,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ):
        return Config.model_validate(json or {})

    @classmethod
    @hookimpl
    async def run(cls, config: Config, logger: logging.Logger):
        # do something at background
        pass
