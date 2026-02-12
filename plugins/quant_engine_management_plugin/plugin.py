from enum import Enum
from typing import Callable, Any, Optional
import logging
from pydantic import BaseModel, ConfigDict
from pydantic import BaseModel, Field
from enforcer import ExecutionContext
from plugins import ui_schema
import pluggy
from .api import (
    activate_forwardtest_model,
    deactivate_trade_model,
    list_trade_models,
    create_trade_model,
)

from schemas import settings

PROJECT_NAME = "job-scheduler"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


def ui_schema_crud(
    field_path: list[str],
    crud_exprs: dict[str, str] | None = None,
    field_code: Optional[str] = None,
    field_url: Optional[str] = None,
    deps: list[str] | None = None,
    ui_options: dict | None = None,
) -> dict:

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
    uat_test = "forward_test"

    def __str__(self):
        return self.value


class Config(BaseModel):

    model_config = ConfigDict(
        json_schema_extra=ui_schema(
            {"url": "HealthPortal.tsx" if settings.env == "dev" else "/assets/{package}/portal.js"}
        )
    )

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

    model_type: str = Field(
        "",
        title="Model Type",
        json_schema_extra=ui_schema_crud(
            field_path=["model_type"],
            field_url="CrudField.tsx" if settings.env == "dev" else "/assets/{package}/crud.js",
            crud_exprs={
                "list": "{{ list_trade_models(env) | tojson }}",
                "create": "{{ create_trade_model(payload, env) | tojson }}",
                "delete": "{{ deactivate_trade_model(key, env) | tojson }}",
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

    _env = {
        "list_trade_models": list_trade_models,
        "create_trade_model": create_trade_model,
        "deactivate_trade_model": deactivate_trade_model,
    }

    _routes: list[tuple[str, Any]] = [
        # empty route will be use as portal
        ("", Config.model_config.get("json_schema_extra")),
    ]

    @classmethod
    @hookimpl
    def install(cls) -> bool:
        return True

    @classmethod
    @hookimpl
    def env(cls):
        return cls._env

    @classmethod
    @hookimpl
    def schema(cls, ctx):
        return Config.model_json_schema()

    @classmethod
    @hookimpl
    def config(
        cls,
        ctx,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ):
        return Config.model_validate(json or {})

    @classmethod
    @hookimpl
    def on_active_job(cls, ctx: ExecutionContext, json: Optional[dict[str, Any]] = None):
        if not json:
            return
        model_key = json.get("model_key")
        if json.get("model_tag") == ModelEnv.uat_test and model_key:
            activate_forwardtest_model(ctx, model_key)

    @classmethod
    @hookimpl
    def on_deactive_job(cls, ctx: ExecutionContext, json: Optional[dict[str, Any]] = None):
        if not json:
            return
        model_key = json.get("model_key")
        if json.get("model_tag") == ModelEnv.uat_test and model_key:
            deactivate_trade_model(ctx, model_key)

    @classmethod
    @hookimpl
    def roles(cls):
        return {}

    @classmethod
    @hookimpl
    def routes(cls) -> list[tuple[str, Any]]:
        return cls._routes

    @classmethod
    @hookimpl
    async def run(
        cls,
        config: Config,
        logger: logging.Logger,
        render: Callable[[ExecutionContext, str, dict], Any],
    ):
        return True
