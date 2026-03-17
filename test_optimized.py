"""Test the optimized agent directly (no webhook needed).

Runs 8 test questions covering all agent capabilities:
  Q1: Config lookup (should cost < $0.005, 1 round)
  Q2: Free shipping (Round 2 should see functions/hooks from Round 1)
  Q3: Hook lookup (search_by_hook for woocommerce_package_rates)
  Q4: Checkout custom code (2 rounds max, investigation state shows findings)
  Q5: Docs search (company docs, not code)
  Q6: Salesforce (honesty test — should not fabricate)
  Q7: Bug diagnosis (shipping methods missing)
  Q8: Code generation (hide Company field)

Usage:
  python test_optimized.py              # Run all 8 tests once
  python test_optimized.py --runs 3     # Run all 8 tests 3x for consistency
  python test_optimized.py Q1 Q4        # Run specific tests
  python test_optimized.py Q4 --runs 3  # Specific tests, 3 runs each
"""

from __future__ import annotations

import argparse
import json
import sys
import io
import time
from pathlib import Path

# Force UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import config
config.PROJECT_ID = "dicha-demo"

from agent import run_agent

PROMPT_FILE = Path(__file__).parent / "prompts" / "system_prompt.md"

TESTS = [
    {
        "id": 1,
        "category": "Config Lookup",
        "question": "Τι εκδόσεις WordPress, WooCommerce και PHP τρέχει αυτό το shop;",
        "criteria": "Should answer from SHOP CONTEXT, 0-1 tool calls, < $0.01",
    },
    {
        "id": 2,
        "category": "Code Search (shipping)",
        "question": "Πώς λειτουργεί η δωρεάν αποστολή σε αυτό το eshop; Ποιος κώδικας την ελέγχει;",
        "criteria": "Round 2 must see functions/hooks from Round 1. Investigation state.",
    },
    {
        "id": 3,
        "category": "Hook Lookup",
        "question": "Ποιος κώδικας χρησιμοποιεί το hook woocommerce_package_rates;",
        "criteria": "Must use search_by_hook. Should show exact snippets using this hook.",
    },
    {
        "id": 4,
        "category": "Complex (multi-tool)",
        "question": "Υπάρχει custom κώδικας που αλλάζει τη συμπεριφορά του checkout; Δείξε μου τι κάνει.",
        "criteria": "Max 2 rounds, investigation state shows findings, < $0.10",
    },
    {
        "id": 5,
        "category": "Docs Search",
        "question": "Υπάρχει documentation για το πώς στήνουμε shipping zones στο WooCommerce;",
        "criteria": "Should search for company docs or answer from SHOP CONTEXT. Not just generic WC advice.",
    },
    {
        "id": 6,
        "category": "No Results (honesty)",
        "question": "Πώς λειτουργεί το integration με το Salesforce σε αυτό το shop;",
        "criteria": "Must NOT fabricate. Say nothing found.",
    },
    {
        "id": 7,
        "category": "Bug Diagnosis",
        "question": "Ένας πελάτης λέει ότι δεν εμφανίζονται shipping methods στο checkout. Τι μπορεί να φταίει;",
        "criteria": "Should check config + search code for shipping customizations. Specific diagnosis.",
    },
    {
        "id": 8,
        "category": "Code Generation",
        "question": "Γράψε μου κώδικα που κρύβει το πεδίο 'Company' από το checkout αν ο πελάτης είναι ιδιώτης.",
        "criteria": "Should search existing checkout code first, then generate compatible code.",
    },
]

# Build lookup for filtering by ID
_TESTS_BY_ID = {f"Q{t['id']}": t for t in TESTS}


def build_messages(question: str) -> list[dict]:
    """Build message list with static system prompt + project summary injection."""
    system_prompt = PROMPT_FILE.read_text(encoding="utf-8")

    # Inject project summary (same as main.py/chatbot.py/webhook.py)
    try:
        import httpx as _httpx
        _headers = {"apikey": config.SUPABASE_KEY, "Authorization": f"Bearer {config.SUPABASE_KEY}"}
        _r = _httpx.get(
            f"{config.SUPABASE_URL}/rest/v1/projects?project_id=eq.{config.PROJECT_ID}&select=summary_text",
            headers=_headers, timeout=5,
        )
        _rows = _r.json() if _r.status_code == 200 else []
        _summary = _rows[0].get("summary_text", "") if _rows else ""
        if _summary:
            system_prompt += f"\n\n## SHOP CONTEXT (auto-injected)\n{_summary}"
    except Exception:
        pass

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"[Project: {config.PROJECT_ID}]"},
        {"role": "user", "content": question},
    ]


