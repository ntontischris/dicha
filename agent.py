import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import tiktoken
from openai import OpenAI
from rich.console import Console

import config
from tools import TOOL_SCHEMAS, call_tool

_client  = OpenAI(api_key=config.OPENAI_API_KEY)
_console = Console(stderr=True)  # tool notifications go to stderr

# ── Pricing (USD per 1M tokens) ───────────────────────────────────────────────

_MODEL_PRICING = {
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
    "gpt-4.1":      950_000,
    "gpt-4.1-mini": 950_000,
    "gpt-4o":       120_000,
    "gpt-4o-mini":  120_000,
}
_RESPONSE_BUFFER = 8_000


def _count_tokens(messages: list[dict], model: str) -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return sum(4 + len(enc.encode(str(m.get("content") or ""))) for m in messages)


def _trim_messages(messages: list[dict], model: str) -> None:
    """Drop oldest non-system turns until we're within the context limit."""
    limit = _CONTEXT_LIMITS.get(model, 120_000) - _RESPONSE_BUFFER
    while _count_tokens(messages, model) > limit and len(messages) > 2:
        messages.pop(1)  # oldest non-system turn
        # Also drop the next message if it's a dangling assistant/tool turn
        if len(messages) > 1 and messages[1].get("role") in ("assistant", "tool"):
            messages.pop(1)


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

def run_agent(messages: list[dict], usage: dict | None = None) -> Iterator[str]:
    """
    Run the agentic loop. Yields text chunks as they stream from OpenAI.

    - Tool-call turns: non-streaming (structured response required), parallel execution
    - Final answer turn: streaming (yields chunks word-by-word)
    - usage: optional mutable dict updated in-place with token counts and cost
    """
    while True:
        # Trim context if needed before each call
        _trim_messages(messages, config.MODEL)

        # Non-streaming call — needed for tool_calls structured response
        response = _client.chat.completions.create(
            model=config.MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        # Track usage from this non-streaming call
        if usage is not None and response.usage:
            _add_usage(usage, response.usage.prompt_tokens, response.usage.completion_tokens, config.MODEL)

        message = response.choices[0].message

        # No tool calls → this IS the final answer, stream it directly
        if not message.tool_calls:
            # Stream the same final turn (no second API call — use the content we got)
            # We stream by yielding the content we already have from the non-streaming call,
            # since we've already paid for it. No duplicate API call.
            content = message.content or ""
            messages.append({"role": "assistant", "content": content})
            yield content
            return

        # Append the assistant's tool-call turn to history
        messages.append(message.model_dump(exclude_unset=True))

        # Execute all requested tools in parallel (preserve original order in results)
        current_project = config.get_project_id()
        tool_results: dict[str, tuple[str, dict, str]] = {}
        with ThreadPoolExecutor(max_workers=len(message.tool_calls)) as pool:
            futures = {pool.submit(_execute_tool, tc, current_project): tc for tc in message.tool_calls}
            for future in as_completed(futures):
                tc_id, name, args, result = future.result()
                tool_results[tc_id] = (name, args, result)
                _console.print(f"  [dim][[tool]][/dim] [cyan]{name}[/cyan]", highlight=False)

        # Append results in the original order the model requested them (OpenAI API requirement)
        for tc in message.tool_calls:
            name, args, result = tool_results[tc.id]
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      result,
            })
