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
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

import config
from sync.models import BulkDocPayload, DocPayload, WebhookPayload
from sync.structured import clear_project_data, generate_project_summary, sync_structured_data
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

    # Proactive session cleanup every 5 minutes
    async def _session_cleanup_loop() -> None:
        while True:
            await asyncio.sleep(300)
            _cleanup_sessions()
            logger.debug("Session cleanup: %d active sessions", len(_sessions))

    cleanup_task = asyncio.create_task(_session_cleanup_loop())
    logger.info("Webhook service started (agent workers=%d)", _AGENT_WORKERS)

    yield

    cleanup_task.cancel()

    await app.state.http_client.aclose()
    logger.info("Webhook service stopped")


app = FastAPI(
    title="WooCommerce Sync Webhook",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api-docs",
    redoc_url=None,
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
_AGENT_WORKERS = int(os.getenv("AGENT_WORKERS", "12"))
_agent_pool = ThreadPoolExecutor(max_workers=_AGENT_WORKERS)


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


def _load_system_prompt() -> str:
    """Load static system prompt (cacheable by OpenAI — no variable substitution)."""
    try:
        return _PROMPT_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "You are a WooCommerce AI assistant."


async def _fetch_project_summary(project_id: str) -> str:
    """Fetch project summary_text from Supabase."""
    try:
        http = app.state.http_client
        url = f"{config.SUPABASE_URL}/rest/v1/projects?project_id=eq.{project_id}&select=summary_text"
        headers = {
            "apikey": config.SUPABASE_KEY,
            "Authorization": f"Bearer {config.SUPABASE_KEY}",
        }
        r = await http.get(url, headers=headers)
        r.raise_for_status()
        rows = r.json()
        if rows and rows[0].get("summary_text"):
            return rows[0]["summary_text"]
    except Exception:
        pass
    return ""


async def _get_or_create_session(session_id: str, project_id: str) -> tuple[_Session, str]:
    """Get existing session or create new one. Returns (session, session_id)."""
    _cleanup_sessions()

    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        if session.project_id == project_id:
            session.last_active = time.monotonic()
            return session, session_id
        logger.warning("Session %s project mismatch (%s != %s), creating new",
                        session_id, session.project_id, project_id)

    # Create new session
    new_id = session_id if session_id and session_id not in _sessions else str(uuid.uuid4())

    prompt = _load_system_prompt()

    # Inject project summary into system prompt (eliminates get_shop_config calls)
    summary = await _fetch_project_summary(project_id)
    if summary:
        prompt += f"\n\n## SHOP CONTEXT (auto-injected)\n{summary}"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"[Project: {project_id}]"},
    ]
    session = _Session(project_id=project_id, messages=messages)
    _sessions[new_id] = session
    return session, new_id


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

    # Generate project summary after sync
    await generate_project_summary(http, payload.project_id)

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

    session, sid = await _get_or_create_session(req.session_id, req.project_id)
    session.messages.append({"role": "user", "content": req.message})

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
    params = f"project_id=eq.{project_id}&select=id,title,type,category,scope,is_active,synced_at&order=synced_at.desc&limit=500"
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


@app.get("/docs/{doc_id}")
async def get_doc(
    doc_id: str,
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """Get a single document by ID (includes full text content)."""
    _verify_secret(x_webhook_secret, authorization)

    http = app.state.http_client
    url = f"{config.SUPABASE_URL}/rest/v1/documents"
    params = f"id=eq.{doc_id}&select=id,title,text,type,category,scope,project_id,is_active,synced_at"

    headers = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
    }
    r = await http.get(f"{url}?{params}", headers=headers)
    r.raise_for_status()

    docs = r.json()
    if not docs:
        raise HTTPException(status_code=404, detail="Document not found")

    return docs[0]


@app.get("/api/projects")
async def list_projects(
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """List all projects for admin dashboard."""
    _verify_secret(x_webhook_secret, authorization)

    http = app.state.http_client
    url = f"{config.SUPABASE_URL}/rest/v1/projects"
    params = "select=project_id,site_url,wp_version,wc_version,php_version,theme_name,active_plugins_count,last_sync&order=last_sync.desc"
    headers = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
    }
    r = await http.get(f"{url}?{params}", headers=headers)
    r.raise_for_status()

    return {"projects": r.json()}


@app.delete("/docs/{doc_id}")
async def delete_single_doc(
    doc_id: str,
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """Delete a single document by ID."""
    _verify_secret(x_webhook_secret, authorization)

    http = app.state.http_client
    url = f"{config.SUPABASE_URL}/rest/v1/documents?id=eq.{doc_id}"
    headers = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
        "Prefer": "return=minimal",
    }
    r = await http.delete(url, headers=headers)
    r.raise_for_status()

    return {"status": "ok", "deleted_id": doc_id}


@app.post("/api/re-ingest")
async def re_ingest_docs(
    project_id: str = Query(default="_global"),
    x_webhook_secret: str = Header(default=""),
    authorization: str = Header(default=""),
):
    """Re-ingest existing docs with parent-child structure.

    Reads flat docs from the database, deletes them, and re-processes
    through the full pipeline (chunk → context → embed → parent-child upsert).
    """
    _verify_secret(x_webhook_secret, authorization)

    http = app.state.http_client
    openai = app.state.openai_client

    # 1. Fetch existing docs (only parents or flat docs, not child chunks)
    url = f"{config.SUPABASE_URL}/rest/v1/documents"
    params = (
        f"project_id=eq.{project_id}"
        f"&is_parent=eq.false"  # flat docs have is_parent=false (default)
        f"&parent_id=is.null"   # and no parent_id (not already a child)
        f"&select=id,title,text,type,category,subcategory,scope,is_active,priority"
        f"&order=id.asc&limit=500"
    )
    headers = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
    }
    r = await http.get(f"{url}?{params}", headers=headers)
    r.raise_for_status()
    existing_docs = r.json()

    if not existing_docs:
        return {"status": "ok", "message": "No flat docs found to re-ingest", "count": 0}

    # 2. Convert to DocPayload objects
    doc_payloads: list[DocPayload] = []
    for doc in existing_docs:
        doc_payloads.append(DocPayload(
            title=doc["title"],
            content=doc["text"],
            type=doc.get("type", "company_doc"),
            project_id=project_id,
            category=doc.get("category", "general"),
            subcategory=doc.get("subcategory", ""),
            priority=doc.get("priority", 3),
            tags=[],
        ))

    # 3. Delete old flat docs
    del_url = f"{config.SUPABASE_URL}/rest/v1/documents?project_id=eq.{project_id}&parent_id=is.null&is_parent=eq.false"
    doc_types = set(d.get("type", "") for d in existing_docs)
    if doc_types:
        quoted_types = ",".join(f'"{t}"' for t in doc_types)
        del_url += f"&type=in.({quoted_types})"
    await http.delete(del_url, headers=headers)

    # 4. Re-ingest with parent-child pipeline
    count = await sync_docs(http, openai, doc_payloads)

    logger.info("Re-ingested %d docs → %d rows for project=%s", len(doc_payloads), count, project_id)
    return {
        "status": "ok",
        "project_id": project_id,
        "docs_found": len(doc_payloads),
        "rows_created": count,
    }


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin dashboard SPA."""
    html_path = Path(__file__).parent / "admin" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "service": "woocommerce-sync-webhook",
        "version": "2.0.0",
        "active_sessions": len(_sessions),
    }
