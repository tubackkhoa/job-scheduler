from enum import Enum
from typing import Callable, Any, Optional
import logging
from pydantic import BaseModel
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from enforcer import ExecutionContext
from plugins import ui_schema
from jinja2.loaders import DictLoader
from jinja2.environment import Environment
from pathlib import Path
import pluggy

PROJECT_NAME = "quant_engine_management_plugin"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


def ui_schema_crud(
    field_path: list[str],
    crud_exprs: dict[str, str] | None = None,
    field_code: Optional[str] = None,
    field_url: Optional[str] = None,
    deps: list[str] | None = None,
    ui_options: dict | None = None,
) -> dict:
    """
    Generic CRUD field schema helper with full expression flexibility.

    Args:
        field_path: Path to the value field (e.g., ["model_type"])
        crud_exprs: Dict of operation -> jinja expression. Keys: list, detail, create, update, delete
                   Example: {"list": "j`{{ my_list_func('${field_id}') | tojson }}`"}
        deps: List of dependency field paths to inject into context (e.g., ["api_url", "api_key"])
        ui_options: Additional UI options (size, etc.)

    Usage:
        model_type_id: int = Field(
            0,
            json_schema_extra=ui_schema_crud(
                field_path=["model_type"],
                crud_exprs={
                    "list": "j`{{ list_model_types('${field_id}', '${search}', ${api_url}) | tojson }}`",
                    "create": "j`{{ sync_model_types(${api_url}, ${api_key}) | tojson }}`",
                },
                deps=["api_url", "api_key"],
            ),
        )
    """

    model_expr = {**(crud_exprs or {})}

    schema: dict = {
        # "ui:field": "Crud",
        "ui:field": "Dynamic",
        "code": field_code,
        "url": field_url,
        "model:binding": field_path,
        "model:expr": model_expr,
        "ui:options": {"size": 12, **(ui_options or {})},
    }

    if deps:
        schema["model:deps"] = deps

    return ui_schema(schema)


class ModelEnv(str, Enum):
    staging = "staging"
    production = "production"
    uat = "uat"
    uat_test = "uat_testing_multiple_models"

    def __str__(self):
        return self.value


class Config(BaseModel):
    webhook_url: str = Field(
        "",
        title="Webhook URL",
        json_schema_extra=ui_schema({"ui:options": {"size": 6}}),
    )

    webhook_api_key: str = Field(
        "",
        title="Webhook API Key",
        json_schema_extra=ui_schema({"ui:widget": "password", "ui:options": {"size": 6}}),
    )

    env: ModelEnv = ModelEnv.staging

    # webhook_test_apikey: str = Field(
    #     "",
    #     title="Test API Key",
    #     json_schema_extra=ui_schema({
    #         "ui:widget": "password",
    #         "ui:options": {"size": 6},
    #         "ui:expr": (
    #             """{"ui:classNames": '{{ "hidden" if env != "uat_testing_multiple_models" else "" }}', "default": {{ webhook_api_key | tojson if env != "uat_testing_multiple_models" else "" | tojson }}}""",
    #             ["env", "webhook_api_key"],
    #         ),
    #     }),
    # )

    model_type: str = Field(
        "",
        title="Model Type",
        json_schema_extra=ui_schema_crud(
            field_url=Path(__file__).parent.joinpath("crud.js").read_text(),
            # field_url="CrudField.tsx",
            field_path=["model_type"],
            crud_exprs={
                "list": "{{ list_trade_models(env, webhook_url, webhook_api_key) | tojson }}",
                "create": "{{ create_trade_model(payload, webhook_url, webhook_api_key, env) | tojson }}",
                "delete": "{{ deactivate_trade_model(key, webhook_url, webhook_api_key, env) | tojson }}",
            },
            deps=["webhook_url", "webhook_api_key", "env"],
            ui_options={
                "createSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "title": "Key"},
                        "name": {"type": "string", "title": "Name"},
                        "description": {"type": "string", "title": "Description"},
                        "source": {"type": "string", "title": "Source"},
                        "detail": {"type": "string", "title": "Detail (JSON)"},
                    },
                    "required": ["key", "name"],
                }
            },
        ),
    )


class Plugin:

    _env = Environment(
        loader=DictLoader({"base": "{% block content %}{% endblock %}"}),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
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
    def schema(cls, ctx):
        return Config.model_json_schema()

    @hookimpl
    @classmethod
    def config(
        cls,
        ctx: ExecutionContext,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ):
        return Config.model_validate(json or {})

    @hookimpl
    @classmethod
    def roles(cls):
        return {}

    @hookimpl
    @classmethod
    async def run(
        cls, config: Config, logger: logging.Logger, render: Callable[[str, Environment, dict], Any]
    ):
        return True
