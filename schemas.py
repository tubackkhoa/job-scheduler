from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigPayload(BaseModel):
    plugin_id: Optional[int] = Field(None, alias="pluginId")
    session_id: Optional[int] = Field(None, alias="sessionId")
    config: Optional[Dict[str, Any]] = None  # Use correct type if known
    description: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        extra = "forbid"


class DownloadPayload(BaseModel):
    version: str = Field(
        ...,
        examples=[
            "git+https://github.com/user/repo@branch",
            "1.2.3",
        ],
    )

    class Config:
        extra = "forbid"


class PluginCreatePayload(BaseModel):
    package: str
    interval: PositiveInt = Field(60)
    description: Optional[str] = None

    class Config:
        extra = "forbid"


class TemplatePayload(BaseModel):
    template: str = Field(
        ...,
    )
    params: Dict[str, Any]

    class Config:
        extra = "forbid"


class Settings(BaseSettings):

    # Field names match ENV_VAR names (case-insensitive by default)
    use_log_indexer: bool = False
    log_dir: str = "logs"
    log_max_size: int = 10 * 1024 * 1024
    log_max_files: int = 10
    log_retention_days: int = 7

    # Required fields from your previous error
    db_connection: str = Field(default=...)
    module_path: str = ""
    static_files: Optional[str] = Field(default=...)

    # Configuration for loading from a .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
