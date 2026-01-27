import os
from pathlib import Path

# Required for macOS + FAISS
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings, ChatOllama


# 1) Load schema docs
def load_schema_docs(path: str) -> list[Document]:
    text = Path(path).read_text(encoding="utf-8")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
    )
    return [Document(page_content=c) for c in splitter.split_text(text)]


SCHEMA_PATH = ".cursorrules"
INDEX_PATH = "cache/faiss"

docs = load_schema_docs(SCHEMA_PATH)

# 2) Vector store (with persistence)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

if Path(INDEX_PATH).exists():
    vectorstore = FAISS.load_local(
        INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )
else:
    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(INDEX_PATH)

retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# 3) Prompt (unchanged, but works better now)
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior backend engineer generating DECLARATIVE PLUGINS "
            "for the Job-Scheduler project.\n\n"
            "PLUGIN FORMAT (STRICT):\n"
            "- Output MUST define a plugin as a FOLDER with EXACTLY two files:\n"
            "  1) plugin.yaml\n"
            "  2) plugin.j2\n"
            "- NO Python code.\n"
            "- NO Pluggy hooks.\n"
            "- NO extra files.\n\n"
            "plugin.yaml RULES:\n"
            "- Must be valid YAML.\n"
            "- Must define: name, version, description, roles, schema, env.\n"
            "- Schema must follow JSON Schema style with UI extensions.\n"
            "- Preserve ui:* , model:* , and code blocks exactly as YAML literals.\n\n"
            "plugin.j2 RULES:\n"
            "- Must be valid Jinja2.\n"
            "- May reference config fields and ctx (ctx.user.id, ctx.now).\n"
            "- Must render structured JSON output.\n"
            "- Do NOT include HTML.\n\n"
            "CONSTRAINTS:\n"
            "- Use ONLY the provided schema context.\n"
            "- Do NOT invent APIs, helpers, or dependencies.\n"
            "- Follow security best practices (no secrets hardcoded beyond defaults).\n\n"
            "OUTPUT FORMAT (MANDATORY):\n"
            "plugins/<plugin_name>@<version>/\n"
            "├── plugin.yaml\n"
            "└── plugin.j2\n\n"
            "Output MUST be plain text, no explanations, no markdown fences.",
        ),
        (
            "human",
            "Schema context:\n{context}\n\n" "Task: {question}",
        ),
    ]
)


# 4) LLM (RECOMMENDED for M1)
llm = ChatOllama(
    model="qwen2.5-coder:14b",
    temperature=0,
)

# 5) LCEL RAG chain
rag_chain = (
    {
        "context": retriever,
        "question": lambda x: x,
    }
    | prompt
    | llm
    | StrOutputParser()
)

# 6) Run with streaming (correct way)
query = (
    "Generate a plugin named hello_plugin version 1.\n"
    "The plugin should define a configuration schema with:\n"
    "- webhook_url (string)\n"
    "- webhook_api_key (string, password widget)\n"
    "- env (enum: staging, production, uat)\n"
    "- model_type (dynamic UI field with model bindings)\n"
    "Include roles for user and admin.\n"
    "Render runtime output as JSON with all config fields included.\n"
)

for chunk in rag_chain.stream(query):
    print(chunk, end="", flush=True)
