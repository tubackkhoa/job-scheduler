from typing import Any, Literal, TypedDict, List, cast


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
    "JobDetai",
]

UIField = Literal["MLThresholdsTable", "MultiSelect", "Template", "Version", "Select"]


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
        "ui:expr": str | tuple[str, *tuple[list[str], ...]],  # expression with memo support
        "ui:options": dict,  # standard ui:options for json_schema_form, mean other ui:option should be placed in here
        "model:binding": List[str],  # for binding element with path
        "model:deps": List[str],  # dependency field paths to inject into context
        "model:expr": ModelExpr,  # for rendering component with CRUD operations
    },
    total=False,
)


def ui_schema(extra: JSONUISchema) -> dict:
    return cast(dict, extra)


def ui_schema_crud(
    field_path: list[str],
    crud_exprs: dict[str, str] | None = None,
    deps: list[str] | None = None,
    ui_options: dict | None = None,
) -> dict:
    """
    Generic CRUD field schema helper with full expression flexibility.

    Args:
        field_path: Path to the value field (e.g., ["model_type"])
        crud_exprs: Dict of operation -> jinja expression. Keys: list, detail, create, update, delete
                   Example: {"list": "j`{{ my_list_func('${field_id}') | tojson }}`"}
        deps: List of dependency field paths to inject into context (e.g., ["api_url", "api_key"])
        ui_options: Additional UI options (size, etc.)

    Usage:
        model_type_id: int = Field(
            0,
            json_schema_extra=ui_schema_crud(
                field_path=["model_type"],
                crud_exprs={
                    "list": "j`{{ list_model_types('${field_id}', '${search}', ${api_url}) | tojson }}`",
                    "create": "j`{{ sync_model_types(${api_url}, ${api_key}) | tojson }}`",
                },
                deps=["api_url", "api_key"],
            ),
        )
    """
    default_exprs = {
        "list": "j`{{ get_value_versions('${field_id}', '${search}', ${limit}, ${offset}) | tojson }}`",
        "detail": "j`{{ get_value_version(${id}) | tojson }}`",
        "create": "j`{{ create_value_version(${payload}) | tojson }}`",
        "update": "j`{{ update_value_version(${id}, ${payload}) | tojson }}`",
        "delete": "j`{{ delete_value_version(${id}) | tojson }}`",
    }

    model_expr = {**default_exprs, **(crud_exprs or {})}

    schema: dict = {
        "ui:field": "Crud",
        "model:binding": field_path,
        "model:expr": model_expr,
        "ui:options": {"size": 12, **(ui_options or {})},
    }

    if deps:
        schema["model:deps"] = deps

    return ui_schema(cast(JSONUISchema, schema))
