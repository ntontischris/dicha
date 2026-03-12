"""
tools.py — WooCommerce AI Agent tools (v3)

Architecture:
  - search()               → Unified hybrid search on ALL content (code + docs + guides)
  - search_by_hook()       → Direct hook lookup via GIN index
  - get_shop_config()      → Structured project context (plugins, shipping, payments, tax)
  - _rerank()              → Cohere reranker for top-K refinement

Search pipeline:
  1. Hybrid search (vector + weighted FTS + RRF) → 40 candidates (all doc types)
  2. Rerank (Cohere cross-encoder) → top 8
  3. Parent expansion (SQL-side) → full context
"""

import json
import re
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


def _embed_query(query: str, category: str = "") -> list[float]:
    """Embed a search query with enrichment to match document embeddings.

    Documents are embedded as '[category] [type] CONTEXT: ... Title: ... CONTENT: ...'
    so queries need similar structure for better cosine similarity alignment.
    """
    parts = []
    if category:
        parts.append(f"[{category}]")
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


# -- Tool: search (unified) -------------------------------------------

def _resolve_helpers(results: list[dict], project_id: str) -> list[dict]:
    """Auto-fetch helper functions called but not defined in results.

    Scans result bodies for dc_*/dicha_* function calls, checks which
    ones are NOT defined in any result, and fetches the missing definitions
    one by one. Each search is cheap (~$0.0001 embedding + 1 Supabase call).
    """
    all_called: set[str] = set()
    all_defined: set[str] = set()

    for doc in results:
        body = doc.get("body") or doc.get("text") or ""
        all_called.update(_FUNC_CALL_RE.findall(body))
        all_defined.update(_FUNC_DEF_RE.findall(body))

    missing = all_called - all_defined
    if not missing:
        return results

    existing_ids = {doc.get("id") for doc in results}
    # Search each missing function individually for precise results.
    # Limit to 5 helpers to cap cost and latency.
    for func_name in sorted(missing)[:5]:
        try:
            embedding = _embed_query(func_name)
        except Exception:
            continue

        helper_results = _rpc("hybrid_search", {
            "query_text": func_name,
            "query_embedding": embedding,
            "match_count": 3,
            "p_project_id": project_id,
        })

        if not helper_results or isinstance(helper_results, dict):
            continue

        for doc in helper_results:
            if doc.get("id") in existing_ids:
                continue
            body = doc.get("body") or doc.get("text") or ""
            defs = set(_FUNC_DEF_RE.findall(body))
            if func_name in defs:
                doc["_auto_resolved"] = True
                results.append(doc)
                existing_ids.add(doc.get("id"))
                break  # found this helper, move to next

    return results


