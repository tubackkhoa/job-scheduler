from typing import Any, Literal, TypedDict, List, cast, Optional
from pydantic import Field, BaseModel, PrivateAttr
from enforcer import ExecutionContext

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


def SecureField(
    default: Any = None,
    *,
    read: str,
    write: Optional[str] = None,
    **kwargs,
):
    extra = kwargs.pop("json_schema_extra", {}) or {}

    extra.update(
        {
            "read": read,
            "write": write,
        }
    )

    return Field(
        default=default,
        json_schema_extra=extra,
        **kwargs,
    )


class SecureBaseModel(BaseModel):
    """
    SECURITY CONTRACT

    - ctx is stored ONLY on the instance
    - instances MUST be request-scoped
    - schema NEVER reads instance state
    """

    _ctx: Optional[ExecutionContext] = PrivateAttr(default=None)

    # ---------------------
    # Secure attribute access
    # ---------------------

    def __getattr__(self, name: str):
        value = super().__getattribute__(name)

        ctx = getattr(self, "_ctx", None)
        if ctx is None:
            return value

        field = self.model_fields.get(name)
        if field is None:
            return value

        extra = field.json_schema_extra
        if not extra:
            return value

        perm_key = extra.get("read")
        if perm_key and not ctx.is_admin() and not ctx.allowed(f"{ctx.package}.{perm_key}"):
            raise PermissionError(f"Read denied for field '{name}'")

        return value

    # ---------------------
    # Secure dumping
    # ---------------------

    def model_dump(self, **kwargs) -> dict[str, Any]:
        ctx = getattr(self, "_ctx", None)
        if ctx is None:
            return super().model_dump(**kwargs)

        allowed: set[str] = set()
        is_admin = ctx.is_admin()

        for name, field in self.model_fields.items():
            extra = field.json_schema_extra

            # ⬅️ Not a SecureField → always include
            if not extra:
                allowed.add(name)
                continue

            perm_key = extra.get("read")
            if perm_key and not is_admin and not ctx.allowed(f"{ctx.package}.{perm_key}"):
                continue

            allowed.add(name)

        include = kwargs.pop("include", None)
        if include is not None:
            allowed &= set(include)

        return super().model_dump(include=allowed, **kwargs)

    # ---------------------
    # Secure schema (explicit ctx)
    # ---------------------

    @staticmethod
    def bind_ctx(instance: BaseModel, ctx: ExecutionContext):
        object.__setattr__(instance, "_ctx", ctx)

    @classmethod
    def model_json_schema(
        cls,
        ctx: ExecutionContext,
        **kwargs,
    ) -> dict[str, Any]:
        # Base schema from Pydantic
        schema = super().model_json_schema(**kwargs)

        if ctx is None:
            return schema

        properties: dict[str, Any] = {}
        is_admin = ctx.is_admin()

        for name, prop in schema.get("properties", {}).items():
            field = cls.model_fields.get(name)
            if field is None:
                continue

            extra = field.json_schema_extra
            if not extra:
                properties[name] = prop
                continue

            perm_key = extra.get("read")
            if perm_key and not is_admin and not ctx.allowed(f"{ctx.package}.{perm_key}"):
                continue

            properties[name] = prop

        schema["properties"] = properties
        return schema

    # ---------------------
    # Secure validation (ctx injection point)
    # ---------------------

    @classmethod
    def model_validate(
        cls,
        obj: Any,
        ctx: ExecutionContext,
        **kwargs,
    ):
        if ctx is None:
            return super().model_validate(obj, **kwargs)

        # Enforce write permissions
        if isinstance(obj, dict):
            is_admin = ctx.is_admin()
            for name, field in cls.model_fields.items():
                if name in obj:
                    extra = field.json_schema_extra
                    if not extra:
                        continue
                    perm_key = extra.get("write")
                    if perm_key and not is_admin:
                        ctx.require(f"{ctx.package}.{perm_key}")

        # Delegate to Pydantic
        instance = super().model_validate(obj, **kwargs)

        # Attach ctx (instance-scoped)
        cls.bind_ctx(instance, ctx)
        return instance
