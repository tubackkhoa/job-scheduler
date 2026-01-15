from typing import Any, Literal, TypedDict, List, cast, Optional


UIWidget = Literal[
    "datetime",
    "text",
    "textarea",
    "password",
    "email",
    "uri",
    "date",
    "updown",
    "range",
    "checkbox",
    "hidden",
    "radio",
    "select",
    "checkboxes",
    "files",
]

UIField = Literal["MLThresholdsTable", "Template", "Version", "Select", "Dynamic"]


class ModelExpr(TypedDict, total=False):
    list: str
    detail: str
    create: str
    update: str
    apply: str
    delete: str


JSONUISchema = TypedDict(
    "JSONUISchema",
    {
        "type": Literal["string", "number", "sql", "markdown", "js", "yaml", "yml", "json"],
        "enum": list[Any],
        "default": Any,  # default value for uiSchema
        "ui:field": UIField,  # for render field
        "ui:widget": UIWidget,  # for render widget
        "ui:expr": str | tuple[str, list[str]],  # expression with memo support
        "ui:options": dict,  # standard ui:options for json_schema_form, mean other ui:option should be placed in here
        "model:binding": List[str],  # for binding element with path
        "model:deps": List[str],  # dependency field paths to inject into context
        "model:expr": ModelExpr,  # for rendering component with CRUD operations
    },
    total=False,
)


def ui_schema(extra: JSONUISchema) -> dict:
    return cast(dict, extra)
