"""
tools.py — WooCommerce AI Agent tools (v3)

Architecture:
  - search()               → Unified hybrid search on ALL content (code + docs + guides)
  - search_by_hook()       → Direct hook lookup via GIN index
  - get_shop_config()      → Structured project context (plugins, shipping, payments, tax)
  - _rerank()              → Cohere reranker for top-K refinement

Search pipeline:
  1. Hybrid search (vector + weighted FTS + RRF) → 25 candidates (all doc types)
  2. Rerank (Cohere cross-encoder) → top 5
  3. Progressive disclosure: QUICK_REF + summary + top 2-3 full code
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


_embedding_cache: dict[str, tuple[list[float], float]] = {}
_EMBEDDING_CACHE_TTL = 3600.0
_EMBEDDING_CACHE_MAX = 500


def _embed_query(query: str, category: str = "") -> list[float]:
    """Embed a search query with enrichment and caching.

    Documents are embedded as '[category] [type] CONTEXT: ... Title: ... CONTENT: ...'
    so queries need similar structure for better cosine similarity alignment.
    """
    cache_key = f"{category}:{query.strip().lower()}"
    now = time.monotonic()

    if cache_key in _embedding_cache:
        embedding, ts = _embedding_cache[cache_key]
        if now - ts < _EMBEDDING_CACHE_TTL:
            return embedding

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
    embedding = response.data[0].embedding

    # Cache with size limit
    if len(_embedding_cache) >= _EMBEDDING_CACHE_MAX:
        oldest_key = min(_embedding_cache, key=lambda k: _embedding_cache[k][1])
        del _embedding_cache[oldest_key]
    _embedding_cache[cache_key] = (embedding, now)

    return embedding


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


def search(query: str, category: str = "") -> str:
    """Search all project knowledge: code, company guides, project docs.

    Uses hybrid search (vector + weighted FTS + RRF) across ALL document
    types — code snippets, functions.php, theme files, company docs,
    and project docs. Global company docs are always included.
    Expands Greek terms for better retrieval. Caches results for 10 min.
    """
    # Check cache first
    project_id = config.get_project_id()
    cache_key = f"{project_id}:{category}:{query.lower().strip()}"
    now = time.monotonic()
    if cache_key in _search_cache:
        cached_result, ts = _search_cache[cache_key]
        if now - ts < _SEARCH_CACHE_TTL:
            return cached_result

    # Expand Greek terms for better FTS matching
    expanded_query = _expand_query(query)

    try:
        embedding = _embed_query(query, category)
    except Exception as e:
        return f"ERROR generating embedding: {e}"

    payload: dict = {
        "query_text": expanded_query,
        "query_embedding": embedding,
        "match_count": 25,
        "p_project_id": project_id,
    }
    if category:
        payload["p_category"] = category

    result = _rpc("hybrid_search", payload)
    if isinstance(result, dict) and "error" in result:
        return f"ERROR: {result['error']}"
    if not result:
        return "No results found. RETRY: try without category filter, or use different English search terms/synonyms."

    # Separate: regular results vs auto-resolved dependencies
    regular = [d for d in result if not d.get("is_dependency")]
    deps = [d for d in result if d.get("is_dependency")]

    # Rerank only regular results (dependencies are always included)
    reranked = _rerank(query, regular, top_n=5)

    # Mark dependencies and append after regular results
    for d in deps:
        d["_auto_resolved"] = True
    reranked.extend(deps)

    formatted = _format_results(reranked)

    # Cache the result
    _search_cache[cache_key] = (formatted, now)

    return formatted


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

    # QUICK_REF header
    active_count = sum(1 for d in result if d.get("is_active"))
    func_defs: set[str] = set()
    for doc in result:
        body = doc.get("body") or doc.get("text") or ""
        func_defs.update(_FUNC_DEF_RE.findall(body))
    header_lines = [f"QUICK_REF: {len(result)} results for hook '{hook_name}' ({active_count} active)"]
    if func_defs:
        header_lines.append(f"  Functions: {', '.join(sorted(func_defs)[:10])}")
    header_lines.append("---")

    parts = ["\n".join(header_lines)]
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


# -- Tool: search_plugin_settings ------------------------------------

# TTL cache for plugin settings
_ps_cache: dict[str, tuple[str, float]] = {}
_ps_lock = threading.Lock()
_PS_TTL = 300.0


# -- Tool: search_settings (structured query engine) -----------------

def search_settings(domain: str = "", query: str = "") -> str:
    """Search structured settings by domain. Direct DB query, no vector search.

    Domains: payments, shipping, tax, checkout, theme, plugin.
    Multi-tenant: always scoped to current project_id.
    """
    project_id = config.get_project_id()
    if not domain:
        return (
            "ERROR: domain required. Options: payments, shipping, tax, checkout, theme, plugin.\n"
            "Examples: search_settings('payments', 'COD fee'), search_settings('shipping', 'Θεσσαλονίκη')"
        )

    # Cache
    cache_key = f"settings:{project_id}:{domain}:{query.lower().strip()}"
    now = time.monotonic()
    with _ps_lock:
        if cache_key in _ps_cache:
            cached, ts = _ps_cache[cache_key]
            if now - ts < _PS_TTL:
                return cached

    handler = _SETTINGS_HANDLERS.get(domain)
    if not handler:
        return f"ERROR: Unknown domain '{domain}'. Options: payments, shipping, tax, checkout, theme, plugin."

    result = handler(project_id, query)

    with _ps_lock:
        _ps_cache[cache_key] = (result, now)
    return result


def _settings_payments(project_id: str, query: str) -> str:
    """Query payment gateways with human-readable formatting."""
    url = f"{config.SUPABASE_URL}/rest/v1/payment_gateways"
    _select_cols = "gateway_id,title,method_title,enabled,description,settings,form_fields_meta"
    _select_cols_fallback = "gateway_id,title,method_title,enabled,description,settings"
    params = f"project_id=eq.{project_id}&select={_select_cols}"

    # Filter by query if specific gateway mentioned
    query_lower = query.lower()
    if query_lower:
        params += f"&or=(gateway_id.ilike.*{query_lower}*,title.ilike.*{query_lower}*,method_title.ilike.*{query_lower}*)"

    try:
        r = _http.get(f"{url}?{params}", headers=_HEADERS)
        if r.status_code == 400:
            # form_fields_meta column may not exist yet — retry without it
            params = f"project_id=eq.{project_id}&select={_select_cols_fallback}"
            if query_lower:
                params += f"&or=(gateway_id.ilike.*{query_lower}*,title.ilike.*{query_lower}*,method_title.ilike.*{query_lower}*)"
            r = _http.get(f"{url}?{params}", headers=_HEADERS)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return f"ERROR: {e}"

    if not rows:
        # Fallback: show all enabled gateways
        try:
            r = _http.get(f"{url}?project_id=eq.{project_id}&enabled=eq.true&select={_select_cols}", headers=_HEADERS)
            if r.status_code == 400:
                r = _http.get(f"{url}?project_id=eq.{project_id}&enabled=eq.true&select={_select_cols_fallback}", headers=_HEADERS)
            r.raise_for_status()
            rows = r.json()
        except Exception:
            pass
        if not rows:
            return "No payment gateways found for this project."

    parts = []
    for gw in rows:
        settings = gw.get("settings", {})
        if isinstance(settings, str):
            settings = json.loads(settings)
        form_fields = gw.get("form_fields_meta", {})
        if isinstance(form_fields, str):
            form_fields = json.loads(form_fields) if form_fields else {}

        enabled = gw.get("enabled", False)
        parts.append(f"=== {gw.get('method_title') or gw.get('title', '?')} ({gw.get('gateway_id', '?')}) ===")
        parts.append(f"Status: {'Enabled' if enabled else 'Disabled'}")
        if gw.get("description"):
            parts.append(f"Description: {gw['description']}")

        if settings:
            parts.append("")
            # Parse restriction/fee JSON blobs into readable format
            _restriction_keys = {"restriction_settings", "fee_settings"}
            for key, value in settings.items():
                if key.startswith("_"):
                    continue
                label = key
                if form_fields and key in form_fields:
                    label = form_fields[key].get("title") or key

                # Smart parsing for complex JSON settings
                if key in _restriction_keys and isinstance(value, (str, dict)):
                    parsed = value if isinstance(value, dict) else json.loads(value) if value else {}
                    if parsed:
                        parts.append(f"- {label}:")
                        for rk, rv in parsed.items():
                            if rv and rv not in ("0", 0, "fixed", "no", "", [], {}):
                                parts.append(f"    {rk}: {_format_setting_value(rv)}")
                    continue

                val_str = _format_setting_value(value)
                if len(val_str) > 300:
                    val_str = val_str[:300] + "..."
                parts.append(f"- {label}: {val_str}")
        parts.append("")

    return "\n".join(parts)


def _settings_shipping(project_id: str, query: str) -> str:
    """Query shipping zones + methods."""
    # Get zones
    zones_url = f"{config.SUPABASE_URL}/rest/v1/shipping_zones?project_id=eq.{project_id}&select=zone_id,zone_name,locations"
    methods_url = f"{config.SUPABASE_URL}/rest/v1/shipping_methods?project_id=eq.{project_id}&enabled=eq.true&select=zone_id,zone_name,method_id,method_title,instance_id,cost,min_amount,requires,class_costs,no_class_cost,tax_status,settings,form_fields_meta"

    try:
        r_zones = _http.get(zones_url, headers=_HEADERS)
        r_zones.raise_for_status()
        zones = r_zones.json()
        r_methods = _http.get(methods_url, headers=_HEADERS)
        r_methods.raise_for_status()
        methods = r_methods.json()
    except Exception as e:
        return f"ERROR: {e}"

    if not methods:
        return "No enabled shipping methods found."

    # Filter by query
    query_lower = query.lower()
    filtered_zones = None
    method_filter = None
    if query_lower:
        # Check for zone name match
        for z in zones:
            if query_lower in (z.get("zone_name", "")).lower():
                filtered_zones = {z["zone_id"]}
                break
        # Check for method type
        if "free" in query_lower or "δωρεάν" in query_lower:
            method_filter = "free_shipping"
        elif "flat" in query_lower or "χρέωση" in query_lower or "κόστος" in query_lower:
            method_filter = "flat_rate"
        elif "pickup" in query_lower or "παραλαβή" in query_lower:
            method_filter = "local_pickup"

    # Group methods by zone
    zone_methods: dict[int, list] = {}
    for m in methods:
        zid = m.get("zone_id", 0)
        if filtered_zones and zid not in filtered_zones:
            continue
        if method_filter and m.get("method_id") != method_filter:
            continue
        zone_methods.setdefault(zid, []).append(m)

    if not zone_methods:
        return f"No shipping methods matching '{query}'. Try a zone name or method type."

    parts = []
    for zid, meths in sorted(zone_methods.items()):
        zone_name = meths[0].get("zone_name", "Unknown")
        parts.append(f"=== Zone: {zone_name} (ID: {zid}) ===")
        for m in meths:
            mid = m.get("method_id", "?")
            iid = m.get("instance_id", "?")
            title = m.get("method_title", "?")
            parts.append(f"  {title} ({mid}:{iid})")
            if m.get("cost"):
                parts.append(f"    Cost: {m['cost']}")
            if m.get("min_amount"):
                parts.append(f"    Min amount: {m['min_amount']}€")
            if m.get("requires"):
                parts.append(f"    Requires: {m['requires']}")
            cc = m.get("class_costs")
            if cc:
                if isinstance(cc, str):
                    cc = json.loads(cc)
                if cc:
                    parts.append(f"    Class costs: {json.dumps(cc, ensure_ascii=False)}")
            if m.get("no_class_cost"):
                parts.append(f"    No class cost: {m['no_class_cost']}")
            # Show extra settings from form_fields_meta (human-readable labels)
            extra_settings = m.get("settings", {})
            form_fields = m.get("form_fields_meta", {})
            if extra_settings and form_fields:
                if isinstance(extra_settings, str):
                    extra_settings = json.loads(extra_settings)
                if isinstance(form_fields, str):
                    form_fields = json.loads(form_fields) if form_fields else {}
                _shown_keys = {"cost", "min_amount", "requires", "tax_status", "type", "title"}
                for sk, sv in extra_settings.items():
                    if sk in _shown_keys or sk.startswith("_") or sv in (None, "", [], {}):
                        continue
                    label = form_fields.get(sk, {}).get("title") or sk
                    parts.append(f"    {label}: {_format_setting_value(sv)}")
        parts.append("")

    # Cap output
    result = "\n".join(parts)
    if len(result) > 4000:
        result = result[:4000] + "\n... [truncated — use a more specific query]"
    return result


def _settings_tax(project_id: str, query: str) -> str:
    """Query tax settings."""
    url = f"{config.SUPABASE_URL}/rest/v1/tax_settings?project_id=eq.{project_id}"
    try:
        r = _http.get(url, headers=_HEADERS)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return f"ERROR: {e}"

    if not rows:
        return "No tax settings found."

    tax = rows[0]
    parts = ["=== Tax Settings ==="]
    parts.append(f"Tax enabled: {tax.get('tax_enabled')}")
    parts.append(f"Prices include tax: {tax.get('prices_include_tax')}")
    parts.append(f"Tax based on: {tax.get('tax_based_on')}")
    parts.append(f"Display in shop: {tax.get('tax_display_shop')}")
    parts.append(f"Display in cart: {tax.get('tax_display_cart')}")

    tax_classes = tax.get("tax_classes")
    if isinstance(tax_classes, str):
        tax_classes = json.loads(tax_classes)
    if tax_classes:
        parts.append(f"Tax classes: {', '.join(tax_classes)}")

    tax_rates = tax.get("tax_rates")
    if isinstance(tax_rates, str):
        tax_rates = json.loads(tax_rates)
    if tax_rates:
        parts.append(f"\nTax Rates ({len(tax_rates)}):")
        for rate in tax_rates[:20]:
            parts.append(f"  {rate.get('name', '?')}: {rate.get('rate', '?')}% (class: {rate.get('class', 'standard')}, country: {rate.get('country', '*')})")

    return "\n".join(parts)


def _settings_checkout(project_id: str, query: str) -> str:
    """Query general WooCommerce settings."""
    url = f"{config.SUPABASE_URL}/rest/v1/wc_general_settings?project_id=eq.{project_id}"
    try:
        r = _http.get(url, headers=_HEADERS)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return f"ERROR: {e}"

    if not rows:
        return "No general settings found."

    gen = rows[0]
    parts = ["=== General / Checkout Settings ==="]
    parts.append(f"Currency: {gen.get('currency')} (position: {gen.get('currency_position')})")
    parts.append(f"Store country: {gen.get('store_country')}")
    parts.append(f"Store city: {gen.get('store_city')}")
    parts.append(f"Coupons enabled: {gen.get('enable_coupons')}")
    parts.append(f"Guest checkout: {gen.get('enable_guest_checkout')}")
    parts.append(f"Stock management: {gen.get('manage_stock')}")

    # If full JSON available
    settings_json = gen.get("settings_json")
    if settings_json:
        if isinstance(settings_json, str):
            settings_json = json.loads(settings_json)
        # Show extra fields not in the summary
        extra_keys = set(settings_json.keys()) - {"currency", "currency_position", "store_country", "store_city", "enable_coupons", "enable_guest_checkout", "manage_stock"}
        if extra_keys:
            parts.append("\nAdditional settings:")
            for key in sorted(extra_keys):
                val = settings_json[key]
                if val and str(val).strip():
                    parts.append(f"  {key}: {val}")

    return "\n".join(parts)


def _settings_theme(project_id: str, query: str) -> str:
    """Query theme settings with prefix filtering."""
    url = f"{config.SUPABASE_URL}/rest/v1/theme_settings?project_id=eq.{project_id}"
    try:
        r = _http.get(url, headers=_HEADERS)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return f"ERROR: {e}"

    if not rows:
        return "No theme settings found."

    ts = rows[0]
    settings = ts.get("settings", {})
    if isinstance(settings, str):
        settings = json.loads(settings)

    framework = settings.get("framework", "customizer")
    framework_opts = settings.get("framework_options", {})
    theme_mods = settings.get("theme_mods", {})
    all_opts = {**framework_opts, **theme_mods}

    slug = ts.get("theme_slug", "?")
    parts = [f"=== Theme Settings: {slug} (framework: {framework}) ==="]
    parts.append(f"Total options: {len(all_opts)}")

    if not all_opts:
        return "\n".join(parts)

    # Prefix filter from query
    query_lower = query.lower().strip()
    filtered = {}
    if query_lower:
        for key, val in all_opts.items():
            key_lower = key.lower()
            if query_lower in key_lower or any(q in key_lower for q in query_lower.split()):
                filtered[key] = val
    else:
        filtered = all_opts

    if not filtered and query_lower:
        # Try broader prefix match
        prefix = query_lower.split()[0] if query_lower.split() else ""
        for key, val in all_opts.items():
            if key.lower().startswith(prefix):
                filtered[key] = val

    if not filtered:
        # Show available prefixes
        prefixes: dict[str, int] = {}
        for key in all_opts:
            p = key.split("_")[0] if "_" in key else key
            prefixes[p] = prefixes.get(p, 0) + 1
        parts.append(f"\nNo match for '{query}'. Available sections:")
        for p, count in sorted(prefixes.items(), key=lambda x: -x[1])[:20]:
            parts.append(f"  {p}: {count} options")
        parts.append("\nTry: search_settings('theme', 'header') or search_settings('theme', 'shop')")
        return "\n".join(parts)

    # Group by prefix and show (cap at 50)
    groups: dict[str, list[tuple[str, object]]] = {}
    for key, val in list(filtered.items())[:50]:
        prefix = key.split("_")[0] if "_" in key else "general"
        groups.setdefault(prefix, []).append((key, val))

    for group_name, items in groups.items():
        parts.append(f"\n--- {group_name} ---")
        for key, val in items:
            parts.append(f"  {key}: {_format_setting_value(val)}")

    if len(filtered) > 50:
        parts.append(f"\n... showing 50/{len(filtered)} matches. Use more specific query.")

    return "\n".join(parts)


def _settings_plugin(project_id: str, query: str) -> str:
    """Query plugin settings with key filtering. Replaces search_plugin_settings()."""
    url = f"{config.SUPABASE_URL}/rest/v1/plugin_settings"
    params = f"project_id=eq.{project_id}&select=plugin_slug,plugin_name,plugin_file,settings"

    # Extract plugin name and feature keyword from query
    query_parts = query.strip().split()
    plugin_term = query_parts[0] if query_parts else ""
    feature_terms = query_parts[1:] if len(query_parts) > 1 else []

    if plugin_term:
        params += f"&or=(plugin_slug.ilike.*{plugin_term}*,plugin_name.ilike.*{plugin_term}*)"

    try:
        r = _http.get(f"{url}?{params}", headers=_HEADERS)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return f"ERROR: {e}"

    if not rows:
        if plugin_term:
            return f"No settings for plugin '{plugin_term}'. Use search_settings('plugin', '') to list all."
        # List all
        try:
            r = _http.get(f"{url}?project_id=eq.{project_id}&select=plugin_slug,plugin_name", headers=_HEADERS)
            r.raise_for_status()
            all_rows = r.json()
        except Exception:
            all_rows = []
        if not all_rows:
            return "No plugin settings synced."
        lines = [f"=== Plugin Settings ({len(all_rows)} plugins) ==="]
        for row in all_rows:
            lines.append(f"  {row.get('plugin_name', row.get('plugin_slug', '?'))}")
        lines.append("\nUse: search_settings('plugin', 'plugin_name feature')")
        return "\n".join(lines)

    parts = []
    for row in rows[:3]:  # max 3 plugins per response
        slug = row.get("plugin_slug", "?")
        name = row.get("plugin_name", slug)
        settings = row.get("settings", {})
        if isinstance(settings, str):
            settings = json.loads(settings)

        # Feature filter: if query has extra terms, filter keys
        if feature_terms and isinstance(settings, dict):
            filtered = {}
            for key, val in settings.items():
                key_lower = key.lower()
                if any(ft.lower() in key_lower for ft in feature_terms):
                    filtered[key] = val
            if filtered:
                settings = filtered

        parts.append(f"=== {name} ({slug}) ===")
        if not settings:
            parts.append("  (no settings)")
            continue

        # Group by prefix
        groups: dict[str, list[tuple[str, object]]] = {}
        for key, val in settings.items():
            if key.startswith("_"):
                continue
            # Skip empty values
            if val is None or val == "" or val == [] or val == {}:
                continue
            prefix = key.split("_")[0] if "_" in key else "general"
            groups.setdefault(prefix, []).append((key, val))

        shown = 0
        for group_name, items in groups.items():
            if shown >= 30:
                parts.append(f"... [capped at 30 settings]")
                break
            parts.append(f"\n  --- {group_name} ---")
            for key, val in items:
                if shown >= 30:
                    break
                val_str = _format_setting_value(val)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                parts.append(f"  {key}: {val_str}")
                shown += 1
        parts.append("")

    return "\n".join(parts)


def _format_setting_value(value: object) -> str:
    """Format a setting value for human readability."""
    if value is None:
        return "(not set)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        if not value:
            return "(none)"
        return ", ".join(str(v) for v in value[:20])
    if isinstance(value, dict):
        if not value:
            return "(empty)"
        return json.dumps(value, ensure_ascii=False)
    return str(value)


_SETTINGS_HANDLERS = {
    "payments": _settings_payments,
    "shipping": _settings_shipping,
    "tax": _settings_tax,
    "checkout": _settings_checkout,
    "theme": _settings_theme,
    "plugin": _settings_plugin,
}


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

    # Theme settings
    theme_settings = data.get("theme_settings") or []
    if theme_settings:
        ts_list = theme_settings if isinstance(theme_settings, list) else [theme_settings]
        for ts_item in ts_list:
            if not isinstance(ts_item, dict):
                continue
            settings = ts_item.get("settings", {})
            if isinstance(settings, str):
                settings = json.loads(settings)
            framework = settings.get("framework", "customizer") if isinstance(settings, dict) else "customizer"
            slug = ts_item.get("theme_slug", "?")
            parts.append(f"\n=== Theme Settings ({slug}) ===")
            parts.append(f"Framework: {framework}")
            if isinstance(settings, dict):
                opt_count = len(settings.get("framework_options", {})) + len(settings.get("theme_mods", {}))
                parts.append(f"Total options: {opt_count}")
                parts.append("(Use search() for specific theme settings)")

    return "\n".join(parts)


# -- Formatting -------------------------------------------------------

_BODY_HIGH = 3000    # relevance >= 0.5 → full body
_BODY_MEDIUM = 1500  # relevance 0.2-0.5 → truncated body
_NOISE_THRESHOLD = 0.15  # relevance < 0.15 → drop entirely

# Detect project-specific function calls and definitions in search results.
# Used to warn the agent about helper functions it needs to search for.
_FUNC_CALL_RE = re.compile(r"\b(dc_\w+|dicha_\w+)\s*\(")
_FUNC_DEF_RE = re.compile(r"function\s+(dc_\w+|dicha_\w+)\s*\(")

# -- Greek → English term dictionary for query expansion ----------------

_GREEK_TERMS: dict[str, str] = {
    "μεταφορικά": "shipping rates",
    "πληρωμή": "payment",
    "αντικαταβολή": "COD cash on delivery",
    "κουπόνι": "coupon",
    "δωρεάν αποστολή": "free shipping",
    "πλακάκια": "tiles plakakia",
    "φόρος": "tax",
    "φπα": "VAT tax",
    "καλάθι": "cart",
    "παραγγελία": "order",
    "ταμείο": "checkout",
    "ζώνη": "zone",
    "τιμή": "price",
    "έκπτωση": "discount",
    "προϊόν": "product",
    "τιμολόγιο": "invoice",
    "μπανιέρα": "bathtub",
    "ντουζιέρα": "shower",
    "αποστολή": "shipping delivery",
    "βάρος": "weight",
    "κατηγορία": "category",
    "απόθεμα": "stock inventory",
    "ειδοποίηση": "notification email",
    "χρέωση": "charge fee surcharge",
    "νησιά": "islands",
    "ηπειρωτική": "mainland",
}


def _expand_query(query: str) -> str:
    """Expand Greek terms and add underscore variants for FTS."""
    expanded = query
    query_lower = query.lower()
    for greek, english in _GREEK_TERMS.items():
        if greek in query_lower:
            expanded += f" {english}"
    # Underscore expansion for potential function names
    words = query_lower.split()
    if len(words) >= 2:
        underscore = "_".join(words)
        if any(underscore.startswith(p) for p in ("dc_", "dicha_", "free_", "flat_")):
            expanded += f" {underscore}"
    return expanded


# -- Search result caching -----------------------------------------------

_search_cache: dict[str, tuple[str, float]] = {}
_SEARCH_CACHE_TTL = 600.0


def _build_quick_ref(results: list[dict]) -> str:
    """Build a structured QUICK_REF header that survives compression.

    Contains: result count, function definitions, hooks, categories.
    """
    from collections import Counter
    func_defs: set[str] = set()
    hook_counts: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    active_count = sum(1 for d in results if d.get("is_active"))

    for doc in results:
        body = doc.get("body") or doc.get("text") or ""
        func_defs.update(_FUNC_DEF_RE.findall(body))
        for h in (doc.get("hooks") or []):
            hook_counts[h] += 1
        cat = doc.get("category") or doc.get("doc_type") or ""
        if cat:
            categories[cat] += 1

    lines = [f"QUICK_REF: {len(results)} results ({active_count} active)"]
    if func_defs:
        lines.append(f"  Functions: {', '.join(sorted(func_defs)[:10])}")
    if hook_counts:
        hooks_str = ", ".join(f"{h}({c})" for h, c in hook_counts.most_common(5))
        lines.append(f"  Hooks: {hooks_str}")
    if categories:
        cats_str = ", ".join(f"{c}({n})" for c, n in categories.most_common(5))
        lines.append(f"  Categories: {cats_str}")
    lines.append("---")
    return "\n".join(lines)


def _format_results(results: list[dict]) -> str:
    """Format hybrid search results with progressive disclosure.

    Tier 1 (ALL results): one-line summary each.
    Tier 2 (top 2-3): full code.
    QUICK_REF header at the top survives all compression tiers.
    """
    all_called: set[str] = set()
    all_defined: set[str] = set()

    # Filter noise
    filtered = [
        d for d in results
        if d.get("_auto_resolved") or
        d.get("relevance_score") is None or
        d.get("relevance_score", 0) >= _NOISE_THRESHOLD
    ]
    if not filtered:
        return "No results above noise threshold."

    # QUICK_REF header
    parts = [_build_quick_ref(filtered)]

    # Warn on low relevance
    top_scores = [d.get("relevance_score", 1.0) for d in filtered[:3]]
    if top_scores and max(top_scores) < 0.3:
        parts.append(
            "⚠️ LOW RELEVANCE: Top results scored < 0.3. Consider: "
            "(1) remove category filter, (2) try different English synonyms, "
            "(3) search_by_hook() if you know the hook name."
        )

    # --- Tier 1: one-line summaries for ALL results ---
    summary_lines = ["RESULTS SUMMARY:"]
    for i, doc in enumerate(filtered, 1):
        score = doc.get("relevance_score")
        active = doc.get("is_active")
        flag = " [ACTIVE]" if active else " [INACTIVE]" if active is False else ""
        cat = doc.get("category") or ""
        cat_str = f" [{cat}]" if cat else ""
        hooks = doc.get("hooks") or []
        hooks_str = f" — {', '.join(hooks[:2])}" if hooks else ""
        score_str = f", rel: {score}" if score is not None else ""
        scope = doc.get("scope", "project")
        scope_str = f" [{scope}]" if scope == "global" else ""
        summary_lines.append(
            f"{i}. {doc.get('title', 'Untitled')}{flag}{cat_str}{scope_str}{hooks_str}{score_str}"
        )
    parts.append("\n".join(summary_lines))

    # --- Tier 2: full code for top results ---
    # Determine how many to show in full based on body size
    top_body_len = len(filtered[0].get("body") or filtered[0].get("text") or "") if filtered else 0
    full_count = 2 if top_body_len > 3000 else 3

    parts.append(f"FULL CODE (top {full_count} results):")

    for i, doc in enumerate(filtered[:full_count], 1):
        score = doc.get("relevance_score")
        active = doc.get("is_active")
        flag = " [ACTIVE]" if active else " [INACTIVE]" if active is False else ""
        score_str = f" (relevance: {score})" if score is not None else ""
        hooks = doc.get("hooks") or []
        hooks_str = f"\nHooks: {', '.join(hooks)}" if hooks else ""
        context = doc.get("context_text", "")
        context_str = f"\nContext: {context}" if context else ""

        text = doc.get("body") or doc.get("text") or ""

        # Track function calls and definitions
        calls_in_doc = set(_FUNC_CALL_RE.findall(text))
        defs_in_doc = set(_FUNC_DEF_RE.findall(text))
        all_called.update(calls_in_doc)
        all_defined.update(defs_in_doc)
        external_calls = calls_in_doc - defs_in_doc
        calls_str = f"\nCalls: {', '.join(sorted(external_calls))}" if external_calls else ""

        # Smart truncation based on relevance
        max_chars = _BODY_HIGH if (score is None or score >= 0.5) else _BODY_MEDIUM
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"

        parts.append(
            f"[{i}] {doc.get('title', 'Untitled')}{flag}{score_str}"
            f"{hooks_str}{calls_str}{context_str}\n{text}"
        )

    # Also scan remaining results for function calls/defs (for helpers warning)
    for doc in filtered[full_count:]:
        body = doc.get("body") or doc.get("text") or ""
        all_called.update(_FUNC_CALL_RE.findall(body))
        all_defined.update(_FUNC_DEF_RE.findall(body))

    if len(filtered) > full_count:
        parts.append(
            f"Results #{full_count + 1}-{len(filtered)} shown as summary only. "
            "Search by function name for full code."
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
                "company guides, project docs, AND plugin reference docs. "
                "Plugin reference docs explain what plugin settings mean and how they work "
                "(use category='plugin_docs' to search only these). "
                "Always query in English. "
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
                        "enum": ["shipping", "payments", "checkout", "cart", "tax", "products", "orders", "emails", "theme", "security", "performance", "general", "plugin_docs"],
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
            "description": "Refresh shop config if needed. Config is already in the system prompt — only call this if data seems stale or you need shipping class_costs/tax details not in the summary.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_settings",
            "description": (
                "Search structured WooCommerce settings by domain. Returns exact configuration "
                "data — payment gateways, shipping zones/methods, tax rates, checkout settings, "
                "theme options, and plugin settings. Use for configuration questions (fees, "
                "thresholds, enabled features, restrictions). For code questions, use search()."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "enum": ["payments", "shipping", "tax", "checkout", "theme", "plugin"],
                        "description": (
                            "payments = gateways (COD, Stripe, bank). "
                            "shipping = zones, methods, costs, free shipping thresholds. "
                            "tax = rates, display, classes. "
                            "checkout = currency, coupons, guest checkout. "
                            "theme = theme/framework options. "
                            "plugin = individual plugin settings (Yoast, Elementor, etc)."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "What to find. Examples: 'COD fee' (payments), "
                            "'Thessaloniki free shipping' (shipping), "
                            "'Yoast breadcrumbs' (plugin), 'header' (theme). "
                            "For plugin domain: 'plugin_name feature' e.g. 'yoast breadcrumbs'."
                        ),
                    },
                },
            },
        },
    },
]


# -- Dispatch ---------------------------------------------------------

_TOOL_MAP = {
    "search": search,
    "search_by_hook": search_by_hook,
    "get_shop_config": get_shop_config,
    "search_settings": search_settings,
}


def call_tool(name: str, arguments: dict) -> str:
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return f"ERROR: Unknown tool '{name}'"
    return fn(**arguments)
