"""Vector branch: chunk code → extract metadata → contextual retrieval → embed → upsert.

Handles both webhook code sync and doc ingestion.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx
from openai import AsyncOpenAI

import config
from sync.chunking import (
    Chunk,
    is_valid_chunk,
    split_by_size,
    split_markdown,
    split_php_functions,
    truncate_text,
)
from sync.context import generate_contexts_batch
from sync.extraction import ExtractedMeta, extract_metadata
from sync.models import DocPayload, WebhookPayload

logger = logging.getLogger(__name__)

_HEADERS = {
    "apikey": config.SUPABASE_KEY,
    "Authorization": f"Bearer {config.SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}


# -- Build raw chunks from webhook payload ----------------------------

def _build_code_chunks(payload: WebhookPayload) -> tuple[list[dict], list[dict]]:
    """Extract text chunks from webhook payload code data.

    Returns:
        (chunks, parent_infos) — chunks have parent_source_id for linking,
        parent_infos have data needed to build parent rows.
    """
    pid = payload.project_id
    chunks: list[dict] = []
    parent_infos: list[dict] = []
    _seen_parents: set[str] = set()

    def _register_parent(source_id: str, title: str, full_text: str,
                         doc_type: str, is_active: bool = True) -> None:
        if source_id in _seen_parents:
            return
        _seen_parents.add(source_id)
        parent_infos.append({
            "source_id": source_id,
            "title": title,
            "text": truncate_text(full_text),
            "type": doc_type,
            "is_active": is_active,
        })

    # -- Code snippets -------------------------------------------------
    for snippet in payload.data.code_snippets:
        if not snippet.code or len(snippet.code.strip()) < 10:
            continue

        meta_lines = [
            f"Snippet: {snippet.name or 'Untitled'}",
            f"Description: {snippet.description}" if snippet.description else "",
            f"Source: {snippet.source or 'unknown'}",
            f"Active: {'Yes' if snippet.active else 'No'}",
            f"Scope: {snippet.scope}" if snippet.scope else "",
            f"Tags: {snippet.tags}" if snippet.tags else "",
        ]
        meta_text = "\n".join(line for line in meta_lines if line)
        full_text = f"{meta_text}\n\n--- CODE ---\n{snippet.code}"

        parent_sid = f"snippet-{snippet.source}-{snippet.id}-parent"
        _register_parent(parent_sid, snippet.name or "Untitled Snippet",
                         full_text, "code_snippet", snippet.active)

        chunks.append({
            "project_id": pid,
            "type": "code_snippet",
            "source_id": f"snippet-{snippet.source}-{snippet.id}",
            "parent_source_id": parent_sid,
            "title": snippet.name or "Untitled Snippet",
            "text": truncate_text(full_text),
            "full_text": full_text,
            "is_active": snippet.active,
            "tags": snippet.tags,
            "raw_code": snippet.code,
            "chunk_index": 0,
        })

    # -- functions.php -------------------------------------------------
    funcs_php = payload.data.functions_php
    if funcs_php and funcs_php.child_theme and funcs_php.child_theme.code:
        full_code = funcs_php.child_theme.code
        php_chunks = split_php_functions(full_code)

        parent_sid = "functions-php-child-parent"
        _register_parent(parent_sid, "functions.php (child theme)",
                         full_code, "functions_php")

        for chunk in php_chunks:
            text = f"File: functions.php (child theme)\nFunction: {chunk.name}\n\n--- CODE ---\n{chunk.text}"
            chunks.append({
                "project_id": pid,
                "type": "functions_php",
                "source_id": f"functions-php-child-{chunk.index}",
                "parent_source_id": parent_sid,
                "title": f"functions.php: {chunk.name}",
                "text": truncate_text(text),
                "full_text": full_code[:8000],
                "is_active": True,
                "tags": "",
                "raw_code": chunk.text,
                "chunk_index": chunk.index,
            })

    # -- Theme files ---------------------------------------------------
    for theme_file in payload.data.theme_files:
        if not theme_file.code or len(theme_file.code.strip()) < 10:
            continue

        parent_sid = f"theme-{theme_file.path}-parent"
        _register_parent(parent_sid, theme_file.path,
                         theme_file.code, "theme_file")

        file_chunks = split_by_size(theme_file.code, 2000)

        for i, chunk_text in enumerate(file_chunks):
            part_label = f" (part {i+1}/{len(file_chunks)})" if len(file_chunks) > 1 else ""
            title = f"{theme_file.path}{part_label}"
            text = f"Theme File: {theme_file.path}\nType: {theme_file.extension}\n\n--- CODE ---\n{chunk_text}"

            chunks.append({
                "project_id": pid,
                "type": "theme_file",
                "source_id": f"theme-{theme_file.path}-{i}",
                "parent_source_id": parent_sid,
                "title": title,
                "text": truncate_text(text),
                "full_text": theme_file.code[:8000],
                "is_active": True,
                "tags": "",
                "raw_code": chunk_text,
                "chunk_index": i,
            })

    # Filter invalid chunks
    valid_chunks = [c for c in chunks if is_valid_chunk(c["text"])]
    return valid_chunks, parent_infos


def _build_doc_chunks(doc: DocPayload) -> list[dict]:
    """Build chunks from a single document (company or project doc).

    Each chunk includes a parent_source_id for parent-child linking.
    """
    scope = "global" if doc.project_id == "_global" else "project"
    parent_source_id = f"doc-{doc.title[:50]}-parent"

    # Split by markdown headings (or size fallback)
    md_chunks = split_markdown(doc.content, max_chars=2000)

    chunks: list[dict] = []
    for chunk in md_chunks:
        text = truncate_text(chunk.text)
        if not is_valid_chunk(text):
            continue

        chunks.append({
            "project_id": doc.project_id,
            "type": doc.type,
            "source_id": f"doc-{doc.title[:50]}-{chunk.index}",
            "parent_source_id": parent_source_id,
            "title": f"{doc.title}: {chunk.name}" if chunk.total > 1 else doc.title,
            "text": text,
            "full_text": doc.content[:8000],
            "is_active": True,
            "tags": " ".join(doc.tags),
            "raw_code": "",
            "scope": scope,
            "category": doc.category,
            "subcategory": doc.subcategory,
            "priority": doc.priority,
            "chunk_index": chunk.index,
        })

    return chunks


# -- Enrich text for embedding ----------------------------------------

def _enrich_text(chunk: dict, meta: ExtractedMeta, context: str) -> str:
    """Build enriched text that gets embedded.

    Structure:
      [category] [type] [ACTIVE/INACTIVE]
      CONTEXT: ... (from contextual retrieval)
      Title: ...
      Hooks: ...
      Functions: ...
      --- CONTENT ---
      actual text...
    """
    parts: list[str] = []

    # Header tags
    status = "ACTIVE" if chunk.get("is_active") else "INACTIVE"
    parts.append(f"[{meta.category}] [{chunk['type']}] [{status}]")

    # Contextual retrieval summary
    if context:
        parts.append(f"CONTEXT: {context}")

    # Metadata
    parts.append(f"Title: {chunk['title']}")
    if meta.hooks:
        parts.append(f"Hooks: {', '.join(meta.hooks[:10])}")
    if meta.functions:
        parts.append(f"Functions: {', '.join(meta.functions[:10])}")
    if chunk.get("tags"):
        parts.append(f"Tags: {chunk['tags']}")

    parts.append(f"\n--- CONTENT ---\n{chunk['text']}")

    return truncate_text("\n".join(parts))


# -- Batch embed ------------------------------------------------------

async def _batch_embed(
    client: AsyncOpenAI,
    texts: list[str],
    batch_size: int = 100,
) -> list[list[float]]:
    """Batch embed texts using OpenAI API."""
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(
            model=config.EMBEDDING_MODEL,
            input=batch,
            dimensions=1536,
        )
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)
        logger.info("Embedded batch %d-%d / %d", i, i + len(batch), len(texts))

    return all_embeddings


# -- Parent row builder -----------------------------------------------

def _build_parent_row(doc: DocPayload, now: str) -> dict:
    """Build a parent document row (full text, no embedding, is_parent=true).

    The parent stores the complete document text. When a child chunk matches
    in hybrid_search, the SQL function expands to return the parent's text,
    giving the agent full context.
    """
    scope = "global" if doc.project_id == "_global" else "project"
    return {
        "project_id": doc.project_id,
        "scope": scope,
        "type": doc.type,
        "source_id": f"doc-{doc.title[:50]}-parent",
        "title": doc.title,
        "text": truncate_text(doc.content),
        "embedding": None,
        "metadata": json.dumps({"is_parent": True}),
        "category": doc.category,
        "subcategory": doc.subcategory,
        "language": "",
        "hooks": [],
        "keywords": [],
        "is_active": True,
        "priority": doc.priority,
        "context_text": "",
        "section_path": "",
        "is_parent": True,
        "parent_id": None,
        "chunk_index": 0,
        "synced_at": now,
    }


# -- Upsert with ID return -------------------------------------------

_RETURNING_HEADERS = {
    "apikey": config.SUPABASE_KEY,
    "Authorization": f"Bearer {config.SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation,resolution=merge-duplicates",
}


async def _upsert_parents_returning_ids(
    client: httpx.AsyncClient,
    rows: list[dict],
) -> dict[str, int]:
    """Upsert parent rows and return a mapping of source_id → DB id.

    Uses Prefer: return=representation to get inserted/upserted rows back.
    """
    if not rows:
        return {}

    url = f"{config.SUPABASE_URL}/rest/v1/documents?select=id,source_id"
    r = await client.post(url, headers=_RETURNING_HEADERS, json=rows)
    if r.status_code >= 400:
        logger.error("Parent upsert failed %d: %s", r.status_code, r.text[:500])
    r.raise_for_status()

    result = r.json()
    id_map = {row["source_id"]: row["id"] for row in result}
    logger.info("Upserted %d parent docs, got %d IDs back", len(rows), len(id_map))
    return id_map


# -- Upsert documents -------------------------------------------------

async def _upsert_documents(
    client: httpx.AsyncClient,
    rows: list[dict],
    batch_size: int = 200,
) -> None:
    """Upsert document rows into Supabase."""
    url = f"{config.SUPABASE_URL}/rest/v1/documents"

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        r = await client.post(url, headers=_HEADERS, json=batch)
        if r.status_code >= 400:
            logger.error("Document upsert failed %d: %s", r.status_code, r.text[:500])
        r.raise_for_status()
        logger.info("Upserted documents %d-%d / %d", i, i + len(batch), len(rows))


# -- Parent-child handling --------------------------------------------

def _build_child_rows(
    chunks: list[dict],
    metas: list[ExtractedMeta],
    contexts: list[str],
    embeddings: list[list[float]],
    now: str,
    parent_id_map: dict[str, int] | None = None,
) -> list[dict]:
    """Build child document rows with embeddings.

    When parent_id_map is provided, links each child to its parent row
    via the parent_source_id field in the chunk dict.
    """
    rows: list[dict] = []

    for i, chunk in enumerate(chunks):
        meta = metas[i]

        # Resolve parent_id from map
        parent_id = None
        if parent_id_map and chunk.get("parent_source_id"):
            parent_id = parent_id_map.get(chunk["parent_source_id"])

        row = {
            "project_id": chunk["project_id"],
            "scope": chunk.get("scope", "project"),
            "type": chunk["type"],
            "source_id": chunk["source_id"],
            "title": chunk["title"],
            "text": chunk["text"],
            "embedding": json.dumps(embeddings[i]),
            "metadata": json.dumps({
                "project_id": chunk["project_id"],
                "type": chunk["type"],
                "source_id": chunk["source_id"],
                "is_active": chunk.get("is_active", True),
                "language": meta.language,
            }),
            "category": chunk.get("category", meta.category),
            "subcategory": chunk.get("subcategory", meta.subcategory),
            "language": meta.language,
            "hooks": meta.hooks,
            "keywords": meta.keywords,
            "is_active": chunk.get("is_active", True),
            "priority": chunk.get("priority", 3),
            "context_text": contexts[i],
            "section_path": chunk.get("section_path", ""),
            "is_parent": False,
            "parent_id": parent_id,
            "chunk_index": chunk.get("chunk_index", 0),
            "synced_at": now,
        }
        rows.append(row)

    return rows


# -- Main orchestrators -----------------------------------------------

def _build_code_parent_row(
    parent_info: dict, project_id: str, now: str,
) -> dict:
    """Build a parent row for code data (full text, no embedding)."""
    return {
        "project_id": project_id,
        "scope": "project",
        "type": parent_info["type"],
        "source_id": parent_info["source_id"],
        "title": parent_info["title"],
        "text": parent_info["text"],
        "embedding": None,
        "metadata": json.dumps({"is_parent": True}),
        "category": "",
        "subcategory": "",
        "language": "",
        "hooks": [],
        "keywords": [],
        "is_active": parent_info.get("is_active", True),
        "priority": 3,
        "context_text": "",
        "section_path": "",
        "is_parent": True,
        "parent_id": None,
        "chunk_index": 0,
        "synced_at": now,
    }


async def sync_vector_data(
    http_client: httpx.AsyncClient,
    openai_client: AsyncOpenAI,
    payload: WebhookPayload,
) -> int:
    """Full vector sync pipeline for webhook data.

    Two-pass parent-child approach (same as sync_docs):
      Pass 1: Upsert parent rows (full code, no embedding) → get DB IDs
      Pass 2: Upsert child rows (chunks with embeddings) → linked to parents

    Returns number of documents upserted (parents + children).
    """
    chunks, parent_infos = _build_code_chunks(payload)
    if not chunks:
        logger.info("No code chunks to embed for %s", payload.project_id)
        return 0

    logger.info("Built %d code chunks + %d parents for %s",
                len(chunks), len(parent_infos), payload.project_id)

    now = datetime.now(timezone.utc).isoformat()

    # -- Pass 1: Build and upsert parent rows ----------------------------
    parent_rows = [
        _build_code_parent_row(p, payload.project_id, now)
        for p in parent_infos
    ]
    parent_id_map = await _upsert_parents_returning_ids(http_client, parent_rows)
    logger.info("Pass 1 done: %d code parent rows upserted", len(parent_id_map))

    # -- Extract metadata ------------------------------------------------
    metas = [
        extract_metadata(
            code=c.get("raw_code", c["text"]),
            title=c["title"],
            tags=c.get("tags", ""),
        )
        for c in chunks
    ]

    # -- Contextual retrieval --------------------------------------------
    full_texts = {c["source_id"]: c["full_text"] for c in chunks}
    contexts = await generate_contexts_batch(
        client=openai_client,
        chunks=chunks,
        full_texts=full_texts,
        concurrency=10,
    )

    # -- Enrich and embed ------------------------------------------------
    enriched_texts = [
        _enrich_text(chunks[i], metas[i], contexts[i])
        for i in range(len(chunks))
    ]
    embeddings = await _batch_embed(openai_client, enriched_texts)

    # -- Pass 2: Build and upsert child rows (linked to parents) ---------
    rows = _build_child_rows(
        chunks, metas, contexts, embeddings, now,
        parent_id_map=parent_id_map,
    )
    await _upsert_documents(http_client, rows)

    total = len(parent_rows) + len(rows)
    logger.info("Vector sync done: %d parents + %d children = %d total for %s",
                len(parent_rows), len(rows), total, payload.project_id)
    return total


async def sync_docs(
    http_client: httpx.AsyncClient,
    openai_client: AsyncOpenAI,
    docs: list[DocPayload],
) -> int:
    """Vector sync pipeline for document uploads (company/project docs).

    Two-pass parent-child approach:
      Pass 1: Upsert parent rows (full doc text, no embedding) → get DB IDs
      Pass 2: Upsert child rows (chunks with embeddings) → linked to parents

    When the agent searches, child chunks match via embedding/FTS.
    The SQL hybrid_search expands matched children to return the parent's
    full document text — giving the agent complete context, not just fragments.

    Returns total number of documents upserted (parents + children).
    """
    now = datetime.now(timezone.utc).isoformat()

    # -- Pass 1: Build and upsert parent rows ----------------------------
    parent_rows = [_build_parent_row(doc, now) for doc in docs]
    parent_id_map = await _upsert_parents_returning_ids(http_client, parent_rows)
    logger.info("Pass 1 done: %d parent docs upserted", len(parent_id_map))

    # -- Build child chunks ----------------------------------------------
    all_chunks: list[dict] = []
    for doc in docs:
        all_chunks.extend(_build_doc_chunks(doc))

    if not all_chunks:
        logger.info("No doc chunks to embed")
        return len(parent_rows)

    logger.info("Built %d doc chunks from %d documents", len(all_chunks), len(docs))

    # Extract metadata (lighter for docs — mostly from title/tags)
    metas = [
        extract_metadata(
            code=c.get("raw_code", ""),
            title=c["title"],
            tags=c.get("tags", ""),
        )
        for c in all_chunks
    ]

    # Override category from doc payload (user-specified > auto-detected)
    for i, chunk in enumerate(all_chunks):
        if chunk.get("category") and chunk["category"] != "general":
            metas[i].category = chunk["category"]
        if chunk.get("subcategory"):
            metas[i].subcategory = chunk["subcategory"]

    # Contextual retrieval
    full_texts = {c["source_id"]: c["full_text"] for c in all_chunks}
    contexts = await generate_contexts_batch(
        client=openai_client,
        chunks=all_chunks,
        full_texts=full_texts,
        concurrency=10,
    )

    # Embed
    enriched_texts = [
        _enrich_text(all_chunks[i], metas[i], contexts[i])
        for i in range(len(all_chunks))
    ]
    embeddings = await _batch_embed(openai_client, enriched_texts)

    # -- Pass 2: Build and upsert child rows (linked to parents) ---------
    rows = _build_child_rows(
        all_chunks, metas, contexts, embeddings, now,
        parent_id_map=parent_id_map,
    )
    await _upsert_documents(http_client, rows)

    total = len(parent_rows) + len(rows)
    logger.info("Doc sync done: %d parents + %d children = %d total", len(parent_rows), len(rows), total)
    return total
