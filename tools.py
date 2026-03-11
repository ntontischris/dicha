"""
tools.py — WooCommerce AI Agent tools (v2)

Architecture:
  - search_code()          → Hybrid search on project code (snippets, functions.php, theme files)
  - search_docs()          → Hybrid search on documentation (company + project docs)
  - search_by_hook()       → Direct hook lookup via GIN index
  - get_shop_config()      → Structured project context (plugins, shipping, payments, tax)
  - _rerank()              → Cohere reranker for top-K refinement

Search pipeline:
  1. Hybrid search (vector + weighted FTS + RRF) → 30 candidates
  2. Rerank (Cohere cross-encoder) → top 5
  3. Parent expansion (SQL-side) → full context
"""

import json
import time
import threading
import httpx
from openai import OpenAI

import config

_http = httpx.Client(timeout=30)

_HEADERS = {
    "apikey": config.SUPABASE_KEY,
    "Authorization": f"Bearer {config.SUPABASE_KEY}",
    "Content-Type": "application/json",
}

_openai = OpenAI(api_key=config.OPENAI_API_KEY)

# Optional reranker
_cohere_client = None
if config.COHERE_API_KEY:
    try:
        import cohere
        _cohere_client = cohere.Client(api_key=config.COHERE_API_KEY)
    except ImportError:
        pass


# -- TTL Cache for get_shop_config() ----------------------------------

_ctx_cache: dict[str, tuple[dict, float]] = {}
_ctx_lock = threading.Lock()
_CTX_TTL = 300.0


# -- Supabase helpers -------------------------------------------------

def _rpc(function_name: str, payload: dict) -> dict | list:
    url = f"{config.SUPABASE_URL}/rest/v1/rpc/{function_name}"
    try:
        r = _http.post(url, headers=_HEADERS, json=payload)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"Supabase {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": str(e)}


def _embed_query(query: str, category: str = "", doc_types: list[str] | None = None) -> list[float]:
    """Embed a search query with enrichment to match document embeddings.

    Documents are embedded as '[category] [type] CONTEXT: ... Title: ... CONTENT: ...'
    so queries need similar structure for better cosine similarity alignment.
    """
    parts = []
    if category:
        parts.append(f"[{category}]")
    if doc_types and len(doc_types) == 1:
        parts.append(f"[{doc_types[0]}]")
    parts.append(f"QUERY: {query}")
    enriched = " ".join(parts)

    response = _openai.embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=enriched,
        dimensions=1536,
    )
    return response.data[0].embedding


# -- Reranker ---------------------------------------------------------

def _rerank(query: str, documents: list[dict], top_n: int = 5) -> list[dict]:
    """Rerank documents using Cohere cross-encoder.

    Includes hooks, category, and context_text for richer signal.
    Falls back to original order if Cohere unavailable.
    """
    if not _cohere_client or not documents:
        return documents[:top_n]

    try:
        texts = [
            f"[{d.get('scope', 'project')}] [{d.get('category', '')}] {d.get('title', '')}\n"
            f"Section: {d.get('section_path', '')}\n"
            f"Hooks: {', '.join(d.get('hooks', []))}\n"
            f"Context: {d.get('context_text', '')}\n"
            f"{d.get('body', '')}"
            for d in documents
        ]
        result = _cohere_client.rerank(
            query=query,
            documents=texts,
            top_n=min(top_n, len(documents)),
            model="rerank-v3.5",
        )
        reranked = []
        for r in result.results:
            doc = {**documents[r.index], "relevance_score": round(r.relevance_score, 3)}
            reranked.append(doc)
        return reranked
    except Exception:
        return documents[:top_n]


# -- Tool: search_code ------------------------------------------------

_CODE_DOC_TYPES = ["code_snippet", "functions_php", "theme_file"]
_DOCS_DOC_TYPES = ["company_doc", "project_doc"]


def search_code(query: str, category: str = "") -> str:
    """Search project code: snippets, functions.php, theme files.

    Uses hybrid search (vector + weighted FTS + RRF) → rerank → top 5.
    Optional category filter narrows results.
    """
    try:
        embedding = _embed_query(query, category, doc_types=_CODE_DOC_TYPES)
    except Exception as e:
        return f"ERROR generating embedding: {e}"

    payload: dict = {
        "query_text": query,
        "query_embedding": embedding,
        "match_count": 30,
        "p_project_id": config.get_project_id(),

        "p_doc_types": _CODE_DOC_TYPES,
    }
    if category:
        payload["p_category"] = category

    result = _rpc("hybrid_search", payload)
    if isinstance(result, dict) and "error" in result:
        return f"ERROR: {result['error']}"
    if not result:
        return "No code results found. RETRY: try without category filter, or use different English search terms/synonyms."

    # Rerank
    reranked = _rerank(query, result, top_n=3)

    return _format_results(reranked)


