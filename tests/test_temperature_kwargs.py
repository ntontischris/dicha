"""Tool rounds want temperature=0 for deterministic tool selection, but the
gpt-5 family rejects any temperature other than the default (API 400). The
helper must omit temperature for gpt-5* and send 0 for everything else.
"""

from __future__ import annotations

import agent


def test_gpt5_models_omit_temperature():
    assert agent._temperature_kwargs("gpt-5") == {}
    assert agent._temperature_kwargs("gpt-5-mini") == {}


def test_non_gpt5_models_get_temperature_zero():
    assert agent._temperature_kwargs("gpt-4.1") == {"temperature": 0}
    assert agent._temperature_kwargs("gpt-4.1-mini") == {"temperature": 0}
    assert agent._temperature_kwargs("gpt-4o-mini") == {"temperature": 0}
