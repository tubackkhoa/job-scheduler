import os
from typing import Any, AsyncIterator, Dict, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel

from app.deps import PluginManagerState
from plugin_manager import PluginManager
from renderer import describe_callable


# ---------------------------------------------------------
# MODEL
# ---------------------------------------------------------

BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "ollama")

provider = OpenAIProvider(
    base_url=BASE_URL,
    api_key=API_KEY,
)

model = OpenAIChatModel(
    "qwen2.5-coder:7b",
    provider=provider,
    settings={"temperature": 0},
)


# ---------------------------------------------------------
# AGENT
# ---------------------------------------------------------

SYSTEM_PROMPT = """
You generate Jinja2 template code.

You are given:
- ENV GLOBALS: available functions and variables
- CHAT HISTORY: previous conversation

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


def build_context(plugin_manager: PluginManager, package: str, history: List[str]):

    plugin = plugin_manager.get_plugin_instance(package)

    if not plugin:
        raise Exception("plugin not found")

    env = plugin.env()
    globals_info = "\n".join(f"{name}: {describe_callable(func)}" for name, func in env.items())
    history_text = "\n".join(history)
    return f"""
ENV GLOBALS:
{globals_info}

CHAT HISTORY:
{history_text}
"""


# ---------------------------------------------------------
# STREAM
# ---------------------------------------------------------


async def stream_agent(prompt: str) -> AsyncIterator[str]:
    async with agent.run_stream(prompt) as result:
        async for chunk in result.stream_text(delta=True):
            if chunk:
                yield chunk


# ---------------------------------------------------------
# ROUTER
# ---------------------------------------------------------

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/chat")
async def chat(
    req: ChatRequest,
    plugin_manager: PluginManagerState,
):
    # max 5 items
    history = (req.history or [])[-5:]
    context = build_context(
        plugin_manager,
        req.package,
        history,
    )

    prompt = f"""
{context}
USER MESSAGE:
{req.message}
"""

    return StreamingResponse(
        stream_agent(prompt),
        media_type="text/event-stream",
        headers={"X-Model-Name": model.model_name},
    )