# -- Tool: search_docs ------------------------------------------------

def search_docs(query: str, category: str = "") -> str:
    """Search documentation: company guides + project-specific docs.

    Searches global docs + current project docs combined.
    """
    try:
        embedding = _embed_query(query, category, doc_types=_DOCS_DOC_TYPES)
    except Exception as e:
        return f"ERROR generating embedding: {e}"

    payload: dict = {
        "query_text": query,
        "query_embedding": embedding,
        "match_count": 30,
        "p_project_id": config.get_project_id(),

        "p_doc_types": _DOCS_DOC_TYPES,
    }
    if category:
        payload["p_category"] = category

    result = _rpc("hybrid_search", payload)
    if isinstance(result, dict) and "error" in result:
        return f"ERROR: {result['error']}"
    if not result:
        return "No documentation found. RETRY: try without category filter, use synonyms, or broaden the English search terms."

    # Rerank
    reranked = _rerank(query, result, top_n=3)

    return _format_results(reranked)


# -- Tool: search_by_hook ---------------------------------------------

def search_by_hook(hook_name: str) -> str:
    """Find all code that uses a specific WordPress/WooCommerce hook.

    Direct lookup via GIN index — fast and precise.
    """
    result = _rpc("search_by_hook", {
        "p_hook_name": hook_name,
        "p_project_id": config.get_project_id(),
        "match_count": 5,
    })
    if isinstance(result, dict) and "error" in result:
        return f"ERROR: {result['error']}"
    if not result:
        return f"No code found using hook '{hook_name}'."

    parts = []
    for i, doc in enumerate(result, 1):
        hooks = doc.get("hooks") or []
        active = doc.get("is_active")
        flag = " [ACTIVE]" if active else " [INACTIVE]" if active is False else ""
        text = doc.get("body") or doc.get("text") or ""
        if len(text) > _BODY_MAX_CHARS:
            text = text[:_BODY_MAX_CHARS] + "\n... [truncated]"
        parts.append(
            f"[{i}] {doc.get('title', 'Untitled')}{flag}\n"
            f"Hooks: {', '.join(hooks)}\n{text}"
        )

    return "\n\n---\n\n".join(parts)


# -- Tool: get_shop_config -------------------------------------------

def get_shop_config() -> str:
    """Get structured shop configuration: plugins, shipping, payments, tax, versions.

    Returns all structured data for the current project in one call.
    Cached for 5 minutes to avoid redundant requests.
    """
    now = time.monotonic()
    project_id = config.get_project_id()

    with _ctx_lock:
        if project_id in _ctx_cache:
            data, ts = _ctx_cache[project_id]
            if now - ts < _CTX_TTL:
                return _format_config(data)

    result = _rpc("get_project_context", {"p_project_id": project_id})
    if isinstance(result, dict) and "error" in result:
        return f"ERROR: {result['error']}"

    data = result[0] if isinstance(result, list) else result

    with _ctx_lock:
        _ctx_cache[project_id] = (data, now)

    return _format_config(data)


