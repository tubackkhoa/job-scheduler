from pydantic import BaseModel, Field
from plugins import ui_schema
from pathlib import Path
from typing import Optional


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

class Config(BaseModel):
    model_type: str = Field(
        "",
        title="Model Type",
        json_schema_extra=ui_schema_crud(
            field_code=Path(__file__).with_name("crud.js").read_text(),
            # field_url="CrudField.tsx",
            field_path=["model_type"],
            crud_exprs={
                "create": "{{ register(payload) }}",
                "list": "",
            },
            ui_options={
                "createSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "title": "Key"},
                        "name": {"type": "string", "title": "Name"}
                    },
                    "required": ["key", "name"],
                }
            },
        ),
    )

    pnl_preview: str = Field(
        "",
        title="PNL Dashboard",
        json_schema_extra=ui_schema({"ui:field": "Template", "type": "markdown", "code": Path(__file__).with_name("pnl_preview.js").read_text()}),
    )

    signal_keyword: str = Field(
        "ranking table ::::",
        title="Signal Keyword",
        json_schema_extra=ui_schema({"ui:options": {"size": 4}}),
    )

    signal_preview: str = Field(
        "",
        title="Signal Comparison",
        json_schema_extra=ui_schema({"ui:field": "Template", "type": "markdown"}),
    )

