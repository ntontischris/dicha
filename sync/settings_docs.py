"""Settings-as-Documents: render plugin/theme settings into searchable documents.

Converts raw settings + form_fields metadata into human-readable text,
then feeds through the existing vector pipeline (contextual retrieval + embed).
This makes settings searchable via natural language through the agent's search() tool.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from openai import AsyncOpenAI

from sync.models import WebhookPayload, DocPayload
from sync.vectors import sync_docs

logger = logging.getLogger(__name__)


def _format_value(value, field_meta: dict | None = None) -> str:
    """Format a setting value for human readability."""
    if value is None:
        return "(not set)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        if not value:
            return "(none)"
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        if not value:
            return "(empty)"
        return json.dumps(value, ensure_ascii=False)

    val_str = str(value)

    # Resolve select/radio options to labels
    if field_meta and field_meta.get("options") and val_str in field_meta["options"]:
        return f"{field_meta['options'][val_str]} ({val_str})"

    return val_str


def _render_settings_block(
    settings: dict,
    form_fields: dict,
) -> list[str]:
    """Render a settings dict as human-readable lines using form_fields metadata."""
    lines = []
    for key, value in settings.items():
        if key.startswith("_"):
            continue

        field_meta = form_fields.get(key, {})
        label = field_meta.get("title") or key
        desc = field_meta.get("description", "")
        display_val = _format_value(value, field_meta)

        line = f"- {label}: {display_val}"
        if desc:
            line += f"  — {desc}"
        lines.append(line)

    return lines


def render_gateway_doc(gateway: dict) -> str:
    """Render a payment gateway's settings as a readable document."""
    settings = gateway.get("settings", {})
    form_fields = gateway.get("form_fields_meta", {})

    lines = [
        f"# Payment Gateway: {gateway.get('method_title', gateway.get('id', '?'))}",
        f"Gateway ID: {gateway.get('id', '?')}",
        f"Enabled: {gateway.get('enabled', '?')}",
        f"Description: {gateway.get('description', '')}",
        "",
        "## Settings",
    ]

    if settings and form_fields:
        lines.extend(_render_settings_block(settings, form_fields))
    elif settings:
        for key, value in settings.items():
            if not key.startswith("_"):
                lines.append(f"- {key}: {_format_value(value)}")
    else:
        lines.append("(no settings collected)")

    return "\n".join(lines)


def render_shipping_doc(zone: dict, method: dict) -> str:
    """Render a shipping method's settings as a readable document."""
    settings = method.get("settings", {})
    form_fields = method.get("form_fields_meta", {})

    lines = [
        f"# Shipping Method: {method.get('method_title', '?')}",
        f"Method ID: {method.get('method_id', '?')}",
        f"Instance ID: {method.get('instance_id', '?')}",
        f"Zone: {zone.get('zone_name', '?')} (ID: {zone.get('zone_id', '?')})",
        f"Enabled: {method.get('enabled', '?')}",
        "",
        "## Settings",
    ]

    if settings and form_fields:
        lines.extend(_render_settings_block(settings, form_fields))
    elif settings:
        for key, value in settings.items():
            if not key.startswith("_"):
                lines.append(f"- {key}: {_format_value(value)}")
    else:
        lines.append("(no settings collected)")

    return "\n".join(lines)


def render_theme_doc(theme_info: dict, theme_settings: dict) -> str:
    """Render theme settings as a readable document."""
    lines = [
        f"# Theme Settings: {theme_info.get('name', '?')}",
        f"Version: {theme_info.get('version', '?')}",
        f"Is Child Theme: {theme_info.get('is_child', False)}",
        f"Framework: {theme_settings.get('framework', 'customizer')}",
        "",
    ]

    # Framework options (Redux, Kirki) — group by prefix for better chunking
    framework_opts = theme_settings.get("framework_options", {})
    if framework_opts:
        groups: dict[str, list[tuple[str, object]]] = {}
        skip_keys = {"last_tab", "compiler", "import_export"}
        for key, value in framework_opts.items():
            if key.startswith("_") or key in skip_keys:
                continue
            prefix = key.split("_")[0] if "_" in key else "general"
            groups.setdefault(prefix, []).append((key, value))

        for group_name, items in groups.items():
            lines.append(f"\n## {group_name.title()} Options")
            for key, value in items:
                lines.append(f"- {key}: {_format_value(value)}")

    # Theme mods (smaller, more standard)
    theme_mods = theme_settings.get("theme_mods", {})
    if theme_mods:
        lines.append("")
        lines.append("## Customizer Settings")
        for key, value in theme_mods.items():
            if key.startswith("_") or isinstance(value, (bytes,)):
                continue
            lines.append(f"- {key}: {_format_value(value)}")

    return "\n".join(lines)