def search(query: str, category: str = "") -> str:
    """Search all project knowledge: code, company guides, project docs.

    Uses hybrid search (vector + weighted FTS + RRF) across ALL document
    types — code snippets, functions.php, theme files, company docs,
    and project docs. Global company docs are always included.
    Auto-resolves missing helper functions found in results.
    """
    try:
        embedding = _embed_query(query, category)
    except Exception as e:
        return f"ERROR generating embedding: {e}"

    payload: dict = {
        "query_text": query,
        "query_embedding": embedding,
        "match_count": 40,
        "p_project_id": config.get_project_id(),
        # p_doc_types NOT sent → NULL → searches ALL types
    }
    if category:
        payload["p_category"] = category

    result = _rpc("hybrid_search", payload)
    if isinstance(result, dict) and "error" in result:
        return f"ERROR: {result['error']}"
    if not result:
        return "No results found. RETRY: try without category filter, or use different English search terms/synonyms."

    # Rerank — top 8 for richer context (gpt-5-mini cost allows more data)
    reranked = _rerank(query, result, top_n=8)

    # Auto-resolve: fetch helper function definitions called in results
    reranked = _resolve_helpers(reranked, config.get_project_id())

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
        if len(text) > _BODY_HIGH:
            text = text[:_BODY_HIGH] + "\n... [truncated]"
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
    """Format project context as readable text.

    Shipping zones are classified into types (MAINLAND, ISLANDS, etc.)
    and shown compactly to save tokens while preserving all IDs.
    """
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

    # Shipping methods (enabled only) — smart grouping by zone type
    methods = [m for m in (data.get("shipping_methods") or []) if m.get("enabled")]
    if methods:
        parts.append(f"\n=== Shipping Methods ({len(methods)} enabled) ===")

        # Group by (zone_id, zone_name)
        zones: dict[tuple, list] = {}
        for m in methods:
            zone_id = m.get("zone_id", 0)
            zone_name = m.get("zone_name", "Unknown")
            zones.setdefault((zone_id, zone_name), []).append(m)

        # Classify zones into types for better agent understanding
        classified: dict[str, list[tuple]] = {
            "THESSALONIKI": [],
            "ATHENS": [],
            "MAINLAND": [],
            "ISLANDS": [],
            "OTHER": [],
        }
        for (zone_id, zone_name), zone_methods in zones.items():
            name_lower = zone_name.lower()
            has_free = any(m.get("method_id") == "free_shipping" for m in zone_methods)
            if "θεσσαλονίκη" in name_lower:
                classified["THESSALONIKI"].append((zone_id, zone_name, zone_methods))
            elif "αθήνα" in name_lower or "πειραι" in name_lower or "αττικ" in name_lower:
                classified["ATHENS"].append((zone_id, zone_name, zone_methods))
            elif has_free:
                classified["MAINLAND"].append((zone_id, zone_name, zone_methods))
            elif zone_id == 0:
                classified["OTHER"].append((zone_id, zone_name, zone_methods))
            else:
                # Islands or zones without free shipping
                classified["ISLANDS"].append((zone_id, zone_name, zone_methods))

        # Collect all shipping class slugs across all flat_rate methods
        all_class_slugs: set[str] = set()
        sample_class_costs: dict[str, str] = {}
        for m in methods:
            class_costs = m.get("class_costs")
            if class_costs and isinstance(class_costs, (dict, str)):
                costs = json.loads(class_costs) if isinstance(class_costs, str) else class_costs
                for slug, cost_formula in costs.items():
                    all_class_slugs.add(slug)
                    if slug not in sample_class_costs:
                        sample_class_costs[slug] = str(cost_formula)

        # Show shipping classes summary if any exist
        if all_class_slugs:
            parts.append("\n--- Shipping Classes (used in flat_rate class_costs) ---")
            for slug in sorted(all_class_slugs):
                sample = sample_class_costs.get(slug, "")
                parts.append(f"  {slug}: e.g. {sample}")

        # Show each zone type with its zones (compact — no class_costs per zone)
        for zone_type, zone_list in classified.items():
            if not zone_list:
                continue
            parts.append(f"\n--- {zone_type} ZONES ---")
            for zone_id, zone_name, zone_methods in zone_list:
                method_strs = []
                for m in zone_methods:
                    method_id = m.get("method_id", "?")
                    instance_id = m.get("instance_id", "?")
                    extras = []
                    if method_id == "free_shipping":
                        min_amt = m.get("min_amount")
                        requires = m.get("requires")
                        if min_amt:
                            extras.append(f"min={min_amt}€")
                        if requires:
                            extras.append(f"req={requires}")
                    else:
                        cost = m.get("cost")
                        has_classes = bool(m.get("class_costs"))
                        if cost:
                            extras.append(f"cost={cost}")
                        if has_classes:
                            extras.append("[has_class_costs]")
                        no_class = m.get("no_class_cost")
                        if no_class and method_id == "flat_rate":
                            extras.append(f"no_class={no_class}")
                    # Show tax status if not the default 'taxable'
                    tax_status = m.get("tax_status", "taxable")
                    if tax_status and tax_status != "taxable":
                        extras.append(f"tax={tax_status}")
                    extra_str = f" {' '.join(extras)}" if extras else ""
                    method_strs.append(f"{method_id}:{instance_id}{extra_str}")
                parts.append(f"  [zone {zone_id}: {zone_name}]: {', '.join(method_strs)}")

        # Free shipping compact summary — grouped by threshold
        free_methods = [m for m in methods if m.get("method_id") == "free_shipping"]
        if free_methods:
            parts.append("\n--- Free Shipping IDs (for PHP code) ---")
            # Group by min_amount for compact display
            by_threshold: dict[str, list[str]] = {}
            for m in free_methods:
                min_amt = str(m.get("min_amount", "0"))
                instance_id = str(m.get("instance_id", "?"))
                zone_name = m.get("zone_name", "?")
                by_threshold.setdefault(min_amt, []).append(
                    f"{instance_id}({zone_name})"
                )
            for threshold, instances in sorted(by_threshold.items()):
                parts.append(f"  min={threshold}€: {', '.join(instances)}")

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

_BODY_HIGH = 4000    # relevance >= 0.5 → full body
_BODY_MEDIUM = 2500  # relevance 0.2-0.5 → truncated body
_NOISE_THRESHOLD = 0.1  # relevance < 0.1 → drop entirely

# Detect project-specific function calls and definitions in search results.
# Used to warn the agent about helper functions it needs to search for.
_FUNC_CALL_RE = re.compile(r"\b(dc_\w+|dicha_\w+)\s*\(")
_FUNC_DEF_RE = re.compile(r"function\s+(dc_\w+|dicha_\w+)\s*\(")


