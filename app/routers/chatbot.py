import os
import sys
import asyncio
from pathlib import Path
from typing import AsyncIterator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Required for macOS + FAISS
if sys.platform == "darwin":
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings, ChatOllama


# ---------------------------------------------------------
# Load schema + vector store (ONCE)
# ---------------------------------------------------------
def load_schema_docs(path: str) -> list[Document]:
    text = Path(path).read_text(encoding="utf-8")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
    )
    return [Document(page_content=c) for c in splitter.split_text(text)]


SCHEMA_PATH = ".cursorrules"
INDEX_PATH = Path("cache/faiss")

docs = load_schema_docs(SCHEMA_PATH)

embeddings = OllamaEmbeddings(model="nomic-embed-text")

if INDEX_PATH.exists():
    vectorstore = FAISS.load_local(
        str(INDEX_PATH),
        embeddings,
        allow_dangerous_deserialization=True,
    )
else:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(str(INDEX_PATH))

retriever = vectorstore.as_retriever(search_kwargs={"k": 2})


# ---------------------------------------------------------
# Prompts
# ---------------------------------------------------------
generate_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an AI plugin generator for the Job-Scheduler project.\n\n"
            "OUTPUT FORMAT (MANDATORY):\n"
            "=== plugin.yaml ===\n"
            "<raw YAML>\n\n"
            "=== plugin.j2 ===\n"
            "<raw Jinja2>\n\n"
            "RULES:\n"
            "- No markdown\n"
            "- No explanations\n"
            "- No extra text\n"
            "- Use ONLY provided schema context",
        ),
        (
            "human",
            "Schema context:\n{context}\n\nTask:\n{question}",
        ),
    ]
)

edit_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an AI plugin editor.\n\n"
            "Modify ONLY what the instruction requests.\n"
            "Preserve everything else.\n\n"
            "OUTPUT FORMAT:\n"
            "=== plugin.yaml ===\n"
            "<updated YAML>\n\n"
            "=== plugin.j2 ===\n"
            "<updated Jinja2>",
        ),
        (
            "human",
            "Existing plugin:\n{plugin}\n\nInstruction:\n{instruction}",
        ),
    ]
)


# ---------------------------------------------------------
# LLM
# ---------------------------------------------------------
llm = ChatOllama(
    model="qwen2.5-coder:7b",
    temperature=0,
)


# ---------------------------------------------------------
# Request models
# ---------------------------------------------------------
class GenerateRequest(BaseModel):
    query: str


class EditRequest(BaseModel):
    plugin: str
    instruction: str


# ---------------------------------------------------------
# Streaming helper
# ---------------------------------------------------------
async def stream_chain(chain, payload) -> AsyncIterator[str]:
    for chunk in chain.stream(payload):
        token = getattr(chunk, "content", "")
        if token:
            yield token
            await asyncio.sleep(0)


# ---------------------------------------------------------
# HTTP streaming endpoints
# ---------------------------------------------------------
router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/generate")
async def generate(req: GenerateRequest):
    chain = (
        {
            "context": retriever,
            "question": lambda _: req.query,
        }
        | generate_prompt
        | llm
    )

    return StreamingResponse(
        stream_chain(chain, req.query),
        media_type="text/plain",
    )


@router.post("/edit")
async def edit(req: EditRequest):
    chain = edit_prompt | llm

    return StreamingResponse(
        stream_chain(
            chain,
            {"plugin": req.plugin, "instruction": req.instruction},
        ),
        media_type="text/plain",
    )
