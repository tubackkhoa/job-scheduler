import logging
import pluggy
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from typing import List
import sqlglot
from datetime import datetime
from jinja2 import Environment, BaseLoader


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
    sql: str = Field("SELECT 1", json_schema_extra={"ui:field": "Template", "type": "sql"})
    json_template: str = Field("{}", json_schema_extra={"ui:field": "Template", "type": "json"})
    yaml_template: str = Field("root:1", json_schema_extra={"ui:field": "Template", "type": "yaml"})

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


class Plugin:

    _env = Environment(
        loader=BaseLoader(),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    _env.globals["datetime"] = datetime
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
        logger.info(config.model_dump())

        return True
