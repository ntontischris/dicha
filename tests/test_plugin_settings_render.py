"""Tests for plugin-settings flattening.

Regression: WP Rocket stores all 78 toggles inside one nested option
(`wp_rocket_settings`), which got json-dumped and truncated to 200 chars — so the
agent only saw the first few keys (cdn/cache_mobile/concatenate invisible → it
guessed). Flattening lifts the nested keys to the top so every toggle is visible.
"""

from __future__ import annotations

from tools import _flatten_one_level


def test_flatten_exposes_nested_plugin_option():
    s = {
        "wp_rocket_debug": 0,
        "wp_rocket_settings": {
            "minify_css": 1,
            "cdn": 0,
            "cache_mobile": 1,
            "minify_concatenate_js": 0,
        },
    }
    flat = _flatten_one_level(s)
    assert flat["minify_css"] == 1
    assert flat["cdn"] == 0  # the value that used to be invisible
    assert flat["cache_mobile"] == 1
    assert flat["minify_concatenate_js"] == 0
    assert flat["wp_rocket_debug"] == 0


def test_flatten_keeps_flat_values():
    s = {"enabled": "yes", "title": "x", "extra_fee": "1.21"}
    assert _flatten_one_level(s) == {
        "enabled": "yes",
        "title": "x",
        "extra_fee": "1.21",
    }


def test_flatten_empty():
    assert _flatten_one_level({}) == {}
