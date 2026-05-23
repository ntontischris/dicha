"""PostgreSQL branch: clear old data + upsert structured tables."""

from __future__ import annotations

import json
import logging

import httpx

import config
from sync.models import WebhookPayload

logger = logging.getLogger(__name__)

_HEADERS = {
    "apikey": config.SUPABASE_KEY,
    "Authorization": f"Bearer {config.SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}


async def _rpc(
    client: httpx.AsyncClient,
    function_name: str,
    payload: dict,
) -> dict | list:
    """Call a Supabase RPC function."""
    url = f"{config.SUPABASE_URL}/rest/v1/rpc/{function_name}"
    r = await client.post(url, headers=_HEADERS, json=payload)
    r.raise_for_status()
    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


async def _upsert(
    client: httpx.AsyncClient,
    table: str,
    rows: list[dict],
) -> None:
    """Upsert rows into a Supabase table."""
    if not rows:
        return

    url = f"{config.SUPABASE_URL}/rest/v1/{table}"
    r = await client.post(url, headers=_HEADERS, json=rows)
    r.raise_for_status()
    logger.info("Upserted %d rows into %s", len(rows), table)


async def clear_project_data(
    client: httpx.AsyncClient,
    project_id: str,
) -> None:
    """Clear all existing data for a project before re-sync."""
    await _rpc(client, "clear_project_data", {"p_project_id": project_id})
    logger.info("Cleared old data for project %s", project_id)


async def sync_structured_data(
    client: httpx.AsyncClient,
    payload: WebhookPayload,
) -> int:
    """Upsert structured data into 8 tables (sequential for FK order).

    Returns the total number of rows upserted.
    """
    pid = payload.project_id
    wc = payload.data.woocommerce
    total = 0
    errors: list[str] = []

    # -- 1. projects ---------------------------------------------------
    try:
        project_row = {
            "project_id": pid,
            "site_url": payload.site_url,
            "wp_version": payload.wordpress_version,
            "php_version": payload.php_version,
            "wc_version": wc.version,
            "wc_active": wc.active,
            "theme_name": payload.data.theme_info.name,
            "theme_version": payload.data.theme_info.version,
            "is_child_theme": payload.data.theme_info.is_child,
            "parent_theme": (
                payload.data.theme_info.parent.name
                if payload.data.theme_info.parent
                else None
            ),
            "active_plugins_count": len(payload.data.active_plugins),
            "last_sync": payload.timestamp,
        }
        await _upsert(client, "projects", [project_row])
        total += 1
    except Exception as e:
        errors.append(f"projects: {e}")

    # -- 2. payment_gateways ------------------------------------------
    try:
        gw_rows = [
            {
                "project_id": pid,
                "gateway_id": gw.id,
                "title": gw.title or gw.method_title,
                "method_title": gw.method_title,
                "enabled": gw.enabled == "yes",
                "description": gw.description,
                "supports": json.dumps(gw.supports),
                "settings": json.dumps(gw.settings),
                "form_fields_meta": json.dumps(gw.form_fields_meta)
                if gw.form_fields_meta
                else None,
            }
            for gw in wc.payment_gateways
        ]
        await _upsert(client, "payment_gateways", gw_rows)
        total += len(gw_rows)
    except Exception as e:
        errors.append(f"payment_gateways: {e}")

    # -- 3. shipping_zones ---------------------------------------------
    try:
        zone_rows = [
            {
                "project_id": pid,
                "zone_id": z.zone_id,
                "zone_name": z.zone_name,
                "locations": ", ".join(loc.code for loc in z.locations),
                "locations_json": json.dumps([loc.model_dump() for loc in z.locations]),
            }
            for z in wc.shipping_zones
        ]
        await _upsert(client, "shipping_zones", zone_rows)
        total += len(zone_rows)
    except Exception as e:
        errors.append(f"shipping_zones: {e}")

    # -- 4. shipping_methods -------------------------------------------
    try:
        method_rows = []
        for z in wc.shipping_zones:
            for m in z.methods:
                method_rows.append(
                    {
                        "project_id": pid,
                        "zone_id": z.zone_id,
                        "zone_name": z.zone_name,
                        "instance_id": m.instance_id,
                        "method_id": m.method_id,
                        "method_title": m.method_title,
                        "enabled": m.enabled == "yes",
                        "cost": m.cost,
                        "tax_status": m.tax_status,
                        "requires": m.requires,
                        "min_amount": m.min_amount,
                        "class_costs": json.dumps(m.class_costs)
                        if m.class_costs
                        else None,
                        "no_class_cost": m.no_class_cost,
                        "settings": json.dumps(m.settings) if m.settings else None,
                        "form_fields_meta": json.dumps(m.form_fields_meta)
                        if m.form_fields_meta
                        else None,
                    }
                )
        await _upsert(client, "shipping_methods", method_rows)
        total += len(method_rows)
    except Exception as e:
        errors.append(f"shipping_methods: {e}")

    # -- 5. tax_settings -----------------------------------------------
    try:
        tax = wc.tax_settings
        tax_row = {
            "project_id": pid,
            "tax_enabled": tax.tax_enabled == "yes",
            "prices_include_tax": tax.prices_include_tax == "yes",
            "tax_based_on": tax.tax_based_on,
            "tax_display_shop": tax.tax_display_shop,
            "tax_display_cart": tax.tax_display_cart,
            "tax_classes": json.dumps(tax.tax_classes),
            "tax_rates": json.dumps(tax.tax_rates),
        }
        await _upsert(client, "tax_settings", [tax_row])
        total += 1
    except Exception as e:
        errors.append(f"tax_settings: {e}")

    # -- 6. wc_general_settings ----------------------------------------
    try:
        gen = wc.general_settings
        gen_row = {
            "project_id": pid,
            "currency": gen.currency,
            "currency_position": gen.currency_position,
            "store_country": gen.store_country,
            "store_city": gen.store_city,
            "enable_coupons": gen.enable_coupons == "yes",
            "enable_guest_checkout": gen.enable_guest_checkout == "yes",
            "manage_stock": gen.manage_stock == "yes",
            "settings_json": json.dumps(gen.model_dump()),
        }
        await _upsert(client, "wc_general_settings", [gen_row])
        total += 1
    except Exception as e:
        errors.append(f"wc_general_settings: {e}")

    # -- 7. active_plugins ---------------------------------------------
    try:
        plugin_rows = [
            {
                "project_id": pid,
                "plugin_name": p.name,
                "version": p.version,
                "author": p.author,
                "description": p.description,
                "plugin_file": p.file,
            }
            for p in payload.data.active_plugins
        ]
        await _upsert(client, "active_plugins", plugin_rows)
        total += len(plugin_rows)
    except Exception as e:
        errors.append(f"active_plugins: {e}")

    # -- 8. plugin_settings ---------------------------------------------
    try:
        ps_rows = [
            {
                "project_id": pid,
                "plugin_slug": ps.plugin_slug,
                "plugin_name": ps.plugin_name,
                "plugin_file": ps.plugin_file,
                "settings": json.dumps(ps.settings),
            }
            for ps in payload.data.plugin_settings
        ]
        await _upsert(client, "plugin_settings", ps_rows)
        total += len(ps_rows)
    except Exception as e:
        errors.append(f"plugin_settings: {e}")

    # -- 9. theme_settings -----------------------------------------------
    try:
        ts = payload.data.theme_settings
        if ts.theme_mods or ts.framework_options:
            ts_row = {
                "project_id": pid,
                "theme_slug": payload.data.theme_info.name.lower().replace(" ", "-"),
                "source": ts.source or "customizer",
                "settings": json.dumps(
                    {
                        "theme_mods": ts.theme_mods,
                        "framework": ts.framework,
                        "framework_options": ts.framework_options,
                    }
                ),
            }
            await _upsert(client, "theme_settings", [ts_row])
            total += 1
    except Exception as e:
        errors.append(f"theme_settings: {e}")

    # -- 10. shipping_classes --------------------------------------------
    try:
        sc_rows = [
            {
                "project_id": pid,
                "term_id": sc.term_id,
                "name": sc.name,
                "slug": sc.slug,
                "description": sc.description,
                "count": sc.count,
            }
            for sc in wc.shipping_classes
        ]
        if sc_rows:
            await _upsert(client, "shipping_classes", sc_rows)
            total += len(sc_rows)
    except Exception as e:
        errors.append(f"shipping_classes: {e}")

    if errors:
        logger.error("Structured sync errors for %s: %s", pid, "; ".join(errors))

    logger.info("Structured sync done: %d total rows for %s", total, pid)
    return total


async def generate_project_summary(
    client: httpx.AsyncClient,
    project_id: str,
) -> str:
    """Generate compact config summary and store in projects.summary_text.

    Called after sync completes. Reuses _format_config from tools.py logic
    but implemented inline to avoid circular imports.
    """
    result = await _rpc(client, "get_project_context", {"p_project_id": project_id})
    if not result:
        return ""

    data = result[0] if isinstance(result, list) else result
    project = data.get("project") or {}
    if not project:
        return ""

    # Build compact summary
    parts = [
        f"=== Store Info ===",
        f"Site: {project.get('site_url')}",
        f"WP: {project.get('wp_version')} | WC: {project.get('wc_version')} | PHP: {project.get('php_version')}",
        f"Theme: {project.get('theme_name')} (child: {project.get('is_child_theme')})",
        f"Active plugins: {project.get('active_plugins_count')}",
    ]

    # Payment gateways (enabled only)
    gateways = [g for g in (data.get("payment_gateways") or []) if g.get("enabled")]
    if gateways:
        gw_str = ", ".join(
            f"{g.get('title')} ({g.get('gateway_id')})" for g in gateways
        )
        parts.append(f"Payment: {gw_str}")

    # Shipping methods (enabled only) — compact
    methods = [m for m in (data.get("shipping_methods") or []) if m.get("enabled")]
    if methods:
        parts.append(f"Shipping: {len(methods)} enabled methods")
        # Group by zone
        zones: dict[int, list[str]] = {}
        for m in methods:
            zid = m.get("zone_id", 0)
            zname = m.get("zone_name", "?")
            mid = m.get("method_id", "?")
            iid = m.get("instance_id", "?")
            zones.setdefault(zid, []).append(f"{mid}:{iid}")
        for zid, meths in zones.items():
            parts.append(f"  zone {zid}: {', '.join(meths)}")

    # Plugins list
    plugins = data.get("active_plugins") or []
    if plugins:
        names = [p.get("plugin_name", "?") for p in plugins]
        parts.append(f"Plugins ({len(plugins)}): {', '.join(names)}")

    # Plugin settings available (dynamic list)
    ps_list = data.get("plugin_settings") or []
    if ps_list:
        ps_names = [
            ps.get("plugin_name") or ps.get("plugin_slug", "?") for ps in ps_list
        ]
        parts.append(
            f"Plugin Settings Available: {', '.join(ps_names)} (use search_plugin_settings for details)"
        )

    # Theme settings
    ts_data = data.get("theme_settings")
    if ts_data:
        ts_list = ts_data if isinstance(ts_data, list) else [ts_data]
        for ts_item in ts_list:
            if isinstance(ts_item, dict):
                settings = ts_item.get("settings", {})
                if isinstance(settings, str):
                    settings = json.loads(settings)
                framework = (
                    settings.get("framework", "customizer")
                    if isinstance(settings, dict)
                    else "customizer"
                )
                parts.append(f"Theme Settings: {framework} framework detected")
                break

    summary = "\n".join(parts)

    # Store in projects table
    url = f"{config.SUPABASE_URL}/rest/v1/projects?project_id=eq.{project_id}"
    patch_headers = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    await client.patch(url, headers=patch_headers, json={"summary_text": summary})
    logger.info("Generated project summary for %s (%d chars)", project_id, len(summary))

    return summary
