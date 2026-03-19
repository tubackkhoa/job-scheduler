import logging
from typing import Any, Callable, Optional, Dict
import pluggy
from pydantic import BaseModel, ConfigDict, Field
from plugins.blog.dao import create_post, get_post, delete_post, get_posts, update_post
from plugins.schema import ui_schema
from schemas import settings
from .models import init_db

hookimpl = pluggy.HookimplMarker("job-scheduler")


class CrawlConfig(BaseModel):
    url: str = Field(
        "",
        description="web page",
        json_schema_extra=ui_schema({"ui:options": {"size": 12}}),
    )
    extractor: str = Field(
        "",
        description="js extractor",
        json_schema_extra=ui_schema(
            {"ui:field": "Template", "type": "js", "ui:options": {"size": 12, "preview": False}}
        ),
    )


class Config(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=ui_schema(
            {
                "url": (
                    "blog/Portal.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/portal.js"
                ),
            }
        )
    )

    cdp_url: str = Field(
        "http://localhost:9222",
        description="run: chrome --headless=new --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-fast-profile --disable-gpu --no-sandbox --disable-dev-shm-usage --disable-extensions --disable-background-networking --disable-background-timer-throttling --disable-renderer-backgrounding --disable-sync --disable-translate --disable-infobars --mute-audio --no-first-run --blink-settings=imagesEnabled=false",
        json_schema_extra=ui_schema({"ui:options": {"size": 12}}),
    )

    crawls: list[CrawlConfig] = Field(
        [],
        json_schema_extra=ui_schema({"ui:options": {"size": 12}}),
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
            {
                "url": (
                    "blog/Dashboard.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/dashboard.js"
                )
            },
        ),
        (
            "blog",
            {
                "url": (
                    "blog/Home.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/home.js"
                )
            },
        ),
        (
            "blog/:blog_id",
            {
                "url": (
                    "blog/Blog.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/blog.js"
                )
            },
        ),
    ]

    @classmethod
    @hookimpl
    def routes(cls) -> list[tuple[str, Any]]:
        # using function so that it will delete memory because page can be huge
        return cls._routes

    @classmethod
    @hookimpl
    async def install(cls) -> bool:
        await init_db()
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
        return Config.model_validate(json or {}, context={"validate": validate})

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
        from playwright.async_api import async_playwright
        import asyncio

        semaphore = asyncio.Semaphore(5)

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(config.cdp_url)

            async def scrape_page(url: str, js_extract: str):
                async with semaphore:
                    context = await browser.new_context()
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                    data = await page.evaluate("(code) => new Function(code)()", js_extract)
                    await context.close()
                    return {"url": url, "data": data}

            # Run tasks in parallel
            tasks = [scrape_page(crawl.url, crawl.extractor) for crawl in config.crawls]
            results = await asyncio.gather(*tasks, return_exceptions=False)

            for result in results:
                print(f"\nURL: {result['url']}")
                for item in result["data"]:
                    print(item)

        return True
