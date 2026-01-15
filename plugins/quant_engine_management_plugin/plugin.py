from enum import Enum
from typing import Callable, Any
import logging
from pydantic import BaseModel
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from plugins import ui_schema, ui_schema_crud
from jinja2.loaders import DictLoader
from jinja2.environment import Environment
import pluggy
PROJECT_NAME = "quant_engine_management_plugin"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class ModelEnv(str, Enum):
    staging = "staging"
    production = "production"
    uat = "uat"
    uat_test = "forward_test"
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
        return True