def _format_results(results: list[dict]) -> str:
    """Format hybrid search results for the LLM.

    Smart truncation: high-relevance results get full body,
    medium gets truncated, noise (< 0.1) is dropped entirely.
    Warns when top results have low relevance to guide re-search.
    Highlights function calls per result and warns about missing helpers.
    """
    parts = []
    idx = 0
    all_called: set[str] = set()
    all_defined: set[str] = set()

    # Warn agent when top results are low-relevance → guide re-search
    top_scores = [d.get("relevance_score", 1.0) for d in results[:3]]
    if top_scores and max(top_scores) < 0.3:
        parts.append(
            "⚠️ LOW RELEVANCE: Top results scored < 0.3. Consider: "
            "(1) remove category filter, (2) try different English synonyms, "
            "(3) search_by_hook() if you know the hook name."
        )

    for doc in results:
        score = doc.get("relevance_score")
        is_auto = doc.get("_auto_resolved", False)

        # Drop noise — but never drop auto-resolved helpers
        if not is_auto and score is not None and score < _NOISE_THRESHOLD:
            continue

        # Smart body truncation based on relevance (auto-resolved get full body)
        if is_auto:
            max_chars = _BODY_HIGH
        elif score is not None and score < 0.5:
            max_chars = _BODY_MEDIUM
        else:
            max_chars = _BODY_HIGH

        idx += 1
        doc_type = doc.get("doc_type") or doc.get("type", "")
        type_tag = f" [{doc_type}]" if doc_type else ""
        active = doc.get("is_active")
        flag = " [ACTIVE]" if active else " [INACTIVE]" if active is False else ""
        auto_tag = " [AUTO-RESOLVED HELPER — USE THIS, don't rewrite]" if is_auto else ""
        score_str = f" (relevance: {score})" if score is not None else ""
        hooks = doc.get("hooks") or []
        hooks_str = f"\nHooks: {', '.join(hooks)}" if hooks else ""
        # Show keywords from metadata for extra context
        meta = doc.get("metadata") or {}
        keywords = meta.get("keywords") if isinstance(meta, dict) else []
        keywords_str = f"\nKeywords: {', '.join(keywords[:8])}" if keywords else ""
        context = doc.get("context_text", "")
        context_str = f"\nContext: {context}" if context else ""
        text = doc.get("body") or doc.get("text") or ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"

        # Track function calls and definitions across all results
        calls_in_doc = set(_FUNC_CALL_RE.findall(text))
        defs_in_doc = set(_FUNC_DEF_RE.findall(text))
        all_called.update(calls_in_doc)
        all_defined.update(defs_in_doc)
        # Show which project functions this code calls (helps agent find helpers)
        external_calls = calls_in_doc - defs_in_doc
        calls_str = f"\n⚡ Calls: {', '.join(sorted(external_calls))}" if external_calls else ""

        parts.append(
            f"[{idx}] {doc.get('title', 'Untitled')}{type_tag}{flag}{auto_tag}{score_str}"
            f"{hooks_str}{keywords_str}{calls_str}{context_str}\n{text}"
        )

    # Warn about helper functions called but not defined in any result
    missing = all_called - all_defined
    if missing:
        parts.append(
            f"⚠️ HELPERS CALLED BUT NOT IN RESULTS: {', '.join(sorted(missing))}\n"
            "→ Search for these by name in Round 2 before writing code! "
            "NEVER write a new helper when one already exists."
        )

    return "\n\n---\n\n".join(parts)


# -- OpenAI tool schemas ----------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": (
                "Search ALL project knowledge: code snippets, functions.php, theme files, "
                "company guides, and project docs. Always query in English. "
                "Tips: use function names from get_shop_config results as queries, "
                "try without category first if results are poor, "
                "search for 'dc_' prefix functions by name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query in English. Use specific terms: function names, "
                            "hook names, or feature descriptions. "
                            "Example: 'free shipping threshold override' or 'dc_hide_cod_for_backorders'"
                        ),
                    },
                    "category": {
                        "type": "string",
                        "enum": ["shipping", "payments", "checkout", "cart", "tax", "products", "orders", "emails", "theme", "security", "performance", "general"],
                        "description": "Optional filter. Omit for broader results. Use when you know the exact domain.",
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
            "description": "Find code using a specific WP/WC hook. GIN index lookup — exact hook name required. Use when you know the hook from search results or WC documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hook_name": {"type": "string", "description": "Exact hook/filter name, e.g. 'woocommerce_package_rates' or 'woocommerce_available_payment_gateways'"},
                },
                "required": ["hook_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shop_config",
            "description": "Get shop config: versions, theme, plugins, gateways, shipping zones/methods with IDs, tax, settings. Call FIRST to get real IDs before searching.",
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
    "search": search,
    "search_by_hook": search_by_hook,
    "get_shop_config": get_shop_config,
}


def call_tool(name: str, arguments: dict) -> str:
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return f"ERROR: Unknown tool '{name}'"
    return fn(**arguments)
