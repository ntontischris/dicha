"""ChatRequest must accept an optional model_tier, defaulting to 'fast' so any
existing client that omits it keeps the current behavior (backward compatible).
"""

from __future__ import annotations

from webhook import ChatRequest


def test_model_tier_defaults_to_fast():
    req = ChatRequest(project_id="p", message="hi")
    assert req.model_tier == "fast"


def test_model_tier_accepts_powerful():
    req = ChatRequest(project_id="p", message="hi", model_tier="powerful")
    assert req.model_tier == "powerful"
