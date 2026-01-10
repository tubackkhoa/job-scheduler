import asyncio
import logging
import pluggy
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from typing import List
import sqlglot
from datetime import datetime
from jinja2 import DictLoader, Environment

from .models import (
    sync_database,
    create_sql_version,
    get_sql_version,
    get_sql_versions,
    update_sql_version,
)
from .data import JSON_TPL, SQL_TPL, YAML_TPL, MD_TPL, countries


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
    country: str = Field(
        "USA",
        json_schema_extra={
            "ui:widget": "select",
            "enum": list(countries.keys()),
            "ui:options": {"size": 6},
        },
    )
    city: List[str] = Field(
        default_factory=list,
        json_schema_extra={
            "ui:field": "MultiSelect",
            "ui:options": {"size": 6},
            "ui:expr": [
                """
            { default: j`{{ get_cities_by_country(country) }}` }
        """,
                ["country"],  # dependency paths, can be many, eg : ["abc"], ["abc", "def"]
            ],
        },
    )
    js_template: str = Field(
        "",
        json_schema_extra={"ui:field": "Template", "type": "js"},
    )
    sql_id: int = Field(
        0,
        title="Search / Select SQL Version",
        json_schema_extra={
            "ui:field": "Version",
            "binding": ["sql"],
            "model:expr": {
                "list": "j`{{ get_sql_versions('${search}', ${limit}, ${offset}) | tojson }}`",
                "detail": "j`{{ get_sql_version(${id}) | tojson }}`",
                "create": "j`{{ create_sql_version(${payload}) | tojson }}`",
                "update": "j`{{ update_sql_version(${id}, ${payload}) | tojson }}`",
            },
            "ui:options": {"size": 12},
        },
    )
    sql: str = Field(
        SQL_TPL,
        json_schema_extra={"ui:field": "Template", "type": "sql"},
    )
    json_template: str = Field(
        JSON_TPL,
        json_schema_extra={"ui:field": "Template", "type": "json"},
    )
    yaml_template: str = Field(
        YAML_TPL,
        json_schema_extra={"ui:field": "Template", "type": "yaml"},
    )
    md_template: str = Field(
        MD_TPL,
        json_schema_extra={"ui:field": "Template", "type": "markdown"},
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
        loader=DictLoader({"base": "{% block content %}{% endblock %}"}),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    _env.globals.update(
        {
            "datetime": datetime,
            "MyClass": MyClass,
            "get_users": lambda: ["tupt", "cuongnv"],
            "get_cities_by_country": lambda country_name: countries.get(country_name, []),
            "get_sql_versions": get_sql_versions,
            "get_sql_version": get_sql_version,
            "update_sql_version": update_sql_version,
            "create_sql_version": create_sql_version,
        }
    )

    _env.filters["in_clause"] = lambda values: (
        "()" if not values else "(" + ",".join(repr(v) for v in values) + ")"
    )

    @hookimpl
    @classmethod
    def install(cls) -> bool:
        return sync_database()

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
