from pydantic import BaseModel, ConfigDict, Field
from plugins import ui_schema
from schemas import settings


class Config(BaseModel):

    model_config = ConfigDict(
        json_schema_extra=ui_schema(
            {
                "url": (
                    "forwardtest/Portal.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/portal.js"
                )
            }
        )
    )

    webhook_url: str = Field(
        "https://api-quantsigengine-uat.orai.network",
        title="API URL",
        json_schema_extra=ui_schema({"ui:options": {"size": 6}}),
    )
    webhook_api_key: str = Field(
        "",
        title="API Key",
        json_schema_extra=ui_schema({"ui:widget": "password", "ui:options": {"size": 6}}),
    )

    pnl_preview: str = Field(
        "",
        title="PNL Dashboard",
        json_schema_extra=ui_schema(
            {
                "ui:field": "Template",
                "type": "markdown",
                "url": (
                    "forwardtest/PnlPreview.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/pnl_preview.js"
                ),
            }
        ),
    )

    signal_keyword: str = Field(
        "ranking table ::::",
        title="Signal Keyword",
        json_schema_extra=ui_schema({"ui:options": {"size": 4}}),
    )

    signal_preview: str = Field(
        "",
        title="Signal Comparison",
        json_schema_extra=ui_schema(
            {
                "ui:field": "Template",
                "type": "markdown",
                "url": (
                    "TableMarkdown.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/signal_comparison.js"
                ),
            }
        ),
    )
