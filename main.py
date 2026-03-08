import sys
import io
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output on Windows so Greek characters display correctly
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import config  # validates env vars on import
from agent import run_agent

from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.panel import Panel

console = Console()

PROMPT_FILE = Path(__file__).parent / "prompts" / "system_prompt.md"
_LOG_DIR    = Path(__file__).parent / "logs"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    try:
        template = PROMPT_FILE.read_text(encoding="utf-8")
        return template.replace("{project_id}", config.PROJECT_ID)
    except FileNotFoundError:
        console.print(f"[red]ERROR:[/red] System prompt not found at {PROMPT_FILE}")
        sys.exit(1)


def _log_turn(role: str, content: str) -> None:
    _LOG_DIR.mkdir(exist_ok=True)
    path = _LOG_DIR / f"{config.PROJECT_ID}_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    entry = {
        "ts":      datetime.now(timezone.utc).isoformat(),
        "project": config.PROJECT_ID,
        "model":   config.MODEL,
        "role":    role,
        "content": content,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WooCommerce AI Agent")
    parser.add_argument("--project", "-p", metavar="CLIENT_ID",
                        help="Project ID (overrides .env PROJECT_ID)")
    parser.add_argument("--model", "-m", metavar="MODEL",
                        help="OpenAI model (overrides .env MODEL)")
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # CLI args override .env — config attrs are module-level, visible to all importers
    if args.project:
        config.PROJECT_ID = args.project
        config.set_project_id(args.project)
    if args.model:
        config.MODEL = args.model

    system_prompt = load_system_prompt()
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Startup banner
    console.print(Panel(
        "[bold cyan]WooCommerce AI Agent[/bold cyan]\n"
        "Hi, είμαι ο Χρήστος και χαίρομαι να συνεργάζομαι με ανθρώπους που αγαπάνε την ταχύτητα!\n"
        "Πως μπορώ να σε βοηθήσω σήμερα;",
        subtitle=f"Project: [green]{config.PROJECT_ID}[/green]  |  Model: [yellow]{config.MODEL}[/yellow]",
        border_style="cyan",
    ))
    console.print("[dim]Type 'exit' or press Ctrl+C to quit.[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold blue]Εσύ:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            console.print("[dim]Goodbye![/dim]")
            break

        messages.append({"role": "user", "content": user_input})
        _log_turn("user", user_input)

        try:
            full_response = ""
            first_chunk   = True
            usage: dict   = {}

            with Live(
                Spinner("dots", text="[dim]Thinking...[/dim]"),
                console=console,
                refresh_per_second=10,
                transient=True,
            ) as live:
                for chunk in run_agent(messages, usage):
                    if first_chunk:
                        live.stop()
                        console.print("\n[bold green]Agent:[/bold green] ", end="")
                        first_chunk = False
                    full_response += chunk
                    console.print(chunk, end="", highlight=False)

            console.print()  # newline after streamed response

            # Re-render with Markdown if response contains code blocks
            if "```" in full_response:
                console.print(Markdown(full_response))

            # Usage summary
            in_tok  = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            cost    = usage.get("cost_usd", 0.0)
            console.print(
                f"[dim]  tokens: {in_tok:,} in / {out_tok:,} out  |  "
                f"cost: ${cost:.4f}[/dim]"
            )
            console.print()
            _log_turn("assistant", full_response)

        except Exception as e:
            console.print(f"\n[red]ERROR:[/red] {e}")
            # Remove the failed user message so history stays consistent
            messages.pop()


if __name__ == "__main__":
    main()
