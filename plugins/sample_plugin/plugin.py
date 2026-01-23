import logging
from pathlib import Path
import pluggy
from pydantic import BaseModel, Field
from typing import Any, Awaitable, Callable, List, Optional, ParamSpec
from datetime import datetime
from enforcer import ExecutionContext, job_permission
from plugins import ui_schema
from plugins.schema import SecureBaseModel, SecureField

from .data import JSON_TPL, SQL_TPL, YAML_TPL, MD_TPL, countries


PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


def ui_schema_binding(field_path: list[str]):
    return ui_schema(
        {
            "ui:field": "Version",
            "model:binding": field_path,
            "model:expr": {
                "list": "{{ dao.get_value_versions(field_id, search, limit, offset) | tojson }}",
                "detail": "{{ dao.get_value_version(id) | tojson }}",
                "create": "{{ dao.create_value_version(payload) | tojson }}",
                "update": "{{ dao.update_value_version(id, payload) | tojson }}",
            },
            "ui:options": {"size": 12},
        }
    )


class DynamicCode(BaseModel):
    code: str = Field(
        "",
        json_schema_extra=ui_schema(
            {
                "ui:field": "Dynamic",
                "code": Path(__file__).with_name("compile_plugin.js").read_text(),
                # "url": "CompilePluginComponent.tsx",
                "ui:options": {
                    "size": 6,
                },
            }
        ),
    )
    dynamic: str = Field(
        "",
        json_schema_extra=ui_schema(
            {
                "ui:field": "Dynamic",
                "ui:expr:code": ("{{ dynamic_code.code }}", ["dynamic_code.code"]),
                "ui:options": {
                    "size": 6,
                },
            }
        ),
    )


class Config(SecureBaseModel):

    dynamic_code: DynamicCode = Field(
        default_factory=DynamicCode,  # type: ignore
        json_schema_extra=ui_schema({"ui:options": {"size": 12, "section": True}}),
    )

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
                "default": [],  # to know type
                "ui:expr:default": (
                    "{{ get_cities_by_country(country) }}",
                    ["country"],  # dependency paths, can be many, eg : ["abc", "def"]
                ),
            }
        ),
    )
    js_template: str = SecureField(
        "",
        read="code_read",
        write="code_write",
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


class MyClass:
    def __init__(self, name):
        self.name = name  # Store some value in the instance

    @property
    def my_object(self):
        # Returns a fixed dictionary, can use self.name if you want
        return {"fixed": "object", "name": self.name}


@job_permission("fetch_data")
async def fetch_data(ctx: ExecutionContext):
    return ctx.user


P = ParamSpec("P")


class Plugin:

    _env = {
        "datetime": datetime,
        "fetch_data": fetch_data,
        "MyClass": MyClass,
        "get_users": lambda: ["tupt", "cuongnv"],
        "get_cities_by_country": lambda country_name: countries.get(country_name, []),
    }

    @hookimpl
    @classmethod
    def install(cls) -> bool:
        return True

    @hookimpl
    @classmethod
    def env(cls) -> dict[str, Any]:
        return cls._env

    @hookimpl
    @classmethod
    def schema(cls, ctx: ExecutionContext):
        return Config.model_json_schema(ctx)

    @hookimpl
    @classmethod
    def config(
        cls,
        ctx: ExecutionContext,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ):
        return Config.model_validate(ctx, json or {}, validate)

    @hookimpl
    @classmethod
    def roles(cls):
        return {
            "fetch_data": {"data", "admin"},
            "code_read": {"admin"},
            "code_write": {"admin"},
        }

    @hookimpl
    @classmethod
    async def run(
        cls,
        ctx: ExecutionContext,
        config: Config,
        logger: logging.Logger,
        render: Callable[..., Awaitable[Any]],
    ):
        version = await render(
            ctx,
            "{{ dao.get_value_version(id).value }}",
            config.model_dump(),
            **cls._env,
            id=config.sql_id,
        )

        print(version)

        # for i in range(10):
        #     logger.info(f"Running step {i}")
        #     await asyncio.sleep(0.5)
        # logger.info(config.model_dump())
        return True
