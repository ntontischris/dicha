import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import tiktoken
from openai import OpenAI
from rich.console import Console

import config
from tools import TOOL_SCHEMAS, call_tool

_client = OpenAI(api_key=config.OPENAI_API_KEY)
_console = Console(stderr=True)  # tool notifications go to stderr

# ── Pricing (USD per 1M tokens) ───────────────────────────────────────────────

_MODEL_PRICING = {
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def _add_usage(
    usage: dict, prompt_tokens: int, completion_tokens: int, model: str
) -> None:
    pricing = _MODEL_PRICING.get(model, {"input": 2.00, "output": 8.00})
    usage["input_tokens"] = usage.get("input_tokens", 0) + prompt_tokens
    usage["output_tokens"] = usage.get("output_tokens", 0) + completion_tokens
    cost = (prompt_tokens / 1_000_000) * pricing["input"] + (
        completion_tokens / 1_000_000
    ) * pricing["output"]
    usage["cost_usd"] = usage.get("cost_usd", 0.0) + cost


def _temperature_kwargs(model: str) -> dict:
    """Tool rounds want temperature=0, but gpt-5* only allow the default (1)."""
    return {} if str(model).startswith("gpt-5") else {"temperature": 0}


# ── Context window management ─────────────────────────────────────────────────

_CONTEXT_LIMITS = {
    "gpt-5-mini": 380_000,
    "gpt-4.1": 950_000,
    "gpt-4.1-mini": 950_000,
    "gpt-4o": 120_000,
    "gpt-4o-mini": 120_000,
}
_RESPONSE_BUFFER = 8_000
_MAX_TOOL_ROUNDS = 2
_MAX_CALLS_PER_ROUND = 3


# ── Tiered compression (replaces uniform compression) ─────────────────────────


def _tiered_compress(messages: list[dict]) -> None:
    """Three-tier compression: full → structured → header-only.

    Current round: no compression.
    Previous round: keep QUICK_REF + function signatures + 1200 chars body.
    Old rounds (2+): keep ONLY QUICK_REF header.
    """
    tc_indices = [
        i
        for i, m in enumerate(messages)
        if m.get("role") == "assistant" and m.get("tool_calls")
    ]

    if len(tc_indices) < 2:
        return

    current_tc = tc_indices[-1]
    previous_tc = tc_indices[-2]

    for idx, msg in enumerate(messages):
        if msg.get("role") != "tool":
            continue
        content = msg.get("content", "")
        if len(content) < 500:
            continue

        if idx > current_tc:
            pass  # Current round: no compression
        elif idx > previous_tc:
            # Previous round: structured compression
            msg["content"] = _compress_tier2(content)
        else:
            # Old rounds: header only
            msg["content"] = _compress_tier3(content)


def _compress_tier2(content: str) -> str:
    """Keep QUICK_REF + function signatures + 1200 chars of body."""
    delimiter = content.find("---\n")
    if delimiter > 0:
        quick_ref = content[: delimiter + 4]
        body = content[delimiter + 4 :]
    else:
        quick_ref = ""
        body = content

    # Extract function signatures from body
    sigs = re.findall(r"function\s+\w+\s*\([^)]*\)", body)
    sigs_str = "\nFunction signatures: " + ", ".join(sigs[:8]) if sigs else ""

    truncated = body[:1200]
    if len(body) > 1200:
        truncated += "\n... [tier-2 compressed]"

    return quick_ref + sigs_str + "\n" + truncated


def _compress_tier3(content: str) -> str:
    """Keep ONLY the QUICK_REF header."""
    delimiter = content.find("---\n")
    if delimiter > 0:
        return (
            content[: delimiter + 4] + "[tier-3: header only — see investigation state]"
        )
    return content[:300] + "\n[tier-3 compressed]"


# ── Token counting (fixed: includes tool_calls) ──────────────────────────────


def _count_tokens(messages: list[dict], model: str) -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    total = 0
    for m in messages:
        total += 4
        total += len(enc.encode(str(m.get("content") or "")))
        # Count tool_calls (previously missing — caused budget miscalculation)
        tool_calls = m.get("tool_calls")
        if tool_calls:
            for tc in tool_calls if isinstance(tool_calls, list) else []:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                total += len(enc.encode(fn.get("name", "") or ""))
                total += len(enc.encode(fn.get("arguments", "") or ""))
                total += 10  # per-call overhead
        # Count tool_call_id
        if m.get("tool_call_id"):
            total += 5
    return total


def _trim_messages(messages: list[dict], model: str) -> None:
    """Drop oldest non-system turns in logical groups until within context limit."""
    limit = _CONTEXT_LIMITS.get(model, 120_000) - _RESPONSE_BUFFER
    while _count_tokens(messages, model) > limit and len(messages) > 2:
        i = 1
        if i < len(messages) and messages[i].get("role") == "user":
            i += 1
        if i < len(messages) and messages[i].get("role") == "assistant":
            i += 1
            while i < len(messages) and messages[i].get("role") == "tool":
                i += 1
        if i <= 1:
            messages.pop(1)
        else:
            del messages[1:i]


# ── Investigation state (nothing is ever lost) ───────────────────────────────


def _build_investigation_state(messages: list[dict], tool_rounds: int) -> str:
    """Extract key findings from ALL tool results (even compressed ones).

    Ensures no information is ever permanently lost across rounds.
    Rebuilds running state from ALL messages including tier-3 compressed ones.
    """
    functions_found: set[str] = set()
    functions_called: set[str] = set()
    hooks_found: dict[str, int] = {}
    ids_found: set[str] = set()
    queries_tried: list[str] = []
    config_loaded = False

    for msg in messages:
        content = msg.get("content") or ""
        role = msg.get("role", "")

        if role == "tool":
            # Extract from tool results (works even on compressed content)
            functions_found.update(
                re.findall(r"function\s+(dc_\w+|dicha_\w+)", content)
            )
            functions_called.update(re.findall(r"\b(dc_\w+|dicha_\w+)\s*\(", content))
            # Extract from QUICK_REF header
            for func_line in re.findall(r"Functions:\s*(.+)", content):
                functions_found.update(re.findall(r"\b(dc_\w+|dicha_\w+)", func_line))
            for hook_match in re.findall(r"Hooks:\s*(.+)", content):
                for h in re.findall(r"(woocommerce_\w+)", hook_match):
                    hooks_found[h] = hooks_found.get(h, 0) + 1
            ids_found.update(
                re.findall(
                    r"(?:instance_id|zone_id|flat_rate|free_shipping):(\d+)", content
                )
            )
            if "=== Store Info ===" in content:
                config_loaded = True

        elif role == "assistant":
            tool_calls = msg.get("tool_calls") or []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    args = tc.get("function", {}).get("arguments", "")
                    query_match = re.search(r'"query"\s*:\s*"([^"]+)"', args)
                    if query_match:
                        queries_tried.append(query_match.group(1))

    # Find unresolved helpers
    unresolved = functions_called - functions_found

    # Build state string
    parts = [f"[INVESTIGATION STATE — Round {tool_rounds + 1}]"]
    if functions_found:
        parts.append(f"  Functions found: {', '.join(sorted(functions_found)[:15])}")
    if hooks_found:
        hooks_str = ", ".join(
            f"{h}({c})" for h, c in sorted(hooks_found.items(), key=lambda x: -x[1])[:8]
        )
        parts.append(f"  Hooks: {hooks_str}")
    if ids_found:
        parts.append(f"  IDs: {', '.join(sorted(ids_found)[:15])}")
    if unresolved:
        parts.append(
            f"  UNRESOLVED helpers (search by name!): {', '.join(sorted(unresolved)[:5])}"
        )
    if queries_tried:
        parts.append(f"  Queries tried: {', '.join(queries_tried[-6:])}")
    parts.append(f"  Config loaded: {'Yes' if config_loaded else 'No'}")

    return "\n".join(parts)


# ── Answer validation ─────────────────────────────────────────────────────────


def _validate_answer(answer: str, messages: list[dict]) -> str | None:
    """Lightweight validation of generated answer. Returns warning if issues found."""
    warnings: list[str] = []

    # Extract IDs from answer code blocks
    code_ids: set[str] = set()
    code_ids.update(re.findall(r"(?:instance_id|zone_id)[\s:=]+(\d+)", answer))
    code_ids.update(re.findall(r"(?:flat_rate|free_shipping):(\d+)", answer))

    if not code_ids:
        # No IDs in answer → nothing to validate
        if "TODO_UNKNOWN" in answer or "TODO_CHECK" in answer:
            return "\n\u26a0\ufe0f VALIDATION: Contains TODO markers — data may be available in tool results"
        return None

    # Collect ALL IDs from tool results + system prompt (SHOP CONTEXT)
    known_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") not in ("tool", "system"):
            continue
        content = msg.get("content") or ""
        known_ids.update(re.findall(r"(?:flat_rate|free_shipping):(\d+)", content))
        known_ids.update(re.findall(r'instance_id["\s:=]+(\d+)', content))
        known_ids.update(re.findall(r'zone_id["\s:=]+(\d+)', content))
        known_ids.update(re.findall(r"zone (\d+):", content))

    fake_ids = code_ids - known_ids
    if fake_ids:
        warnings.append(
            f"IDs not found in any tool result: {', '.join(sorted(fake_ids))}"
        )

    if "TODO_UNKNOWN" in answer or "TODO_CHECK" in answer:
        warnings.append("Contains TODO markers — data may be available in tool results")

    if warnings:
        return "\n\u26a0\ufe0f VALIDATION: " + " | ".join(warnings)
    return None


# ── Single-round completeness check ──────────────────────────────────────────


def _has_unresolved_helpers(messages: list[dict]) -> bool:
    """Check if any tool result contains unresolved helper warnings."""
    for msg in messages:
        if msg.get("role") == "tool":
            if "HELPERS CALLED BUT NOT IN RESULTS" in (msg.get("content") or ""):
                return True
    return False


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
            result = f"{retry_result}\n\n\u26a0\ufe0f Tool failed after retry. Do NOT guess — inform the user about the retrieval error."

        return tc.id, tc.function.name, arguments, result
    finally:
        config.clear_project_id()


# ── Agent loop (generator — yields str chunks) ────────────────────────────────


def run_agent(
    messages: list[dict], usage: dict | None = None, model: str | None = None
) -> Iterator[str]:
    """
    Run the agentic loop with two-model strategy + investigation state.

    - Tool rounds: cheap TOOL_MODEL for tool calling decisions
    - Final answer: better ANSWER_MODEL for quality output
    - Investigation state injected before each tool round (prevents info loss)
    - Answer validation post-processing (catches fake IDs)
    """
    tool_model = model or config.TOOL_MODEL
    answer_model = model or config.ANSWER_MODEL

    if usage is not None:
        usage["model"] = f"{tool_model} → {answer_model}"

    tool_rounds = 0
    while True:
        # Tiered compression + trim context before each call
        _tiered_compress(messages)

        # Choose model: tool rounds use cheap model, final answer uses better model
        active_model = tool_model if tool_rounds < _MAX_TOOL_ROUNDS else answer_model

        _trim_messages(messages, active_model)

        # Inject investigation state for rounds 2+ (after compression, before API call)
        state_injected = False
        if tool_rounds > 0:
            state = _build_investigation_state(messages, tool_rounds)
            state_msg = {"role": "system", "content": state}
            messages.insert(1, state_msg)
            state_injected = True

        # Non-streaming call — needed for tool_calls structured response
        # temperature=0 for tool rounds: deterministic tool selection, no creativity needed
        response = _client.chat.completions.create(
            model=active_model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0,
        )

        # Remove injected state after call (prevent accumulation)
        if state_injected:
            messages.pop(1)

        # Track usage
        if usage is not None and response.usage:
            _add_usage(
                usage,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                active_model,
            )

        message = response.choices[0].message

        # Track tool usage
        if usage is not None and message.tool_calls:
            if "tools_used" not in usage:
                usage["tools_used"] = []
            for tc in message.tool_calls:
                if tc.function.name not in usage["tools_used"]:
                    usage["tools_used"].append(tc.function.name)

        # No tool calls → final answer (use better model if this was a tool model response)
        if not message.tool_calls:
            # If the tool model produced the answer, re-generate with answer model
            if active_model != answer_model and tool_rounds > 0:
                # Discard tool-model answer, re-query with answer model
                state = _build_investigation_state(messages, tool_rounds)
                messages.insert(1, {"role": "system", "content": state})

                response = _client.chat.completions.create(
                    model=answer_model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="none",
                )

                messages.pop(1)  # remove injected state

                if usage is not None and response.usage:
                    _add_usage(
                        usage,
                        response.usage.prompt_tokens,
                        response.usage.completion_tokens,
                        answer_model,
                    )

                message = response.choices[0].message

            content = message.content or ""

            # Answer validation
            validation = _validate_answer(content, messages)
            if validation:
                content += validation
                _console.print(
                    f"  [dim][[validation]][/dim] [yellow]{validation.strip()}[/yellow]",
                    highlight=False,
                )

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
            capped_msg = message.model_dump(exclude_unset=True)
            capped_msg["tool_calls"] = capped_msg["tool_calls"][:_MAX_CALLS_PER_ROUND]
            messages.append(capped_msg)
        else:
            messages.append(message.model_dump(exclude_unset=True))

        tool_rounds += 1

        # Execute all requested tools in parallel
        current_project = config.get_project_id()
        tool_results: dict[str, tuple[str, dict, str]] = {}
        with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
            futures = {
                pool.submit(_execute_tool, tc, current_project): tc for tc in tool_calls
            }
            for future in as_completed(futures):
                tc_id, name, args, result = future.result()
                tool_results[tc_id] = (name, args, result)
                _console.print(
                    f"  [dim][[tool]][/dim] [cyan]{name}[/cyan]", highlight=False
                )

        # Append results in the original order
        for tc in tool_calls:
            name, args, result = tool_results[tc.id]
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

        # Single-round mode: skip Round 2 only if model was thorough (2+ calls) and no HELPERS
        # With 1 call, allow Round 2 so the model can search more if needed
        if (
            tool_rounds == 1
            and len(tool_calls) >= 2
            and not _has_unresolved_helpers(messages)
        ):
            _console.print(
                f"  [dim][[single-round]][/dim] [green]{len(tool_calls)} calls, no helpers — forcing answer[/green]",
                highlight=False,
            )
            # Go straight to answer model
            state = _build_investigation_state(messages, tool_rounds)
            messages.insert(1, {"role": "system", "content": state})

            response = _client.chat.completions.create(
                model=answer_model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="none",
            )

            messages.pop(1)

            if usage is not None and response.usage:
                _add_usage(
                    usage,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    answer_model,
                )

            content = response.choices[0].message.content or ""

            validation = _validate_answer(content, messages)
            if validation:
                content += validation
                _console.print(
                    f"  [dim][[validation]][/dim] [yellow]{validation.strip()}[/yellow]",
                    highlight=False,
                )

            messages.append({"role": "assistant", "content": content})
            yield content
            return

        # Hard limit: force final answer after max tool rounds
        if tool_rounds >= _MAX_TOOL_ROUNDS:
            _console.print(
                f"  [dim][[limit]][/dim] [yellow]Max {_MAX_TOOL_ROUNDS} tool rounds reached — forcing answer[/yellow]",
                highlight=False,
            )
            messages.append(
                {
                    "role": "user",
                    "content": "You have used all available search rounds. Answer NOW with what you have. Do NOT call any more tools.",
                }
            )