def render_plugin_doc(plugin_settings: dict) -> str:
    """Render generic plugin settings with prefix-based sectioning."""
    slug = plugin_settings.get("plugin_slug", "?")
    name = plugin_settings.get("plugin_name", slug)
    settings = plugin_settings.get("settings", {})

    lines = [
        f"# Plugin Settings: {name}",
        f"Slug: {slug}",
    ]

    if isinstance(settings, str):
        settings = json.loads(settings)

    if not settings:
        lines.append("\n(no settings collected)")
        return "\n".join(lines)

    # Group by prefix for better chunking
    groups: dict[str, list[tuple[str, object]]] = {}
    for key, value in settings.items():
        if key.startswith("_"):
            continue
        # Skip empty values
        if value is None or value == "" or value == [] or value == {}:
            continue
        prefix = key.split("_")[0] if "_" in key else "general"
        groups.setdefault(prefix, []).append((key, value))

    for group_name, items in groups.items():
        lines.append(f"\n## {group_name.replace('_', ' ').title()}")
        for key, value in items:
            lines.append(f"- {key}: {_format_value(value)}")

    return "\n".join(lines)


_PLUGIN_CATEGORIES = {
    "yoast": "seo", "rank-math": "seo", "seo": "seo",
    "elementor": "page-builder", "wpbakery": "page-builder",
    "wp-rocket": "performance", "litespeed": "performance", "autoptimize": "performance",
    "wordfence": "security", "sucuri": "security", "aios": "security",
    "mailchimp": "email", "klaviyo": "email", "mailerlite": "email",
    "gravity": "forms", "wpforms": "forms", "contact-form": "forms",
    "stripe": "payments", "paypal": "payments", "viva": "payments",
}


def _infer_plugin_category(slug: str, name: str) -> str:
    """Infer category from plugin slug/name."""
    combined = f"{slug} {name}".lower()
    for keyword, category in _PLUGIN_CATEGORIES.items():
        if keyword in combined:
            return category
    return "plugin"


def _extract_settings_keywords(content: str, name: str, category: str) -> list[str]:
    """Extract keywords from settings doc for FTS weight A indexing."""
    keywords = set()
    keywords.add(name.lower())
    keywords.add(category)

    # Setting key names
    for match in re.findall(r'^- (\w+):', content, re.MULTILINE):
        keywords.add(match.lower())

    # Labels from form_fields
    for match in re.findall(r'^- ([^:]+):', content, re.MULTILINE):
        for word in match.lower().split():
            if len(word) > 3:
                keywords.add(word)

    # Section headings
    for match in re.findall(r'^##\s+(.+)', content, re.MULTILINE):
        for word in match.lower().split():
            if len(word) > 3:
                keywords.add(word)

    return list(keywords)[:30]


async def generate_settings_documents(
    http_client: httpx.AsyncClient,
    openai_client: AsyncOpenAI,
    payload: WebhookPayload,
) -> int:
    """Convert all collected settings into documents and sync via vector pipeline.

    This makes settings searchable through the agent's existing search() tool
    via hybrid search (vector + FTS). Each settings document passes through
    contextual retrieval and embedding — same as code chunks and company docs.

    Returns total number of documents upserted (parents + children).
    """
    docs: list[DocPayload] = []
    pid = payload.project_id

    # -- Payment gateways: SKIP (served by search_settings domain=payments) --
    # -- Shipping methods: SKIP (served by search_settings domain=shipping) --

    # -- Theme settings -------------------------------------------------
    ts = payload.data.theme_settings
    if ts.theme_mods or ts.framework_options:
        content = render_theme_doc(
            payload.data.theme_info.model_dump(),
            ts.model_dump(),
        )
        if len(content) > 50:
            tags = _extract_settings_keywords(content, payload.data.theme_info.name, "theme")
            docs.append(DocPayload(
                project_id=pid,
                type="plugin_settings_doc",
                title=f"Settings: {payload.data.theme_info.name} theme",
                content=content,
                category="theme",
                tags=tags,
            ))

    # -- Generic plugin settings (exclude WooCommerce — already in structured tables) --
    wc_slugs = {"woocommerce", "woocommerce-legacy-rest-api"}
    for ps in payload.data.plugin_settings:
        if ps.plugin_slug in wc_slugs:
            continue
        content = render_plugin_doc(ps.model_dump())
        if len(content) < 50:
            continue
        tags = _extract_settings_keywords(content, ps.plugin_name or ps.plugin_slug, "plugin")
        docs.append(DocPayload(
            project_id=pid,
            type="plugin_settings_doc",
            title=f"Settings: {ps.plugin_name or ps.plugin_slug}",
            content=content,
            category=_infer_plugin_category(ps.plugin_slug, ps.plugin_name),
            tags=tags,
        ))

    if not docs:
        logger.info("No settings documents to generate for %s", pid)
        return 0

    logger.info(
        "Generating %d settings documents for %s: %s",
        len(docs), pid,
        ", ".join(d.title for d in docs[:5]),
    )

    return await sync_docs(http_client, openai_client, docs)
