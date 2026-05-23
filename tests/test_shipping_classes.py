"""Tests for shipping-class persistence + rendering.

Root-cause regression: the WP plugin sends `woocommerce.shipping_classes`, but the
backend silently dropped them (no model field → Pydantic extra="ignore"), so the
agent had no authoritative class list per shop and invented slugs in code.
"""

from __future__ import annotations

from sync.models import WooCommerceData
from tools import _format_shipping_class_list


def test_woocommerce_data_keeps_shipping_classes():
    wc = WooCommerceData(
        **{
            "version": "10.4",
            "active": True,
            "shipping_classes": [
                {
                    "term_id": 6040,
                    "name": "Πλακάκια",
                    "slug": "plakakia",
                    "description": "",
                    "count": 12,
                },
                {
                    "term_id": 6039,
                    "name": "Μεγάλο Έπιπλο",
                    "slug": "megalo-epiplo",
                    "count": 3,
                },
            ],
        }
    )
    assert len(wc.shipping_classes) == 2
    assert wc.shipping_classes[0].slug == "plakakia"
    assert wc.shipping_classes[0].term_id == 6040
    assert wc.shipping_classes[1].name == "Μεγάλο Έπιπλο"


def test_format_shipping_class_list_uses_real_slugs_names_ids():
    rows = [
        {"slug": "plakakia", "name": "Πλακάκια", "term_id": 6040},
        {"slug": "megalo-epiplo", "name": "Μεγάλο Έπιπλο", "term_id": 6039},
    ]
    out = _format_shipping_class_list(rows)
    assert "plakakia" in out
    assert "megalo-epiplo" in out
    assert "6040" in out
    assert "Πλακάκια" in out
    assert "shipping class" in out.lower()


def test_format_shipping_class_list_empty():
    assert _format_shipping_class_list([]) == ""
