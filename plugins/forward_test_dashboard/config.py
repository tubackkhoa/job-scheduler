from pydantic import BaseModel, ConfigDict, Field
from plugins import ui_schema
from pathlib import Path


class Config(BaseModel):

    model_config = ConfigDict(json_schema_extra=ui_schema({"url": "forwardtest/Portal.tsx"}))

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
                "url": "PnlPreview.tsx",
                # "code": Path(__file__).with_name("pnl_preview.js").read_text(),
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
            # {"ui:field": "Template", "type": "markdown", "url": "TableMarkdown.tsx"}
            {
                "ui:field": "Template",
                "type": "markdown",
                "code": Path(__file__).with_name("signal_comparison.js").read_text(),
            }
        ),
    )
