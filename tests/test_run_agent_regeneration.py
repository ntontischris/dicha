"""The powerful-tier quality guarantee: after at least one tool round, when the
cheap tool_model returns a direct answer (no tool calls), run_agent must DISCARD
it and re-generate the final answer with answer_model via a tool_choice="none"
call that sends NO temperature arg. This covers that re-generation path.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import agent


def _round1_message_with_tool_call():
    """Round-1 assistant message: exactly ONE tool_call, supports both attribute
    access and .model_dump(exclude_unset=True) (run_agent appends the dump)."""
    args = json.dumps({"query": "x"})
    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="search", arguments=args),
    )
    dumped = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "search", "arguments": args},
            }
        ],
    }
    return SimpleNamespace(
        tool_calls=[tool_call],
        content=None,
        model_dump=lambda exclude_unset=False: dumped,
    )


def _response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)


def test_direct_answer_is_regenerated_with_answer_model(monkeypatch):
    calls: list[dict] = []

    round1 = _response(_round1_message_with_tool_call())
    round2 = _response(SimpleNamespace(tool_calls=None, content="final"))
    regen = _response(SimpleNamespace(tool_calls=None, content="final"))
    responses = [round1, round2, regen]

    def fake_create(**kwargs):
        calls.append(kwargs)
        return responses[len(calls) - 1]

    monkeypatch.setattr(agent._client.chat.completions, "create", fake_create)
    monkeypatch.setattr(agent, "call_tool", lambda name, args: "tool result text")

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    out = list(
        agent.run_agent(messages, tool_model="gpt-4.1", answer_model="gpt-4.1-mini")
    )

    # Exactly three create calls: round 1, round 2, re-generation.
    assert len(calls) == 3

    regen_call = calls[2]
    # Re-generation uses the powerful answer_model, not the cheap tool_model.
    assert regen_call["model"] == "gpt-4.1-mini"
    assert regen_call["model"] != "gpt-4.1"
    # Forced answer — no further tool calls allowed.
    assert regen_call["tool_choice"] == "none"
    # The re-gen call must NOT send a temperature arg.
    assert "temperature" not in regen_call

    # The yielded final text comes from the re-generation response.
    assert out[-1] == "final"