def _format_config(data: dict) -> str:
    """Format project context as readable text."""
    project = data.get("project") or {}
    if not project:
        return "No shop data synced yet. Run a sync from the WP plugin first."

    parts = [
        f"=== Store Info ===",
        f"Site: {project.get('site_url')}",
        f"WP: {project.get('wp_version')} | WC: {project.get('wc_version')} | PHP: {project.get('php_version')}",
        f"Theme: {project.get('theme_name')} (child: {project.get('is_child_theme')})",
        f"Active plugins: {project.get('active_plugins_count')}",
        f"Last sync: {project.get('last_sync')}",
    ]

    # Payment gateways (enabled only)
    gateways = [g for g in (data.get("payment_gateways") or []) if g.get("enabled")]
    if gateways:
        parts.append("\n=== Payment Gateways (enabled) ===")
        for g in gateways:
            parts.append(f"- {g.get('title')} ({g.get('gateway_id')})")

    # Shipping methods (enabled only) — grouped by zone for brevity
    methods = [m for m in (data.get("shipping_methods") or []) if m.get("enabled")]
    if methods:
        parts.append(f"\n=== Shipping Methods ({len(methods)} enabled) ===")
        # Group by zone
        zones: dict[str, list] = {}
        for m in methods:
            zone = m.get("zone_name", "Unknown")
            zones.setdefault(zone, []).append(m)
        for zone_name, zone_methods in zones.items():
            method_strs = []
            for m in zone_methods:
                title = m.get("method_title", "?")
                cost = m.get("cost")
                cost_str = f" ({cost})" if cost else ""
                method_strs.append(f"{title}{cost_str}")
            parts.append(f"[{zone_name}]: {', '.join(method_strs)}")

    # Tax
    tax = data.get("tax_settings") or {}
    if tax:
        parts.append(f"\n=== Tax ===")
        parts.append(f"Enabled: {tax.get('tax_enabled')} | Prices include tax: {tax.get('prices_include_tax')}")
        rates = tax.get("tax_rates")
        if isinstance(rates, str):
            rates = json.loads(rates)
        if rates:
            for r in rates[:5]:
                parts.append(f"- Rate: {r.get('rate', '')}% ({r.get('name', '')})")

    # General settings
    general = data.get("wc_general_settings") or {}
    if general:
        parts.append(f"\n=== General Settings ===")
        parts.append(f"Currency: {general.get('currency', '?')} (position: {general.get('currency_position', '?')})")
        parts.append(f"Store location: {general.get('store_country', '?')}, {general.get('store_city', '?')}")
        parts.append(f"Coupons enabled: {general.get('enable_coupons')}")
        parts.append(f"Guest checkout: {general.get('enable_guest_checkout')}")
        parts.append(f"Stock management: {general.get('manage_stock')}")

    # Active plugins — compact format (name only) to save tokens
    plugins = data.get("active_plugins") or []
    if plugins:
        names = [p.get("plugin_name", "?") for p in plugins]
        parts.append(f"\n=== Active Plugins ({len(plugins)}) ===")
        parts.append(", ".join(names))

    return "\n".join(parts)


# -- Formatting -------------------------------------------------------

_BODY_HIGH = 3000    # relevance >= 0.5 → full body
_BODY_MEDIUM = 1500  # relevance 0.2-0.5 → truncated body
_NOISE_THRESHOLD = 0.1  # relevance < 0.1 → drop entirely


def _format_results(results: list[dict]) -> str:
    """Format hybrid search results for the LLM.

    Smart truncation: high-relevance results get full body,
    medium gets truncated, noise (< 0.1) is dropped entirely.
    """
    parts = []
    idx = 0
    for doc in results:
        score = doc.get("relevance_score")

        # Drop noise — wastes tokens and confuses the model
        if score is not None and score < _NOISE_THRESHOLD:
            continue

        # Smart body truncation based on relevance
        if score is not None and score < 0.5:
            max_chars = _BODY_MEDIUM
        else:
            max_chars = _BODY_HIGH

        idx += 1
        active = doc.get("is_active")
        flag = " [ACTIVE]" if active else " [INACTIVE]" if active is False else ""
        score_str = f" (relevance: {score})" if score is not None else ""
        hooks = doc.get("hooks") or []
        hooks_str = f"\nHooks: {', '.join(hooks)}" if hooks else ""
        context = doc.get("context_text", "")
        context_str = f"\nContext: {context}" if context else ""
        text = doc.get("body") or doc.get("text") or ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"

        parts.append(
            f"[{idx}] {doc.get('title', 'Untitled')}{flag}{score_str}"
            f"{hooks_str}{context_str}\n{text}"
        )

    return "\n\n---\n\n".join(parts)


# -- OpenAI tool schemas ----------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search project code: snippets, functions.php, theme files. Hybrid vector+keyword search. Always query in English.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query in English"},
                    "category": {
                        "type": "string",
                        "enum": ["shipping", "payments", "checkout", "cart", "tax", "products", "orders", "emails", "theme", "security", "performance", "general"],
                        "description": "Optional category filter",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Search documentation: company guides, how-tos, project notes. Always query in English.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query in English"},
                    "category": {
                        "type": "string",
                        "enum": ["shipping", "payments", "checkout", "cart", "tax", "products", "orders", "emails", "theme", "security", "performance", "general"],
                        "description": "Optional category filter",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_hook",
            "description": "Find code using a specific WP/WC hook. GIN index lookup — exact hook name required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hook_name": {"type": "string", "description": "Exact hook/filter name"},
                },
                "required": ["hook_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shop_config",
            "description": "Get shop config: versions, theme, plugins, gateways, shipping, tax, settings.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# -- Dispatch ---------------------------------------------------------

_TOOL_MAP = {
    "search_code": search_code,
    "search_docs": search_docs,
    "search_by_hook": search_by_hook,
    "get_shop_config": get_shop_config,
}


def call_tool(name: str, arguments: dict) -> str:
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return f"ERROR: Unknown tool '{name}'"
    return fn(**arguments)
