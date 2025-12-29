import asyncio
import logging
import pluggy
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from typing import List
import sqlglot
from datetime import datetime
from jinja2 import DictLoader, Environment, BaseLoader


PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Config(BaseModel):
    warmup_bars: int = 150
    extra_bars: int = 1
    quote_asset: str = "USDT"
    base_assets: List[str] = Field(
        default_factory=list,
        json_schema_extra={"ui:field": "MultiSelect", "default": "BTC,ETH,SOL,BNB,LINK"},
    )
    sql: str = Field(
        """
{% set infer_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') %}
{% set users = get_users() %}

WITH time_bounds AS (
  SELECT
    TIMESTAMP '{{ infer_ts }}' AS infer_ts,
    TIMESTAMP '{{ infer_ts }}'
      - INTERVAL '{{ warmup_bars + extra_bars }} hour' AS ts_warmup_start
),

ohlcv_binance_futures_in_range AS (
  SELECT *
  FROM public."ohlcv_binance-futures_1h" t
  CROSS JOIN time_bounds b
  WHERE t.quote_asset = '{{ quote_asset }}'
    AND t.user in {{ users | in_clause }}
    AND t.base_asset IN {{ base_assets | in_clause }}
    AND t.open_time >= b.ts_warmup_start
    AND t.open_time <= b.infer_ts
)

SELECT * FROM ohlcv_binance_futures_in_range;
""",
        json_schema_extra={"ui:field": "Template", "type": "sql"},
    )
    json_template: str = Field(
        """
{% extends "base" %}
{% block content %}
{
  "name": {{obj.name|tojson}},
  "my_object": {{obj.my_object|tojson}},
  "quote_asset": {{ quote_asset | tojson }},
  "extra_bars": {{ extra_bars }},
  "base_assets": {{ base_assets | tojson }}
}
{% endblock %}
""",
        json_schema_extra={"ui:field": "Template", "type": "json"},
    )
    yaml_template: str = Field(
        """
quote_asset: {{ quote_asset }}
extra_bars: {{ extra_bars }}
base_assets:
{% for base_asset in base_assets %}
  - {{ base_asset }}
{% endfor %}
""",
        json_schema_extra={"ui:field": "Template", "type": "yaml"},
    )

    @field_validator("sql", mode="after")
    @classmethod
    def validate_sql(cls, sql: str, info: ValidationInfo):
        """Validate raw_sql using sqlglot for DuckDB SQL syntax."""
        try:
            template_engine = Plugin.env().from_string(sql)
            sqlglot.parse_one(template_engine.render(**info.data))
            return sql
        except Exception as e:
            raise ValueError(f"Error validating SQL: {str(e)}")


class MyClass:
    def __init__(self, name):
        self.name = name  # Store some value in the instance

    @property
    def my_object(self):
        # Returns a fixed dictionary, can use self.name if you want
        return {"fixed": "object", "name": self.name}


class Plugin:

    _env = Environment(
        loader=DictLoader(
            {
                "base": """
{% set obj = MyClass("ChatGPT") %}
{% block content %}{% endblock %}
"""
            }
        ),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    _env.globals["datetime"] = datetime
    _env.globals["MyClass"] = MyClass
    _env.globals["get_users"] = lambda: ["tupt", "cuongnv"]
    _env.filters["in_clause"] = lambda values: (
        "()"
        if not values
        else "(" + ",".join('"' + str(v).replace('"', '\\"') + '"' for v in values) + ")"
    )

    @hookimpl
    @classmethod
    def env(cls) -> Environment:
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
        for i in range(10):
            logger.info(f"Running step {i}")
            await asyncio.sleep(0.5)
        logger.info(config.model_dump())

        return True
