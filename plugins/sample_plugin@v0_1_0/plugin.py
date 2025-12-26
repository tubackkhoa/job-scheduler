import asyncio
import logging
import pluggy
from pydantic import BaseModel, Field, model_validator
from typing import List
import sqlglot
from .sql_process import generate_sql

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Config(BaseModel):
    sql: str = Field("1.0", json_schema_extra={"ui:field": "Sql"})
    warmup_bars: int = 150
    extra_bars: int = 1
    quote_asset: str = "USDT"
    base_assets: List[str] = Field(
        default_factory=list,
        json_schema_extra={"ui:field": "MultiSelect", "default": "BTC,ETH,SOL,BNB,LINK"},
    )

    @model_validator(mode="after")
    def validate_sql_against_config(self):
        """Validate raw_sql using sqlglot for DuckDB SQL syntax."""
        sql = generate_sql(self.sql, self.model_dump(exclude={"sql"}))
        try:
            sqlglot.parse_one(sql)
            return self
        except Exception as e:
            raise ValueError(f"Error validating SQL: {str(e)}")


class Plugin:

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
        sql = generate_sql(config.sql, config.model_dump(exclude={"sql"}))
        logger.info(sql)

        return True
