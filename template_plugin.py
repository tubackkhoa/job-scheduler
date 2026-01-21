from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, create_model
import yaml


from auth import User
from enforcer import ExecutionContext
from renderer import Renderer


class TemplatePlugin:
    def __init__(self, plugin_dir: str):
        self.plugin_dir = plugin_dir

        with open(f"{plugin_dir}/plugin.yaml") as f:
            self.meta = yaml.safe_load(f)
        with open(f"{plugin_dir}/plugin.j2") as f:
            self.template_str = f.read()
        print(self.meta, self.template_str)

    # ---------------- PluginSpec ----------------

    def env(self):
        return self.meta.get("env", {})

    def schema(self, ctx: ExecutionContext):
        return self.meta["schema"]

    @property
    def description(self):
        return self.meta["description"]

    def config(
        self,
        ctx: ExecutionContext,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ) -> BaseModel:
        schema = self.meta["schema"]

        fields = {
            k: (str, schema["properties"][k].get("default", ...)) for k in schema["properties"]
        }

        Model = create_model("Config", **fields)  # type: ignore
        return Model(**(json or {}))

    def run(self, ctx: ExecutionContext, config: BaseModel):
        rendered = Renderer.render(ctx, self.template_str, config.model_dump(), **self.env())
        return rendered

    def roles(self):
        return self.meta.get("roles", {})

    def save(
        self,
        ctx: ExecutionContext,
        description: Optional[str] = None,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ) -> None:
        """
        Persist config values as schema defaults and optionally update description.
        """
        config = self.config(ctx, json, validate)
        schema = self.meta.setdefault("schema", {})
        properties = schema.setdefault("properties", {})

        # Write config values back as defaults
        for field, value in config.model_dump().items():
            if field not in properties:
                continue

            properties[field]["default"] = value

        # Update description if provided
        if description is not None:
            self.meta["description"] = description

        # Persist to disk
        plugin_yaml = Path(self.plugin_dir) / "plugin.yaml"
        with plugin_yaml.open("w") as f:
            yaml.safe_dump(self.meta, f, sort_keys=False)

    async def install(self):
        return True

    async def uninstall(self):
        return True
