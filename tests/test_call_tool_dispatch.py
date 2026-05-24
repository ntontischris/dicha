"""call_tool dispatch must tolerate extra/misnamed kwargs from the LLM.

Observed in production: the model occasionally emits a kwarg the tool doesn't
accept, e.g. search_settings(domain=..., query=..., plugin="wp-rocket"), which
raised TypeError -> HTTP 500 (intermittent, ~1 in 3 calls). The dispatcher must
drop unknown kwargs and still run the valid ones so the request succeeds.
"""

from __future__ import annotations

import tools


def test_unexpected_kwarg_is_dropped_and_valid_args_pass(monkeypatch):
    seen = {}

    def fake_search_settings(domain: str = "", query: str = "") -> str:
        seen["args"] = (domain, query)
        return "ok"

    monkeypatch.setitem(tools._TOOL_MAP, "search_settings", fake_search_settings)

    out = tools.call_tool(
        "search_settings",
        {"domain": "plugin", "query": "wp-rocket lazy load", "plugin": "wp-rocket"},
    )

    assert out == "ok"  # must NOT raise on the stray 'plugin' kwarg
    assert seen["args"] == ("plugin", "wp-rocket lazy load")


def test_unknown_tool_returns_error_string():
    assert tools.call_tool("does_not_exist", {}).startswith("ERROR")
