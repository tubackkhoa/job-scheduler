from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, PositiveInt


class ConfigPayload(BaseModel):
    plugin_id: int = Field(..., alias="pluginId")
    session_id: int = Field(..., alias="sessionId")
    config: Optional[dict] = None  # Use correct type if known
    description: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        extra = "forbid"


class DownloadPayload(BaseModel):
    version: str = Field("", description="git+https://github.com/...")

    class Config:
        extra = "forbid"


class PluginCreatePayload(BaseModel):
    package: str
    interval: PositiveInt = Field(60)
    description: Optional[str] = None

    class Config:
        extra = "forbid"


class TemplatePayload(BaseModel):
    template: str = Field("", description="Template string to render")
    params: Dict[str, Any] = Field(..., description="Parameters for the template")

    class Config:
        extra = "forbid"
