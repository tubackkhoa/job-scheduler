import asyncio
from typing import AsyncIterator
import os
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel


# ---------------------------------------------------------
# Model (Ollama-compatible OpenAI Chat API)
# ---------------------------------------------------------

BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "ollama")

provider = OpenAIProvider(
    base_url=BASE_URL,
    api_key=API_KEY,
)

model = OpenAIChatModel("qwen2.5-coder:7b", provider=provider, settings={"temperature": 0})

# ---------------------------------------------------------
# Agents
# ---------------------------------------------------------

generate_agent = Agent(
    model,
    system_prompt="""
You are an AI plugin generator for the Job-Scheduler project.

OUTPUT FORMAT (MANDATORY):
=== plugin.yaml ===
<raw YAML>

=== plugin.j2 ===
<raw Jinja2>

RULES:
- No markdown
- No explanations
- No extra text
""",
)

edit_agent = Agent(
    model,
    system_prompt="""
You are an AI plugin editor.

Modify ONLY what the instruction requests.
Preserve everything else.

OUTPUT FORMAT:
=== plugin.yaml ===
<updated YAML>

=== plugin.j2 ===
<updated Jinja2>

No markdown.
No explanations.
No extra text.
""",
)


# ---------------------------------------------------------
# Request Models
# ---------------------------------------------------------


class GenerateRequest(BaseModel):
    query: str


class EditRequest(BaseModel):
    plugin: str
    instruction: str


# ---------------------------------------------------------
# Streaming Helpers
# ---------------------------------------------------------


async def stream_agent(
    agent: Agent,
    prompt: str,
) -> AsyncIterator[str]:
    try:
        async with agent.run_stream(prompt) as result:
            async for chunk in result.stream_text(
                delta=True,
            ):
                if chunk:
                    yield chunk
    except asyncio.CancelledError:
        raise


# ---------------------------------------------------------
# FastAPI Router
# ---------------------------------------------------------

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/generate")
async def generate(req: GenerateRequest):
    return StreamingResponse(
        stream_agent(
            generate_agent,
            f"Task:\n{req.query}",
        ),
        media_type="text/event-stream",
    )


@router.post("/edit")
async def edit(req: EditRequest):
    return StreamingResponse(
        stream_agent(
            edit_agent,
            f"Existing plugin:\n{req.plugin}\n\nInstruction:\n{req.instruction}",
        ),
        media_type="text/event-stream",
    )
