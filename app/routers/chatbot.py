import os
from typing import AsyncIterator, List, get_origin, get_args, Union
import inspect
import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel

from app.deps import PluginManagerState
from plugin_manager import PluginManager


# ---------------------------------------------------------
# MODEL
# ---------------------------------------------------------

BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
MODEL_NAME = os.getenv("OPENAI_MODEL", "qwen2.5-coder:7b")

provider = OpenAIProvider(
    base_url=BASE_URL,
    api_key=API_KEY,
)

model = OpenAIChatModel(
    MODEL_NAME,
    provider=provider,
)


# ---------------------------------------------------------
# AGENT
# ---------------------------------------------------------

SYSTEM_PROMPT = """
You are given:

ENV GLOBALS
Functions and variables that can be used inside the template.

CHAT HISTORY
Previous conversation messages.

Return ONLY valid Jinja2 template code.

"""

agent = Agent(
    model,
    system_prompt=SYSTEM_PROMPT,
)


# ---------------------------------------------------------
# REQUEST MODEL
# ---------------------------------------------------------


class ChatRequest(BaseModel):
    package: str
    message: str
    history: List[str] | None = None


# ---------------------------------------------------------
# CONTEXT BUILDER
# ---------------------------------------------------------


def type_to_str(t):
    """Convert python type annotation to readable string."""
    if t is inspect._empty:
        return "any"

    origin = get_origin(t)

    if origin is Union:
        args = [a for a in get_args(t) if a is not type(None)]
        if args:
            return type_to_str(args[0])

    if hasattr(t, "__name__"):
        return t.__name__

    return str(t)


def describe_item(name, obj):
    # Function / callable
    if callable(obj):
        try:
            sig = inspect.signature(obj)
            params = {}

            for p_name, p in sig.parameters.items():
                params[p_name] = {
                    "type": type_to_str(p.annotation),
                    "required": p.default is inspect._empty,
                }

            return {
                "name": name,
                "type": "function",
                "description": inspect.getdoc(obj) or "",
                "parameters": params,
            }

        except (ValueError, TypeError):
            # Some callables don't support signature()
            return {
                "name": name,
                "type": "function",
                "description": inspect.getdoc(obj) or "",
                "parameters": {},
            }

    # Variable / constant
    return {
        "name": name,
        "type": "variable",
        "value_type": type(obj).__name__,
        "value": repr(obj),
    }


def generate_globals_info(env):
    items = [describe_item(name, obj) for name, obj in env.items()]

    return yaml.safe_dump({"ENV GLOBALS": items}, sort_keys=False, allow_unicode=True)


def build_context(plugin_manager: PluginManager, package: str, history: List[str]):

    plugin = plugin_manager.get_plugin_instance(package)

    if not plugin:
        raise HTTPException(404, "plugin not found")

    return "\n".join(
        (
            generate_globals_info(plugin.env()),
            "CHAT HISTORY:",
            *history,
        )
    )


# ---------------------------------------------------------
# STREAM
# ---------------------------------------------------------


async def stream_agent(prompt: str, request: Request) -> AsyncIterator[str]:
    async with agent.run_stream(prompt) as result:
        async for chunk in result.stream_text(delta=True):
            if await request.is_disconnected():
                break
            if chunk:
                yield chunk


# ---------------------------------------------------------
# ROUTER
# ---------------------------------------------------------

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/chat")
async def chat(
    req: ChatRequest,
    request: Request,
    plugin_manager: PluginManagerState,
):
    # max 5 items
    history = (req.history or [])[-5:]
    context = build_context(
        plugin_manager,
        req.package,
        history,
    )

    prompt = f"{context}\nUSER MESSAGE:{req.message}"

    return StreamingResponse(
        stream_agent(prompt, request),
        media_type="text/event-stream",
        headers={"X-Model-Name": MODEL_NAME},
    )
