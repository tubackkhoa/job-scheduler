import logging
from pathlib import Path
from typing import Any, Callable, Optional, Dict
import pluggy
from pydantic import BaseModel, ConfigDict
from plugins.blog.dao import create_post, get_post, delete_post, get_posts, update_post
from plugins.schema import ui_schema
from schemas import settings

hookimpl = pluggy.HookimplMarker("job-scheduler")


class Config(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=ui_schema(
            {
                **(
                    {"url": "blog/Portal.tsx"}
                    if settings.env == "dev"
                    else {"url": "/assets/{package}/portal.js"}
                ),
            }
        )
    )


class Plugin:
    _env = {
        "get_posts": get_posts,
        "create_post": create_post,
        "update_post": update_post,
        "get_post": get_post,
        "delete_post": delete_post,
    }
    _routes: list[tuple[str, Any]] = [
        # empty route will be use as portal
        ("", Config.model_config.get("json_schema_extra")),
        (
            "dashboard",
            (
                {"url": "blog/Dashboard.tsx"}
                if settings.env == "dev"
                else {"url": "/assets/{package}/dashboard.js"}
            ),
        ),
        (
            "blog",
            (
                {"url": "blog/Home.tsx"}
                if settings.env == "dev"
                else {"url": "/assets/{package}/home.js"}
            ),
        ),
        (
            "blog/:blog_id",
            (
                {"url": "blog/Blog.tsx"}
                if settings.env == "dev"
                else {"url": "/assets/{package}/blog.js"}
            ),
        ),
    ]

    @classmethod
    @hookimpl
    def routes(cls) -> list[tuple[str, Any]]:
        # using function so that it will delete memory because page can be huge
        return cls._routes

    @classmethod
    @hookimpl
    def install(cls) -> bool:
        return True

    @classmethod
    @hookimpl
    def env(cls) -> Dict[str, Any]:
        return cls._env

    @classmethod
    @hookimpl
    def schema(cls, ctx):
        return Config.model_json_schema()

    @classmethod
    @hookimpl
    def config(
        cls,
        ctx,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ):

        return Config.model_validate(json or {})

    @classmethod
    @hookimpl
    def roles(cls):
        return {}

    @classmethod
    @hookimpl
    async def run(
        cls,
        ctx,
        config: Config,
        logger: logging.Logger,
        render: Callable,
    ):

        return True
