from typing import TypedDict, List, cast


class ModelExpr(TypedDict, total=False):
    list: str
    detail: str
    create: str
    update: str


JSONUISchema = TypedDict(
    "JSONUISchema",
    {
        "ui:field": str,
        "ui:widget": str,
        "ui:meta": dict,
        "ui:expr": str | tuple[str, *tuple[list[str], ...]],
        "ui:options": dict,
        "model:binding": List[str],
        "model:expr": ModelExpr,
    },
    total=False,
)


def ui_schema(extra: JSONUISchema) -> dict:
    return cast(dict, extra)
