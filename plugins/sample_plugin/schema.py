from typing import Any, TypedDict, List, cast


class ModelExpr(TypedDict, total=False):
    list: str
    detail: str
    create: str
    update: str


GridSize = int | bool


class GridSizes(TypedDict, total=False):
    xs: GridSize
    sm: GridSize
    md: GridSize
    lg: GridSize
    xl: GridSize


class SubmitButtonProps(TypedDict, total=False):
    disabled: bool
    className: str


class SubmitButtonOptions(TypedDict, total=False):
    props: SubmitButtonProps
    submitText: str
    norender: bool


class UIOptions(TypedDict, total=False):
    # Common / generic
    title: str
    description: str
    classNames: str
    help: str
    autofocus: bool
    emptyValue: Any

    size: GridSize | GridSizes

    # String widgets
    inputType: str  # e.g. "text", "password", "tel"

    # Date / datetime widgets
    yearsRange: List[int] | tuple[int, int]
    hideNowButton: bool
    hideClearButton: bool

    # Form-level
    submitButtonOptions: SubmitButtonOptions


JSONSchemaForm = TypedDict(
    "JSONSchemaForm",
    {
        "ui:field": str,
        "ui:widget": str,
        "ui:expr": str | tuple[str, *tuple[list[str], ...]],
        "ui:options": UIOptions,
        "binding": List[str],
        "model:expr": ModelExpr,
    },
    total=False,
)


def schema_form(extra: JSONSchemaForm) -> dict:
    return cast(dict, extra)
