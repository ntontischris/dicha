"""Tests for Smart COD restriction interpretation (_interpret_cod_restrictions).

Regression guard for the min/max bug: the agent used to flip-flop on
`cart_amount_restriction` (sometimes "up to 500", sometimes "only above 500").
Per the Smart COD reference, the value means "disable COD when cart total >=
amount" — i.e. a MAXIMUM. The rendering must state this unambiguously.
"""

from __future__ import annotations

from tools import _interpret_cod_restrictions

# Real dicha-demo Smart COD shape (trimmed to the relevant fields).
SMART_COD = {
    "enabled": "yes",
    "title": "Αντικαταβολή",
    "restriction_settings": (
        '{"shipping_zone_restrictions":1,"country_restrictions":0,'
        '"cart_amount_restriction":0,"category_restriction":0,'
        '"shipping_class_restriction":0,"shipping_zone_method_restriction":0}'
    ),
    "shipping_zone_restrictions": ["1"],
    "cart_amount_restriction": "500.001",
    "category_restriction_mode": "one_product",
    "category_restriction": ["4193", "2523"],
    "shipping_class_restriction_mode": "one_product",
    "shipping_class_restriction": ["6040", "6039"],
    "shipping_zone_method_restriction": ["81_176"],
    "cart_amount_mode": ["tax", "shipping"],
    "extra_fee": "1.21",
}


def _find(lines, needle):
    return next((l for l in lines if needle in l.lower()), "")


def test_cart_amount_is_a_maximum_not_a_minimum():
    line = _find(_interpret_cod_restrictions(SMART_COD), "cart total")
    assert line, "expected a cart-amount restriction line"
    assert "500.001" in line
    assert "maximum" in line.lower()
    assert "up to" in line.lower()
    # The bug was describing it as a minimum / floor — must never happen.
    assert "minimum" not in line.lower()
    assert "at least" not in line.lower()


def test_cart_amount_states_disabled_when_ge():
    line = _find(_interpret_cod_restrictions(SMART_COD), "cart total")
    assert ">=" in line or "≥" in line
    assert "disabled" in line.lower()


def test_cart_amount_basis_included():
    line = _find(_interpret_cod_restrictions(SMART_COD), "cart total")
    assert "tax" in line.lower() and "shipping" in line.lower()


def test_shipping_zone_is_include_mode():
    zone = _find(_interpret_cod_restrictions(SMART_COD), "zone id")
    assert zone
    assert "include" in zone.lower() or "only" in zone.lower()


def test_category_is_exclude_mode_with_trigger():
    cat = _find(_interpret_cod_restrictions(SMART_COD), "categor")
    assert cat
    assert "exclude" in cat.lower() or "disabled when" in cat.lower()
    assert "one_product" in cat


def test_empty_settings_returns_no_lines():
    assert _interpret_cod_restrictions({"enabled": "yes", "title": "COD"}) == []


def test_shipping_class_ids_resolve_to_names_when_map_given():
    id_maps = {"shipping_class_restriction": {"6040": "kanapedes", "6039": "ntoylapes"}}
    line = _find(_interpret_cod_restrictions(SMART_COD, id_maps), "shipping class")
    assert "6040 (kanapedes)" in line
    assert "6039 (ntoylapes)" in line


def test_shipping_class_ids_stay_raw_without_map():
    line = _find(_interpret_cod_restrictions(SMART_COD), "shipping class")
    assert "6040" in line and "(kanapedes)" not in line