def run_single_test(test: dict) -> dict:
    """Run a single test and return result dict."""
    messages = build_messages(test["question"])
    usage: dict = {}

    start = time.time()
    full_response = ""
    try:
        for chunk in run_agent(messages, usage):
            full_response += chunk
            print(chunk, end="", flush=True)
    except Exception as e:
        print(f"\nERROR: {e}")
        full_response = f"ERROR: {e}"

    elapsed = time.time() - start

    print(f"\n\n--- METRICS ---")
    print(f"Model: {usage.get('model', '?')}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Cost: ${usage.get('cost_usd', 0.0):.4f}")
    print(f"Tokens: {usage.get('input_tokens', 0):,} in + {usage.get('output_tokens', 0):,} out")
    print(f"Tools: {usage.get('tools_used', [])}")
    print(f"Response length: {len(full_response)} chars")

    return {
        "test": test["id"],
        "category": test["category"],
        "question": test["question"],
        "criteria": test["criteria"],
        "tools_used": usage.get("tools_used", []),
        "model": usage.get("model", "?"),
        "reply": full_response,
        "time_s": round(elapsed, 1),
        "cost_usd": usage.get("cost_usd", 0.0),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


def run_tests(tests: list[dict], num_runs: int = 1) -> list[dict]:
    all_results: list[dict] = []

    for run_idx in range(num_runs):
        if num_runs > 1:
            print(f"\n{'#'*70}")
            print(f"  RUN {run_idx + 1}/{num_runs}")
            print(f"{'#'*70}")

        for test in tests:
            print(f"\n{'='*70}")
            print(f"TEST Q{test['id']}: {test['category']}" + (f" (run {run_idx + 1})" if num_runs > 1 else ""))
            print(f"Q: {test['question']}")
            print(f"Criteria: {test['criteria']}")
            print(f"{'='*70}")

            result = run_single_test(test)
            result["run"] = run_idx + 1
            all_results.append(result)

    # Save results
    out_file = Path(__file__).parent / "test_optimized_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n\nResults saved to {out_file}")

    # Summary table
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    if num_runs == 1:
        total_cost = 0.0
        for r in all_results:
            cost = r.get("cost_usd", 0)
            total_cost += cost
            print(f"  Q{r['test']:1d} ({r['category']:<25s}): ${cost:.4f} | {r['time_s']:5.1f}s | {r.get('input_tokens',0):>7,} tok | tools: {r.get('tools_used', [])}")
        print(f"\n  TOTAL COST: ${total_cost:.4f}")
        print(f"  AVG COST/QUERY: ${total_cost / len(all_results):.4f}")
    else:
        # Group by test ID and show min/max/avg for consistency analysis
        from collections import defaultdict
        by_test: dict[int, list[dict]] = defaultdict(list)
        for r in all_results:
            by_test[r["test"]].append(r)

        total_cost = sum(r.get("cost_usd", 0) for r in all_results)
        print(f"  {'Test':<30s} {'Min':>6s} {'Max':>6s} {'Avg':>6s} {'Max/Min':>8s} {'Avg$':>8s}")
        print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*6} {'-'*8} {'-'*8}")

        for test_id in sorted(by_test.keys()):
            runs = by_test[test_id]
            times = [r["time_s"] for r in runs]
            costs = [r["cost_usd"] for r in runs]
            cat = runs[0]["category"]
            min_t, max_t, avg_t = min(times), max(times), sum(times) / len(times)
            ratio = max_t / min_t if min_t > 0 else float("inf")
            avg_cost = sum(costs) / len(costs)
            print(f"  Q{test_id} ({cat:<25s}): {min_t:5.1f}s {max_t:5.1f}s {avg_t:5.1f}s {ratio:7.1f}x ${avg_cost:.4f}")

        print(f"\n  TOTAL COST ({num_runs} runs): ${total_cost:.4f}")
        print(f"  AVG COST/QUERY: ${total_cost / len(all_results):.4f}")

    return all_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test optimized WooCommerce agent")
    parser.add_argument("tests", nargs="*", help="Test IDs to run (e.g. Q1 Q4). Default: all.")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs per test for consistency (default: 1)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Filter tests if specific IDs given
    if args.tests:
        selected = []
        for tid in args.tests:
            key = tid.upper() if tid.upper().startswith("Q") else f"Q{tid}"
            if key in _TESTS_BY_ID:
                selected.append(_TESTS_BY_ID[key])
            else:
                print(f"Unknown test: {tid} (available: {', '.join(sorted(_TESTS_BY_ID.keys()))})")
                sys.exit(1)
        run_tests(selected, num_runs=args.runs)
    else:
        run_tests(TESTS, num_runs=args.runs)
