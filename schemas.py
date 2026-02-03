from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class ConfigPayload(BaseModel):
    plugin_id: Optional[int] = Field(None, alias="pluginId")
    session_id: Optional[int] = Field(None, alias="sessionId")
    config: Optional[Dict[str, Any]] = None  # Use correct type if known
    description: Optional[str] = None

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
    interval: PositiveInt = Field(60)
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class TemplatePayload(BaseModel):
    template: str = Field(
        ...,
    )
    params: Dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class Settings(BaseSettings):

    # Field names match ENV_VAR names (case-insensitive by default)
    use_log_indexer: bool = False
    log_dir: str = "logs"
    log_max_size: int = 10 * 1024 * 1024
    log_max_files: int = 10
    log_retention_days: int = 7

    # Required fields from your previous error
    db_connection: str = ""
    module_path: Optional[str] = ""
    plugin_path: str = "plugins"
    user_plugin_path: str = "plugins"
    static_files: Optional[str] = ""

    # Configuration for loading from a .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_host: Optional[str] = None
    redis_port: Optional[int] = 0
    redis_db: Optional[int] = 0

    secret_key: str = ""
    admin_password: str = ""
    chatbot_enabled: bool = False
    jinja_cache_path: str = "cache/jinja"

    uat_endpoint_api: str = ""
    test_system_api_key: str = ""


settings = Settings()
