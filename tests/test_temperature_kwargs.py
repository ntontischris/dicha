"""Tool rounds want temperature=0 for deterministic tool selection, but the
gpt-5 family rejects any temperature other than the default (API 400). The
helper must omit temperature for gpt-5* and send 0 for everything else.
"""

from __future__ import annotations

import agent


def test_gpt5_models_omit_temperature():
    assert agent._temperature_kwargs("gpt-5") == {}
    assert agent._temperature_kwargs("gpt-5-mini") == {}
    assert agent._temperature_kwargs("gpt-5-turbo") == {}  # any gpt-5* variant


def test_non_gpt5_models_get_temperature_zero():
    assert agent._temperature_kwargs("gpt-4.1") == {"temperature": 0}
    assert agent._temperature_kwargs("gpt-4.1-mini") == {"temperature": 0}
    assert agent._temperature_kwargs("gpt-4o-mini") == {"temperature": 0}


from types import SimpleNamespace


def _fake_response_no_tools(content: str = "done"):
    """Minimal OpenAI-style response whose message has no tool_calls."""
    message = SimpleNamespace(tool_calls=None, content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=None)


def _run(monkeypatch, **run_kwargs):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response_no_tools()

    monkeypatch.setattr(agent._client.chat.completions, "create", fake_create)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    list(agent.run_agent(messages, **run_kwargs))
    return captured


def test_tool_round_sends_temperature_zero_for_gpt41(monkeypatch):
    captured = _run(monkeypatch, tool_model="gpt-4.1", answer_model="gpt-4.1-mini")
    assert captured["model"] == "gpt-4.1"
    assert captured.get("temperature") == 0


def test_tool_round_omits_temperature_for_gpt5(monkeypatch):
    captured = _run(monkeypatch, tool_model="gpt-5-mini", answer_model="gpt-4.1-mini")
    assert captured["model"] == "gpt-5-mini"
    assert "temperature" not in captured
