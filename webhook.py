"""FastAPI webhook service for WooCommerce data sync + chat API.

Endpoints:
  POST /webhook       — Receive WooCommerce plugin data (code + config)
  POST /chat          — Stateful chat with AI agent (per project)
  POST /docs          — Upload single document (company or project doc)
  POST /docs/bulk     — Bulk upload documents
  GET  /docs          — List documents for a project
  DELETE /docs        — Delete documents by project_id + type
  GET  /health        — Health check

Run:
  uvicorn webhook:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel

import config
from sync.models import BulkDocPayload, DocPayload, WebhookPayload
from sync.structured import clear_project_data, sync_structured_data
from sync.vectors import sync_docs, sync_vector_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# -- Lifespan (startup/shutdown) --------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared clients on startup, close on shutdown."""
    # Validate webhook secret
    if not config.WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET not set — webhook auth disabled!")

    app.state.http_client = httpx.AsyncClient(timeout=60)
    app.state.openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    logger.info("Webhook service started")

    yield

    await app.state.http_client.aclose()
    logger.info("Webhook service stopped")


app = FastAPI(
    title="WooCommerce Sync Webhook",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for WP Admin AJAX calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Chat models & session management ------------------------------------

_PROMPT_FILE = Path(__file__).parent / "prompts" / "system_prompt.md"
_SESSION_TTL = 1800.0  # 30 minutes
_agent_pool = ThreadPoolExecutor(max_workers=4)


class ChatRequest(BaseModel):
    project_id: str
    message: str
    session_id: str = ""


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tools_used: list[str] = []
    usage: dict = {}


class _Session:
    __slots__ = ("project_id", "messages", "created_at", "last_active")

    def __init__(self, project_id: str, messages: list[dict]) -> None:
        self.project_id = project_id
        self.messages = messages
        self.created_at = time.monotonic()
        self.last_active = time.monotonic()


_sessions: dict[str, _Session] = {}


def _cleanup_sessions() -> None:
    """Remove expired sessions."""
    now = time.monotonic()
    expired = [
        sid for sid, s in _sessions.items()
        if now - s.last_active > _SESSION_TTL
    ]
    for sid in expired:
        del _sessions[sid]


def _load_system_prompt(project_id: str) -> str:
    """Load system prompt template with project_id substitution."""
    try:
        template = _PROMPT_FILE.read_text(encoding="utf-8")
        return template.replace("{project_id}", project_id)
    except FileNotFoundError:
        return f"You are a WooCommerce AI assistant for project {project_id}."


def _get_or_create_session(session_id: str, project_id: str) -> _Session:
    """Get existing session or create new one."""
    _cleanup_sessions()

    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        if session.project_id == project_id:
            session.last_active = time.monotonic()
            return session

    # Create new session
    if not session_id:
        session_id = str(uuid.uuid4())

    prompt = _load_system_prompt(project_id)
    messages = [{"role": "system", "content": prompt}]
    session = _Session(project_id=project_id, messages=messages)
    _sessions[session_id] = session
    return session


# -- Auth dependency ---------------------------------------------------

def _extract_secret(
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
) -> str:
    """Extract auth token from either X-Webhook-Secret or Authorization: Bearer header."""
    if x_webhook_secret:
        return x_webhook_secret
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return ""


def _verify_secret(
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
) -> str:
    """Validate webhook secret (timing-safe). Accepts both header formats."""
    if not config.WEBHOOK_SECRET:
        return "no-auth"

    token = _extract_secret(x_webhook_secret, authorization)

    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication header")

    if not hmac.compare_digest(token, config.WEBHOOK_SECRET):
        logger.warning("Invalid webhook secret attempt")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    return token


# -- Routes ------------------------------------------------------------

@app.post("/webhook")
async def webhook_sync(
    payload: WebhookPayload,
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """Receive WooCommerce plugin data and sync to Supabase.

    Two branches run in parallel:
    1. Structured data → clear + upsert 7 tables
    2. Vector data → chunk + extract + context + embed + upsert documents
    """
    _verify_secret(x_webhook_secret, authorization)

    logger.info(
        "Webhook received for project=%s site=%s",
        payload.project_id, payload.site_url,
    )

    http = app.state.http_client
    openai = app.state.openai_client

    # Clear old data first (affects both branches)
    await clear_project_data(http, payload.project_id)

    # Run both branches in parallel
    structured_task = sync_structured_data(http, payload)
    vector_task = sync_vector_data(http, openai, payload)

    pg_count, vec_count = await asyncio.gather(
        structured_task,
        vector_task,
        return_exceptions=False,
    )

    logger.info(
        "Sync complete for %s: %d pg rows, %d vector docs",
        payload.project_id, pg_count, vec_count,
    )

    return {
        "status": "ok",
        "project_id": payload.project_id,
        "structured_rows": pg_count,
        "vector_documents": vec_count,
    }


@app.post("/docs")
async def upload_doc(
    doc: DocPayload,
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """Upload a single document (company or project doc)."""
    _verify_secret(x_webhook_secret, authorization)

    http = app.state.http_client
    openai = app.state.openai_client

    count = await sync_docs(http, openai, [doc])

    return {
        "status": "ok",
        "project_id": doc.project_id,
        "chunks_created": count,
    }


@app.post("/docs/bulk")
async def upload_docs_bulk(
    bulk: BulkDocPayload,
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """Bulk upload documents."""
    _verify_secret(x_webhook_secret, authorization)

    http = app.state.http_client
    openai = app.state.openai_client

    # Apply bulk-level defaults to individual docs
    for doc in bulk.documents:
        if doc.project_id == "_global" and bulk.project_id != "_global":
            doc.project_id = bulk.project_id
        if doc.type == "company_doc" and bulk.type != "company_doc":
            doc.type = bulk.type
        if doc.category == "general" and bulk.category != "general":
            doc.category = bulk.category

    count = await sync_docs(http, openai, bulk.documents)

    return {
        "status": "ok",
        "project_id": bulk.project_id,
        "documents_received": len(bulk.documents),
        "chunks_created": count,
    }


@app.delete("/docs")
async def delete_docs(
    project_id: str,
    doc_type: str | None = None,
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """Delete documents for a project (optionally filter by type)."""
    _verify_secret(x_webhook_secret, authorization)

    http = app.state.http_client
    url = f"{config.SUPABASE_URL}/rest/v1/documents?project_id=eq.{project_id}"
    if doc_type:
        url += f"&type=eq.{doc_type}"

    headers = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
    }
    r = await http.delete(url, headers=headers)
    r.raise_for_status()

    logger.info("Deleted docs for project=%s type=%s", project_id, doc_type or "all")

    return {"status": "ok", "project_id": project_id, "type_filter": doc_type}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """Stateful chat with AI agent for a specific project.

    Manages conversation sessions (30 min TTL).
    Runs the sync agent loop in a thread executor.
    """
    _verify_secret(x_webhook_secret, authorization)

    session = _get_or_create_session(req.session_id, req.project_id)
    session.messages.append({"role": "user", "content": req.message})

    # Find session_id key
    sid = next(
        (k for k, v in _sessions.items() if v is session),
        req.session_id or str(uuid.uuid4()),
    )

    from agent import run_agent
    usage: dict = {}

    # Run sync agent in thread pool with thread-local project_id
    def _run() -> tuple[str, list[str]]:
        config.set_project_id(req.project_id)
        try:
            tools_used: list[str] = []
            full_reply = ""
            for chunk in run_agent(session.messages, usage):
                full_reply += chunk
            # Extract tool names from messages added during this run
            for msg in session.messages:
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        name = tc.get("function", {}).get("name", "")
                        if name and name not in tools_used:
                            tools_used.append(name)
            return full_reply, tools_used
        finally:
            config.clear_project_id()

    loop = asyncio.get_event_loop()
    reply, tools_used = await loop.run_in_executor(_agent_pool, _run)

    return ChatResponse(
        reply=reply,
        session_id=sid,
        tools_used=tools_used,
        usage=usage,
    )


@app.get("/docs")
async def list_docs(
    project_id: str = Query(...),
    doc_type: str | None = Query(default=None, alias="type"),
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """List documents for a project (for admin UI)."""
    _verify_secret(x_webhook_secret, authorization)

    http = app.state.http_client

    # Build Supabase REST query
    url = f"{config.SUPABASE_URL}/rest/v1/documents"
    params = f"project_id=eq.{project_id}&select=id,title,type,category,scope,is_active,synced_at&order=synced_at.desc&limit=100"
    if doc_type:
        params += f"&type=eq.{doc_type}"

    headers = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
    }
    r = await http.get(f"{url}?{params}", headers=headers)
    r.raise_for_status()

    docs = r.json()
    return {
        "documents": docs,
        "count": len(docs),
        "project_id": project_id,
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "service": "woocommerce-sync-webhook",
        "version": "2.0.0",
        "active_sessions": len(_sessions),
    }
