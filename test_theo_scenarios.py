"""Test suite based on Theo's feedback — verifies agent behavior improvements.

Run: python test_theo_scenarios.py

Tests:
  1. Read plugin settings (Smart COD)
  2. Prefer plugin solution over code (COD fee)
  3. Source attribution (WHERE code was found)
  4. Caching bug → WP Rocket (not random code)
  5. Theme capabilities (Woodmart shipping bar)
  6. Cross-reference settings + code (shipping diagnosis)
  7. Multi-turn context retention
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
from tools import get_shop_config
from agent import run_agent


def _run_scenario(
    name: str,
    question: str,
    checks: list[tuple[str, str]],
    project_id: str = "dicha-demo",
    follow_up: str | None = None,
) -> dict:
    """Run a single scenario and check assertions."""
    config.set_project_id(project_id)
    prompt = Path("prompts/system_prompt.md").read_text(encoding="utf-8")
    summary = get_shop_config()
    prompt += f"\n\n## SHOP CONTEXT (auto-injected)\n{summary}"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]

    usage: dict = {}
    answer = ""
    for chunk in run_agent(messages, usage):
        answer = chunk

    # Run follow-up if provided
    follow_up_answer = ""
    if follow_up:
        messages.append({"role": "user", "content": follow_up})
        for chunk in run_agent(messages, usage):
            follow_up_answer = chunk

    text_to_check = (answer + " " + follow_up_answer).lower()
    results = []
    for check_name, keyword in checks:
        passed = keyword.lower() in text_to_check
        results.append({"check": check_name, "keyword": keyword, "passed": passed})

    all_passed = all(r["passed"] for r in results)
    return {
        "name": name,
        "passed": all_passed,
        "checks": results,
        "tools": usage.get("tools_used", []),
        "cost": usage.get("cost_usd", 0),
        "answer_preview": answer[:300],
    }


SCENARIOS = [
    {
        "name": "1. Read Smart COD settings",
        "question": "Μπορείς να δεις αν υπάρχει plugin που επηρεάζει την αντικαταβολή και να διαβάσεις τις ρυθμίσεις του;",
        "checks": [
            ("Mentions Smart COD", "smart cod"),
            ("Finds cart_amount_restriction", "500"),
            ("Finds restrictions", "restriction"),
            ("Has source attribution", "[plugin"),
        ],
    },
    {
        "name": "2. Prefer plugin over code (COD fee)",
        "question": "Πώς μπορώ να προσθέσω κόστος στην αντικαταβολή;",
        "checks": [
            ("Suggests Smart COD plugin", "smart cod"),
            ("Mentions extra_fee setting", "extra_fee"),
            ("Does NOT lead with custom PHP", "add_action"),  # Should NOT contain this - inverted check below
        ],
    },
    {
        "name": "3. Source attribution (snippet location)",
        "question": "Πώς δουλεύει ο μηχανισμός υπολογισμού μεταφορικών για πλακάκια;",
        "checks": [
            ("Mentions function name", "dc_add_plakakia"),
            ("Has source: snippet or functions.php", "snippet"),
            ("Mentions shipping class", "plakakia"),
        ],
    },
    {
        "name": "4. Caching bug → WP Rocket",
        "question": "Μετά από αλλαγές στο site μου, οι πελάτες βλέπουν παλιές τιμές στα προϊόντα. Τι μπορεί να φταίει;",
        "checks": [
            ("Mentions WP Rocket / cache", "rocket"),
            ("Suggests clearing cache", "cache"),
        ],
    },
    {
        "name": "5. Theme capability (shipping bar)",
        "question": "Θέλω να εμφανίσω μια μπάρα που δείχνει πόσο λείπει για δωρεάν μεταφορικά. Γίνεται μέσω του theme;",
        "checks": [
            ("Mentions Woodmart shipping bar feature", "shipping progress bar"),
            ("Gives admin path", "theme options"),
            ("Does NOT write custom PHP", "add_action"),  # inverted
        ],
    },
    {
        "name": "6. Cross-reference settings + code",
        "question": "Τα μεταφορικά στη Θεσσαλονίκη φαίνεται να μην λειτουργούν σωστά. Μπορείς να ελέγξεις;",
        "checks": [
            ("Finds shipping zone settings", "zone"),
            ("Finds custom code", "dc_"),
            ("Has source attribution", "["),
        ],
    },
    {
        "name": "7. Multi-turn: COD follow-up",
        "question": "Τι ρυθμίσεις έχει η αντικαταβολή στο eshop μου;",
        "follow_up": "Υπάρχουν περιορισμοί ανά περιοχή;",
        "checks": [
            ("First answer has COD settings", "restriction"),
            ("Follow-up finds zone restriction", "zone"),
        ],
    },
]


def main() -> None:
    print("=" * 70)
    print("THEO'S FEEDBACK TEST SUITE")
    print("=" * 70)

    results = []
    total_cost = 0.0

    for scenario in SCENARIOS:
        name = scenario["name"]
        print(f"\n--- {name} ---")
        print(f"Q: {scenario['question'][:80]}...")

        t0 = time.time()
        result = _run_scenario(
            name=name,
            question=scenario["question"],
            checks=scenario["checks"],
            follow_up=scenario.get("follow_up"),
        )
        elapsed = time.time() - t0

        # Invert checks for "should NOT contain" patterns
        for check in result["checks"]:
            if check["keyword"] == "add_action":
                # These are inverted: PASS if NOT found
                check["passed"] = not check["passed"]
                check["check"] += " (inverted: should NOT appear)"

        all_passed = all(c["passed"] for c in result["checks"])
        result["passed"] = all_passed
        result["time_s"] = round(elapsed, 1)
        total_cost += result["cost"]

        status = "PASS" if all_passed else "FAIL"
        print(f"  {status} | Tools: {result['tools']} | Cost: ${result['cost']:.4f} | Time: {elapsed:.1f}s")
        for check in result["checks"]:
            mark = "v" if check["passed"] else "X"
            print(f"    [{mark}] {check['check']}")

        results.append(result)

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} passed | Total cost: ${total_cost:.4f}")
    print("=" * 70)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['name']} (${r['cost']:.4f}, {r.get('time_s', '?')}s)")

    # Save results
    out_path = Path("test_theo_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nDetailed results saved to {out_path}")


if __name__ == "__main__":
    main()
