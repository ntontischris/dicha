"""Tests for settings-as-documents rendering."""
from __future__ import annotations

from sync.settings_docs import (
    _format_value,
    render_gateway_doc,
    render_shipping_doc,
    render_theme_doc,
    render_plugin_doc,
)


def test_format_value_none():
    assert _format_value(None) == "(not set)"


def test_format_value_bool():
    assert _format_value(True) == "yes"
    assert _format_value(False) == "no"


def test_format_value_list():
    assert _format_value([]) == "(none)"
    assert _format_value(["a", "b"]) == "a, b"


def test_format_value_with_options():
    meta = {"options": {"remove_unused_css": "Remove Unused CSS", "async_css": "Load CSS Async"}}
    assert _format_value("remove_unused_css", meta) == "Remove Unused CSS (remove_unused_css)"


def test_render_gateway_doc_with_form_fields():
    gw = {
        "id": "cod",
        "method_title": "Cash on Delivery",
        "enabled": "yes",
        "description": "Pay on delivery",
        "settings": {"enabled": "yes", "title": "COD", "restrict_postals": "55133"},
        "form_fields_meta": {
            "enabled": {"title": "Enable/Disable", "type": "checkbox", "description": "", "default": "no", "options": {}},
            "title": {"title": "Title", "type": "text", "description": "Payment method title", "default": "COD", "options": {}},
            "restrict_postals": {"title": "Postal Restrictions", "type": "text", "description": "Restrict for postal codes", "default": "", "options": {}},
        },
    }
    doc = render_gateway_doc(gw)
    assert "# Payment Gateway: Cash on Delivery" in doc
    assert "Postal Restrictions: 55133" in doc
    assert "Restrict for postal codes" in doc


def test_render_gateway_doc_without_form_fields():
    gw = {
        "id": "cod",
        "method_title": "COD",
        "enabled": "yes",
        "description": "",
        "settings": {"title": "COD"},
        "form_fields_meta": {},
    }
    doc = render_gateway_doc(gw)
    assert "title: COD" in doc


def test_render_shipping_doc():
    zone = {"zone_name": "Greece", "zone_id": 1}
    method = {
        "method_title": "Flat Rate",
        "method_id": "flat_rate",
        "instance_id": 5,
        "enabled": "yes",
        "settings": {"cost": "5.00", "tax_status": "taxable"},
        "form_fields_meta": {
            "cost": {"title": "Cost", "type": "text", "description": "Shipping cost", "default": "0", "options": {}},
        },
    }
    doc = render_shipping_doc(zone, method)
    assert "Zone: Greece" in doc
    assert "Cost: 5.00" in doc


def test_render_theme_doc_groups_by_prefix():
    theme_info = {"name": "Woodmart", "version": "7.0", "is_child": False}
    theme_settings = {
        "framework": "redux",
        "framework_options": {
            "blog_design": "grid",
            "blog_columns": "3",
            "header_layout": "base",
            "header_sticky": True,
        },
        "theme_mods": {},
    }
    doc = render_theme_doc(theme_info, theme_settings)
    assert "## Blog Options" in doc
    assert "## Header Options" in doc
    assert "blog_design: grid" in doc


def test_render_plugin_doc():
    ps = {
        "plugin_slug": "wp-rocket",
        "plugin_name": "WP Rocket",
        "settings": {"minify_css": 1, "defer_all_js": 0},
    }
    doc = render_plugin_doc(ps)
    assert "# Plugin Settings: WP Rocket" in doc
    assert "minify_css: 1" in doc
