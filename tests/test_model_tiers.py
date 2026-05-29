"""resolve_tier maps an opaque tier name to (tool_model, answer_model).

Unknown / missing tiers must fall back to the default tier so a malformed or
absent client value never breaks /chat (backward compatible).
"""

from __future__ import annotations

import config


def test_fast_tier_resolves_to_mini_mini():
    assert config.resolve_tier("fast") == (
        config.MODEL_TIERS["fast"]["tool"],
        config.MODEL_TIERS["fast"]["answer"],
    )


def test_powerful_tier_resolves_to_full_tool_mini_answer():
    assert config.resolve_tier("powerful") == (
        config.MODEL_TIERS["powerful"]["tool"],
        config.MODEL_TIERS["powerful"]["answer"],
    )


def test_unknown_tier_falls_back_to_default():
    assert config.resolve_tier("nonsense") == config.resolve_tier(
        config.DEFAULT_MODEL_TIER
    )


def test_default_tier_is_fast():
    assert config.DEFAULT_MODEL_TIER == "fast"
