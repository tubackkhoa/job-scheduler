from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Annotated
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class ConfigPayload(BaseModel):
    plugin_id: Optional[int] = Field(None)
    session_id: Optional[int] = Field(None)
    config: Optional[Dict[str, Any]] = None  # Use correct type if known
    description: Optional[str] = None
    cron_expr: str = Field("")
    model_config = ConfigDict(validate_by_name=True, extra="forbid")


class TemplateCodePayload(BaseModel):
    script: str
    form: str


class DownloadPayload(BaseModel):
    version: str = Field(
        ...,
        examples=[
            "git+https://github.com/user/repo@branch",
            "1.2.3",
        ],
    )

    model_config = ConfigDict(extra="forbid")


class PluginCreatePayload(BaseModel):
    package: str
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class TemplatePayload(BaseModel):
    template: str = Field(
        ...,
    )
    params: Dict[str, Any]

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class JobQuery:
    search_text: Optional[str] = None
    active: Optional[bool] = None

    plugin_id: Annotated[Optional[list[int]], Query()] = None
    session_id: Annotated[Optional[list[int]], Query()] = None

    order_by: str = "id"
    sort: str = "desc"
    limit: int = 20
    offset: int = 0


class Settings(BaseSettings):

    # Configuration for loading from a .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Field names match ENV_VAR names (case-insensitive by default)
    use_log_indexer: bool = False
    log_dir: str = "logs"
    log_max_size: int = 10 * 1024 * 1024
    log_max_files: int = 10
    log_retention_days: int = 7
    min_gzip_size: Optional[int] = None

    # Required fields from your previous error
    db_connection: str = ""
    module_path: Optional[str] = ""
    plugin_path: str = "plugins"
    user_plugin_path: str = "plugins"
    static_files: Optional[str] = ""

    redis_host: Optional[str] = None
    redis_port: Optional[int] = 0
    redis_db: Optional[int] = 0

    secret_key: str = ""
    admin_password: str = ""
    chatbot_enabled: bool = False
    jinja_cache_path: str = "cache/jinja"

    uat_endpoint_api: str = ""
    test_system_api_key: str = ""
    env: Literal["prod", "dev"] = "prod"


settings = Settings()
