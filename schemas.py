from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, PositiveInt


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
