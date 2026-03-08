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
    """Upsert structured data into 7 tables (sequential for FK order).

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
            "parent_theme": (payload.data.theme_info.parent.name
                             if payload.data.theme_info.parent else None),
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
                method_rows.append({
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
                    "class_costs": json.dumps(m.class_costs) if m.class_costs else None,
                    "no_class_cost": m.no_class_cost,
                })
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

    if errors:
        logger.error("Structured sync errors for %s: %s", pid, "; ".join(errors))

    logger.info("Structured sync done: %d total rows for %s", total, pid)
    return total
