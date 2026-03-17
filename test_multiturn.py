"""
Multi-turn test for WooCommerce Agent.
Tests Q2, Q4, Q6 with follow-up questions to see if quality improves.

Uses two-model strategy (TOOL_MODEL → ANSWER_MODEL) and project summary injection.
"""
from __future__ import annotations

import sys
import io
import json
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


def load_system_prompt() -> str:
    """Load system prompt with project summary injection (matches main.py/webhook.py)."""
    system_prompt = PROMPT_FILE.read_text(encoding="utf-8")

    # Inject project summary
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

    return system_prompt


def run_multiturn(question_id: str, turn1: str, turn2: str) -> dict:
    """Run a two-turn conversation using the two-model strategy."""
    system_prompt = load_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"[Project: {config.PROJECT_ID}]"},
        {"role": "user", "content": turn1},
    ]

    usage: dict = {}

    # Turn 1 — uses default two-model strategy (no model override)
    print(f"\n{'='*80}")
    print(f"  {question_id} — TURN 1")
    print(f"{'='*80}")
    print(f"Q: {turn1[:100]}...")

    answer1 = ""
    for chunk in run_agent(messages, usage):
        answer1 += chunk

    print(f"\n--- Answer (Turn 1) ---")
    print(answer1[:500])
    if len(answer1) > 500:
        print(f"... [{len(answer1)} chars total]")

    cost_t1 = usage.get("cost_usd", 0)
    print(f"\n[Cost after Turn 1: ${cost_t1:.4f}]")

    # Turn 2 — follow-up (uses same two-model strategy)
    messages.append({"role": "user", "content": turn2})

    print(f"\n{'='*80}")
    print(f"  {question_id} — TURN 2 (follow-up)")
    print(f"{'='*80}")
    print(f"Q: {turn2[:100]}...")

    answer2 = ""
    for chunk in run_agent(messages, usage):
        answer2 += chunk

    cost_total = usage.get("cost_usd", 0)
    print(f"\n--- Answer (Turn 2) ---")
    print(answer2[:500])
    if len(answer2) > 500:
        print(f"... [{len(answer2)} chars total]")

    print(f"\n[Total cost: ${cost_total:.4f} | Turn 2 cost: ${cost_total - cost_t1:.4f}]")
    print(f"[Tools used: {usage.get('tools_used', [])}]")

    return {
        "question_id": question_id,
        "turn1_answer": answer1,
        "turn2_answer": answer2,
        "usage": usage,
    }


# ── Test Questions ───────────────────────────────────────────────────────────

TESTS = {
    "Q2": {
        "turn1": "Στο eshop πρέπει να γίνει αντικαταβολή και τιμολόγιο μόνο στα 500€. Ελέγξτε ότι δεν χάθηκε αυτό",
        "turn2": "Βρήκες τον υπάρχοντα κώδικα που χειρίζεται τον περιορισμό αντικαταβολής; Μπορείς να μου δείξεις τι ακριβώς αλλάζεις στη function και γιατί; Επίσης, ο περιορισμός αντικαταβολής ισχύει μόνο για Θεσσαλονίκη.",
    },
    "Q4": {
        "turn1": "Δεν λειτουργεί σωστά ο υπολογισμός μεταφορικών εξόδων στη σελίδα του προϊόντος",
        "turn2": "Βρήκες ποιο snippet/plugin χειρίζεται τώρα τον shipping calculator στο product page; Δείξε μου τη function που είναι buggy και τι αλλαγή χρειάζεται.",
    },
    "Q6": {
        "turn1": "Στα πλακάκια τα μεταφορικά στην Αθήνα πρέπει να βγαίνουν 45€ ανεξαρτήτως ποσότητας. Τώρα βγαίνουν 54.99€. Ελέγξτε",
        "turn2": "Ποια function βρήκες που χειρίζεται τα μεταφορικά πλακιδίων; Δείξε μου τον υπάρχοντα κώδικα και τι ακριβώς αλλάζεις. Τα zone IDs της Αθήνας τα πήρες από το config;",
    },
}


if __name__ == "__main__":
    # Run specific test or all
    test_ids = sys.argv[1:] if len(sys.argv) > 1 else list(TESTS.keys())

    results = []
    for tid in test_ids:
        if tid not in TESTS:
            print(f"Unknown test: {tid} (available: {', '.join(TESTS.keys())})")
            continue
        t = TESTS[tid]
        result = run_multiturn(tid, t["turn1"], t["turn2"])
        results.append(result)

    # Save results
    out_file = Path(__file__).parent / "test_multiturn_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to {out_file}")

    # Summary
    print(f"\n\n{'='*80}")
    print("  MULTI-TURN SUMMARY")
    print(f"{'='*80}")
    total_cost = 0
    for r in results:
        cost = r["usage"].get("cost_usd", 0)
        total_cost += cost
        print(f"\n{r['question_id']}:")
        print(f"  Model: {r['usage'].get('model', '?')}")
        print(f"  Cost: ${cost:.4f}")
        print(f"  Tools: {r['usage'].get('tools_used', [])}")
        print(f"  Turn 1 length: {len(r['turn1_answer'])} chars")
        print(f"  Turn 2 length: {len(r['turn2_answer'])} chars")

    print(f"\nTotal cost: ${total_cost:.4f}")
