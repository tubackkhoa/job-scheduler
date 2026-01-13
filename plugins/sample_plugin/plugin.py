import json
import logging
import pluggy
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from typing import Any, Callable, List
import sqlglot
from datetime import datetime
from jinja2 import DictLoader, Environment

from plugins import ui_schema

from .data import JSON_TPL, SQL_TPL, YAML_TPL, MD_TPL, countries


PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


def ui_schema_binding(field_path: list[str]):
    return ui_schema(
        {
            "ui:field": "Version",
            "model:binding": field_path,
            "model:expr": {
                "list": "{{ get_value_versions(field_id, search, limit, offset) | tojson }}",
                "detail": "{{ get_value_version(id) | tojson }}",
                "create": "{{ create_value_version(payload) | tojson }}",
                "update": "{{ update_value_version(id, payload) | tojson }}",
            },
            "ui:options": {"size": 12},
        }
    )


class Config(BaseModel):
    warmup_bars: int = 150
    extra_bars: int = 1
    quote_asset: str = "USDT"
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
    country: str = Field(
        "USA",
        json_schema_extra=ui_schema(
            {
                "ui:widget": "select",
                "enum": list(countries.keys()),
                "ui:options": {"size": 6},
            }
        ),
    )
    city: List[str] = Field(
        default_factory=list,
        json_schema_extra=ui_schema(
            {
                "ui:field": "Select",
                "ui:options": {"size": 6, "multiple": True},
                "ui:expr": (
                    "{ default: {{ get_cities_by_country(country) }} }",
                    ["country"],  # dependency paths, can be many, eg : ["abc"], ["abc", "def"]
                ),
            }
        ),
    )
    js_template: str = Field(
        "",
        json_schema_extra=ui_schema({"ui:field": "Template", "type": "js"}),
    )
    sql_id: int = Field(
        0,
        title="Search / Select SQL Version",
        json_schema_extra=ui_schema_binding(["sql"]),
    )
    sql: str = Field(
        SQL_TPL,
        json_schema_extra=ui_schema({"ui:field": "Template", "type": "sql"}),
    )
    json_template: str = Field(
        JSON_TPL,
        json_schema_extra=ui_schema({"ui:field": "Template", "type": "json"}),
    )
    yaml_template: str = Field(
        YAML_TPL,
        json_schema_extra=ui_schema({"ui:field": "Template", "type": "yaml"}),
    )
    md_id: int = Field(
        0,
        title="Search / Select Markdown Version",
        json_schema_extra=ui_schema_binding(["md_template"]),
    )
    md_template: str = Field(
        MD_TPL,
        json_schema_extra=ui_schema({"ui:field": "Template", "type": "markdown"}),
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
        }
    )

    _env.filters["in_clause"] = lambda values: (
        "()" if not values else "(" + ",".join(repr(v) for v in values) + ")"
    )

    @hookimpl
    @classmethod
    def install(cls) -> bool:
        return True

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
    def roles(cls):
        return {"admin"}

    @hookimpl
    @classmethod
    async def run(
        cls, config: Config, logger: logging.Logger, render: Callable[[str, Environment, dict], Any]
    ):
        version = json.loads(
            render("{{ get_value_version(id) | tojson }}", cls._env, {"id": config.sql_id})
        )
        logger.info(version["value"])
        # for i in range(10):
        #     logger.info(f"Running step {i}")
        #     await asyncio.sleep(0.5)
        # logger.info(config.model_dump())
        return True
