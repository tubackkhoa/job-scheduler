from typing import Any, TypedDict, List, cast


class ModelExpr(TypedDict, total=False):
    list: str
    detail: str
    create: str
    update: str


JSONUISchema = TypedDict(
    "JSONUISchema",
    {
        "type": str,
        "enum": list[Any],
        "default": Any,  # default value for uiSchema
        "ui:field": str,  # for render field
        "ui:widget": str,  # for render widget
        "ui:expr": str | tuple[str, *tuple[list[str], ...]],  # expression with memo support
        "ui:options": dict,  # standard ui:options for json_schema_form, mean other ui:option should be placed in here
        "model:binding": List[str],  # for binding element with path
        "model:expr": ModelExpr,  # for rendering component with list, detail and update, create data
    },
    total=False,
)


def ui_schema(extra: JSONUISchema) -> dict:
    return cast(dict, extra)
