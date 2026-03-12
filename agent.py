import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import tiktoken
from openai import OpenAI
from rich.console import Console

import config
from tools import TOOL_SCHEMAS, call_tool

# NOTE: _select_model routing removed — gpt-5-mini is cheap enough for all queries.

_client  = OpenAI(api_key=config.OPENAI_API_KEY)
_console = Console(stderr=True)  # tool notifications go to stderr

# ── Pricing (USD per 1M tokens) ───────────────────────────────────────────────

_MODEL_PRICING = {
    "gpt-5-mini":   {"input": 0.25,  "output": 2.00},
    "gpt-4.1":      {"input": 2.00,  "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40,  "output": 1.60},
    "gpt-4o":       {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":  {"input": 0.15,  "output": 0.60},
}


def _add_usage(usage: dict, prompt_tokens: int, completion_tokens: int, model: str) -> None:
    pricing = _MODEL_PRICING.get(model, {"input": 2.00, "output": 8.00})
    usage["input_tokens"]  = usage.get("input_tokens", 0)  + prompt_tokens
    usage["output_tokens"] = usage.get("output_tokens", 0) + completion_tokens
    cost = (prompt_tokens / 1_000_000) * pricing["input"] + \
           (completion_tokens / 1_000_000) * pricing["output"]
    usage["cost_usd"] = usage.get("cost_usd", 0.0) + cost


# ── Context window management ─────────────────────────────────────────────────

_CONTEXT_LIMITS = {
    "gpt-5-mini":   380_000,
    "gpt-4.1":      950_000,
    "gpt-4.1-mini": 950_000,
    "gpt-4o":       120_000,
    "gpt-4o-mini":  120_000,
}
_RESPONSE_BUFFER = 8_000
_MAX_TOOL_ROUNDS = 3
_MAX_CALLS_PER_ROUND = 4


def _compress_old_tool_results(messages: list[dict]) -> None:
    """Replace tool results from PREVIOUS turns with short summaries.

    Keeps the current (last) tool-call round intact so the model can use
    those results for its answer.  Only compresses tool messages whose
    content is longer than a small threshold — tiny results aren't worth
    touching.

    Preserves first 300 chars of each result (titles, function names, IDs)
    instead of replacing with a generic placeholder — critical for multi-turn
    where later rounds need to reference earlier findings.
    """
    # Find the index of the last assistant message that has tool_calls.
    # Everything BEFORE that round is "old" and can be compressed.
    last_tc_idx = None
    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            last_tc_idx = idx
            break

    if last_tc_idx is None:
        return  # no tool calls at all

    # Compress tool results that appear BEFORE last_tc_idx
    _MIN_CHARS = 200     # don't bother compressing tiny results
    _SUMMARY_CHARS = 300  # keep first 300 chars (titles, function names, IDs)
    for idx in range(1, last_tc_idx):
        msg = messages[idx]
        content = msg.get("content", "")
        if msg.get("role") == "tool" and len(content) > _MIN_CHARS:
            summary = content[:_SUMMARY_CHARS]
            if len(content) > _SUMMARY_CHARS:
                summary += "\n... [compressed — full result was in earlier round]"
            msg["content"] = summary


def _count_tokens(messages: list[dict], model: str) -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return sum(4 + len(enc.encode(str(m.get("content") or ""))) for m in messages)


def _trim_messages(messages: list[dict], model: str) -> None:
    """Drop oldest non-system turns in logical groups until within context limit.

    A logical group is: user message + assistant response (with tool calls) + all tool results.
    Dropping partial groups would leave orphaned tool results that confuse the model.
    """
    limit = _CONTEXT_LIMITS.get(model, 120_000) - _RESPONSE_BUFFER
    while _count_tokens(messages, model) > limit and len(messages) > 2:
        # Find the end of the first complete turn (after system message at index 0)
        i = 1
        # Skip user message
        if i < len(messages) and messages[i].get("role") == "user":
            i += 1
        # Skip assistant message (may contain tool_calls)
        if i < len(messages) and messages[i].get("role") == "assistant":
            i += 1
            # Skip all consecutive tool results belonging to this assistant turn
            while i < len(messages) and messages[i].get("role") == "tool":
                i += 1
        # Drop messages[1:i] as a complete logical group
        if i <= 1:
            # Safety: at least drop one message to avoid infinite loop
            messages.pop(1)
        else:
            del messages[1:i]


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute_tool(tc, project_id: str) -> tuple[str, str, dict, str]:
    """Execute a single tool call with one retry on error. Runs in thread pool."""
    config.set_project_id(project_id)
    try:
        try:
            arguments = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            arguments = {}

        result = call_tool(tc.function.name, arguments)

        # Retry once on transient errors (network, timeout)
        if isinstance(result, str) and result.startswith("ERROR"):
            import time
            time.sleep(1)
            retry_result = call_tool(tc.function.name, arguments)
            if not (isinstance(retry_result, str) and retry_result.startswith("ERROR")):
                return tc.id, tc.function.name, arguments, retry_result
            # Both failed — return error with warning for the agent
            result = f"{retry_result}\n\n⚠️ Tool failed after retry. Do NOT guess — inform the user about the retrieval error."

        return tc.id, tc.function.name, arguments, result
    finally:
        config.clear_project_id()


# ── Agent loop (generator — yields str chunks) ────────────────────────────────

def run_agent(messages: list[dict], usage: dict | None = None, model: str | None = None) -> Iterator[str]:
    """
    Run the agentic loop. Yields text chunks as they stream from OpenAI.

    - Tool-call turns: non-streaming (structured response required), parallel execution
    - Final answer turn: streaming (yields chunks word-by-word)
    - usage: optional mutable dict updated in-place with token counts and cost
    - model: optional model override (defaults to config.MODEL)
    """
    active_model = model or config.MODEL

    if usage is not None:
        usage["model"] = active_model

    tool_rounds = 0
    while True:
        # Compress old tool results + trim context before each call
        _compress_old_tool_results(messages)
        _trim_messages(messages, active_model)

        # Non-streaming call — needed for tool_calls structured response
        response = _client.chat.completions.create(
            model=active_model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        # Track usage from this non-streaming call
        if usage is not None and response.usage:
            _add_usage(usage, response.usage.prompt_tokens, response.usage.completion_tokens, active_model)

        message = response.choices[0].message

        # Track tool usage
        if usage is not None and message.tool_calls:
            if "tools_used" not in usage:
                usage["tools_used"] = []
            for tc in message.tool_calls:
                if tc.function.name not in usage["tools_used"]:
                    usage["tools_used"].append(tc.function.name)

        # No tool calls → this IS the final answer
        if not message.tool_calls:
            content = message.content or ""
            messages.append({"role": "assistant", "content": content})
            yield content
            return

        # Cap tool calls per round
        tool_calls = message.tool_calls[:_MAX_CALLS_PER_ROUND]
        if len(message.tool_calls) > _MAX_CALLS_PER_ROUND:
            _console.print(
                f"  [dim][[cap]][/dim] [yellow]{len(message.tool_calls)} tool calls → capped to {_MAX_CALLS_PER_ROUND}[/yellow]",
                highlight=False,
            )
            # Rebuild message with only the kept tool calls for history
            capped_msg = message.model_dump(exclude_unset=True)
            capped_msg["tool_calls"] = capped_msg["tool_calls"][:_MAX_CALLS_PER_ROUND]
            messages.append(capped_msg)
        else:
            messages.append(message.model_dump(exclude_unset=True))

        tool_rounds += 1

        # Execute all requested tools in parallel (preserve original order in results)
        current_project = config.get_project_id()
        tool_results: dict[str, tuple[str, dict, str]] = {}
        with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
            futures = {pool.submit(_execute_tool, tc, current_project): tc for tc in tool_calls}
            for future in as_completed(futures):
                tc_id, name, args, result = future.result()
                tool_results[tc_id] = (name, args, result)
                _console.print(f"  [dim][[tool]][/dim] [cyan]{name}[/cyan]", highlight=False)

        # Append results in the original order the model requested them (OpenAI API requirement)
        for tc in tool_calls:
            name, args, result = tool_results[tc.id]
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      result,
            })

        # Hard limit: force final answer after max tool rounds
        if tool_rounds >= _MAX_TOOL_ROUNDS:
            _console.print(f"  [dim][[limit]][/dim] [yellow]Max {_MAX_TOOL_ROUNDS} tool rounds reached — forcing answer[/yellow]", highlight=False)
            messages.append({"role": "user", "content": "You have used all available search rounds. Answer NOW with what you have. Do NOT call any more tools."})
