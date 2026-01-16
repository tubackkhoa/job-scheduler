from typing import Any, Literal, TypedDict, List, cast, Optional
from pydantic import Field, ConfigDict, BaseModel

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

    model_config = ConfigDict(extra="forbid")
    __slots__ = ("_ctx",)

    # ---------------------
    # Internal helpers
    # ---------------------

    @classmethod
    def _extra(cls, field) -> dict:
        return field.json_schema_extra or {}

    @classmethod
    def _read_perm(cls, field, ctx: ExecutionContext) -> str | None:
        perm = cls._extra(field).get("read")
        return perm and f"{ctx.package}.{perm}"

    @classmethod
    def _write_perm(cls, field, ctx: ExecutionContext) -> str | None:
        perm = cls._extra(field).get("write")
        return perm and f"{ctx.package}.{perm}"

    @staticmethod
    def _allowed(perm: str, ctx: ExecutionContext) -> bool:
        return ctx.is_admin() or ctx.allowed(perm)

    def _get_ctx(self):
        return getattr(self, "_ctx", None)

    # ---------------------
    # Secure attribute access
    # ---------------------

    def __getattribute__(self, name: str):
        if name.startswith("_"):
            return super().__getattribute__(name)

        value = super().__getattribute__(name)
        fields = super().__getattribute__("model_fields")

        if name in fields:
            ctx = self._get_ctx()
            if ctx is not None:
                field = fields[name]
                perm = self._read_perm(field, ctx)
                if perm and not self._allowed(perm, ctx):
                    raise PermissionError(f"Read denied for field '{name}'")

        return value

    # ---------------------
    # Secure dumping
    # ---------------------

    def model_dump(self, **kwargs) -> dict[str, Any]:
        ctx: ExecutionContext = self._get_ctx()
        if ctx is None:
            return super().model_dump(**kwargs)

        allowed = set()

        for name, field in self.model_fields.items():
            extra = field.json_schema_extra

            # ⬅️ Not a SecureField → always include
            if not extra:
                allowed.add(name)
                continue

            # ⬅️ SecureField → enforce read permission
            perm = extra.get("read") and f"{ctx.package}.{perm}"
            if perm is None or self._allowed(perm, ctx):
                allowed.add(name)

        include = kwargs.pop("include", None)
        if include is not None:
            allowed &= set(include)

        return super().model_dump(include=allowed, **kwargs)

    # model_dump_json automatically inherits model_dump
    # ---------------------

    # ---------------------
    # Secure schema (explicit ctx)
    # ---------------------

    @classmethod
    def model_json_schema(cls, **kwargs):
        ctx: ExecutionContext = kwargs.pop("ctx", None)
        schema = super().model_json_schema(**kwargs)

        if ctx is None:
            return schema

        properties = {}

        for name, prop in schema.get("properties", {}).items():
            field = cls.model_fields.get(name)
            if field is None:
                continue

            extra = field.json_schema_extra

            # ⬅️ Not a SecureField → always include
            if not extra:
                properties[name] = prop
                continue

            perm = cls._read_perm(field, ctx)
            if perm is None or cls._allowed(perm, ctx):
                properties[name] = prop

        schema["properties"] = properties
        return schema

    # ---------------------
    # Secure validation (ctx injection point)
    # ---------------------

    @classmethod
    def model_validate_secure(cls, data: Any, ctx):
        # Enforce write permissions first
        for field in cls.model_fields.values():
            if perm := cls._write_perm(field, ctx):
                ctx.require(perm)

        instance = cls.model_validate(data)

        # ⬅️ ctx is attached HERE (instance-scoped)
        object.__setattr__(instance, "_ctx", ctx)

        return instance
