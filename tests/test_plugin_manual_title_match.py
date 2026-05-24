"""Contract between the WP-admin 'Plugin Manual' upload and the agent's lookup.

The admin form posts ONE document with title = the plugin slug in spaced form
(dashes -> spaces, e.g. "wc-smart-cod" -> "Wc Smart Cod"). This guards that such
a document produces child-chunk titles that tools._plugin_doc_summary() will find,
whose Supabase queries are:
    title ilike *{term}*Quick Summary*   (preferred)
    title ilike *{term}*                 (fallback)
with term = slug.replace('-', ' '). We replicate that ilike semantics as a
case-insensitive substring check against the REAL chunker output.
"""

from __future__ import annotations

from sync.models import DocPayload
from sync.vectors import _build_doc_chunks


def _admin_title(slug: str) -> str:
    # Mirrors PHP: ucwords( str_replace('-', ' ', $slug) )
    return " ".join(word.capitalize() for word in slug.split("-"))


def _child_titles(slug: str, content: str) -> list[str]:
    doc = DocPayload(
        project_id="_global",
        type="company_doc",
        title=_admin_title(slug),
        content=content,
        category="plugin_docs",
    )
    return [c["title"].lower() for c in _build_doc_chunks(doc)]


def test_manual_with_summary_heading_matches_preferred_query():
    slug = "wc-smart-cod"
    content = (
        "## Quick Summary for AI Interpretation\n"
        "This plugin disables cash on delivery when the cart total goes over a "
        "configured threshold, and can also restrict COD by shipping zone.\n\n"
        "## Settings\n"
        "- cart_amount_restriction: the maximum cart total still allowed for COD.\n"
        "- enabled: whether the gateway is active at all.\n"
    )
    term = slug.replace("-", " ")
    titles = _child_titles(slug, content)
    # fallback query: *term*
    assert any(term in t for t in titles), titles
    # preferred query: *term* ... *quick summary*
    assert any(term in t and "quick summary" in t for t in titles), titles


def test_short_manual_without_headings_still_matches_fallback():
    slug = "my-new-plugin"
    content = (
        "This plugin adds an extra pickup option at checkout and lets the shop "
        "owner configure a per-order handling fee. There are no markdown headings "
        "in this short manual, only a paragraph of plain explanatory text."
    )
    term = slug.replace("-", " ")
    titles = _child_titles(slug, content)
    assert any(term in t for t in titles), titles
