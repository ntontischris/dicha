"""Live agent verification suite for a synced shop (default: dicha-demo).

Re-runnable smoke/regression battery against the /chat endpoint. Each check has
assertions (must-contain / contain-any / must-NOT-contain); some run multiple
times to catch inconsistency. Prints a PASS/FAIL table + saves verify_report.txt.

Usage:
    1) start a server with current code:  python -m uvicorn webhook:app --port 8006
    2) AGENT_URL=http://localhost:8006 python verify_agent.py
Env overrides: AGENT_URL (default http://localhost:8006), VERIFY_PID (default dicha-demo).
"""

from __future__ import annotations

import os
import httpx
from pathlib import Path

HERE = Path(__file__).parent
env = {}
for line in (HERE / ".env").read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip()

SECRET = env.get("WEBHOOK_SECRET", "")
SUPA = env["SUPABASE_URL"]
KEY = env["SUPABASE_KEY"]
BASE = os.getenv("AGENT_URL", "http://localhost:8006")
PID = os.getenv("VERIFY_PID", "dicha-demo")
SB = {"apikey": KEY, "Authorization": "Bearer " + KEY}

out: list[str] = []


def log(*a):
    out.append(" ".join(str(x) for x in a))


def supa_get(path):
    return httpx.get(f"{SUPA}/rest/v1/{path}", headers=SB, timeout=20).json()


# --- pull real shop facts so assertions are data-driven where it matters ------
proj = supa_get(f"projects?project_id=eq.{PID}&select=wc_version,wp_version")
wc_ver = proj[0]["wc_version"] if proj else ""
wp_ver = proj[0]["wp_version"] if proj else ""
classes = [
    c["slug"] for c in supa_get(f"shipping_classes?project_id=eq.{PID}&select=slug")
]

# --- the battery --------------------------------------------------------------
# all: every needle present | any: each inner group needs >=1 | none: forbidden
# review=True -> diagnostic / open-ended (failure is informational, logs full reply)
TESTS = [
    dict(
        id="cod-max",
        repeat=3,
        q="Μέχρι ποιο ποσό παραγγελίας επιτρέπεται η αντικαταβολή;",
        any=[["μέχρι", "έως", "ανώτατο", "maximum", "πάνω από"]],
        none=[
            "ελάχιστο",
            "τουλάχιστον",
            "μόνο πάνω",
            "μόνο άνω",
            "only above",
            "minimum",
        ],
        note="Smart COD = MAX direction (regression: used to flip min/max)",
    ),
    dict(
        id="cod-settings",
        repeat=1,
        q="Τι ρυθμίσεις έχει αυτή τη στιγμή το Smart COD;",
        must_all=["1.21", "500"],
        none=["ελάχιστο 500", "τουλάχιστον"],
        note="extra fee 1.21 + 500 as max",
    ),
    dict(
        id="cod-restrictions",
        repeat=1,
        q="Υπάρχουν περιορισμοί στην αντικαταβολή, ανά περιοχή ή ποσό;",
        must_all=["500"],
        any=[["ζών", "zone", "περιοχ"], ["snippet", "dc_", "κώδικ"]],
        note="cross-references settings + custom code",
    ),
    dict(
        id="classes-list",
        repeat=2,
        q="Τι κατηγορίες αποστολής (shipping classes) υπάρχουν στο κατάστημα;",
        must_all=["plakakia", "megalo-epiplo", "mpaniera"],
        none=["epipla", "mpanieres"],
        note="real slugs, no invented epipla/mpanieres",
    ),
    dict(
        id="free-ship-code",
        repeat=2,
        q=(
            "Θέλω δωρεάν μεταφορικά για παραγγελίες άνω των 300€ στη χερσαία Ελλάδα "
            "(όχι νησιά), με εξαίρεση έπιπλα, πλακάκια και μπανιέρες. Γράψε τον κώδικα."
        ),
        any=[
            ["megalo-epiplo", "epiplo-mpaniou", "mesaio-epiplo"],
            ["plakakia", "plakakia-megalon-diastaseon"],
            ["mpaniera"],
        ],
        none=["epipla", "mpanieres"],
        note="generated code uses REAL class slugs (the headline fix)",
    ),
    dict(
        id="anti-invent",
        repeat=1,
        review=True,
        q="Γράψε κώδικα PHP που εξαιρεί τη shipping class «βιβλία» (books) από τα δωρεάν μεταφορικά.",
        none=[
            "'books'",
            '"books"',
            "`books`",
            "'vivlia'",
            "`vivlia`",
            "'βιβλία'",
            "'vivlio'",
        ],
        any=[
            ["δεν υπάρχ", "δεν βρ", "δεν εντοπ", "not found", "καμία", "δεν φαίνεται"]
        ],
        note="KNOWN-SOFT: must NOT fabricate a non-existent class slug (prompt-resistant)",
    ),
    dict(
        id="gateways",
        repeat=1,
        q="Ποιοι τρόποι πληρωμής είναι ενεργοί αυτή τη στιγμή στο κατάστημα;",
        any=[["viva"], ["αντικαταβ", "cod"]],
        note="real gateways (Viva + COD)",
    ),
    dict(
        id="config-versions",
        repeat=1,
        q="Τι έκδοση WooCommerce και WordPress τρέχει το κατάστημα;",
        any=[[v for v in (wc_ver, wp_ver) if v]],
        note=f"real versions from DB (wc={wc_ver}, wp={wp_ver})",
    ),
    dict(
        id="tax-display",
        repeat=1,
        review=True,
        q="Οι τιμές των προϊόντων εμφανίζονται με ΦΠΑ ή χωρίς ΦΠΑ;",
        note="DIAGNOSTIC: raw-value interpretation (Layer-2, not yet hardened)",
    ),
    # ── COMPLEX / realistic multi-factor scenarios (open-ended → review) ──────
    dict(
        id="cx-athens-overcharge",
        repeat=1,
        review=True,
        q=(
            "Σε μια παραγγελία χρεώθηκαν σωστά 45€ μεταφορικά για τα πλακάκια, αλλά "
            "χρεώθηκαν και 54,99€ για τα υπόλοιπα προϊόντα ενώ ο πελάτης είναι στην Αθήνα "
            "— θα έπρεπε να είναι 0€. Τι φταίει και πώς το διορθώνω;"
        ),
        any=[["dc_", "snippet", "plakakia", "ζών", "zone", "function"]],
        none=["epipla", "mpanieres"],
        note="COMPLEX: Athens over-charge diagnosis (real client case)",
    ),
    dict(
        id="cx-cod-invoice-600",
        repeat=1,
        review=True,
        q=(
            "Πελάτης ζήτησε τιμολόγιο και αντικαταβολή για παραγγελία 600€ και δεν του "
            "εμφανίζεται η αντικαταβολή. Γιατί συμβαίνει αυτό;"
        ),
        must_all=["500"],
        any=[["τιμολ", "invoice", "snippet", "dc_", "αντικαταβ"]],
        none=["ελάχιστο", "τουλάχιστον"],
        note="COMPLEX: COD disabled >500 (+ invoice rule)",
    ),
    dict(
        id="cx-multizone-freeship",
        repeat=1,
        review=True,
        q=(
            "Θέλω δωρεάν μεταφορικά: 500€ για όλη τη χερσαία Ελλάδα και 200€ για "
            "Θεσσαλονίκη, με εξαίρεση πλακάκια, έπιπλα και μπανιέρες. Τι πρέπει να αλλάξω "
            "σε ρυθμίσεις και κώδικα;"
        ),
        any=[
            ["plakakia"],
            ["megalo-epiplo", "epiplo-mpaniou", "mesaio-epiplo"],
            ["mpaniera"],
        ],
        none=["epipla", "mpanieres"],
        note="COMPLEX: multi-zone free shipping + real exclusion slugs",
    ),
    dict(
        id="cx-conflict-crossref",
        repeat=1,
        review=True,
        q=(
            "Ποιο είναι το πραγματικό όριο για δωρεάν μεταφορικά στην Αθήνα και από πού "
            "καθορίζεται — από ρύθμιση ή από κώδικα; Υπάρχει σύγκρουση;"
        ),
        any=[["snippet", "dc_", "κώδικ", "ρύθμ", "zone", "ζών", "flat_rate"]],
        note="COMPLEX: cross-reference settings vs custom code",
    ),
]


def ask(q):
    r = httpx.post(
        BASE + "/chat",
        headers={"X-Webhook-Secret": SECRET, "Content-Type": "application/json"},
        json={"project_id": PID, "message": q, "session_id": ""},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()


def check(reply, t):
    low = reply.lower()
    fails = []
    for n in t.get("must_all", []):
        if n.lower() not in low:
            fails.append(f"missing '{n}'")
    for group in t.get("any", []):
        if group and not any(n.lower() in low for n in group):
            fails.append(f"none of {group}")
    for n in t.get("none", []):
        if n.lower() in low:
            fails.append(f"FORBIDDEN '{n}'")
    return fails


# --- run ----------------------------------------------------------------------
log(f"AGENT VERIFY — project={PID} endpoint={BASE}")
log(f"shop facts: wc={wc_ver} wp={wp_ver} | shipping_classes in DB: {len(classes)}")
log("=" * 74)

summary = []
for t in TESTS:
    verdicts = []
    log(f"\n### [{t['id']}] {t['note']}")
    log(f"Q: {t['q']}")
    for run in range(t.get("repeat", 1)):
        try:
            d = ask(t["q"])
            reply = d.get("reply", "")
            fails = check(reply, t)
            ok = not fails
            verdicts.append(ok)
            tag = "PASS" if ok else "FAIL"
            log(
                f"  run{run + 1}: {tag} {('- ' + '; '.join(fails)) if fails else ''} | tools={d.get('tools_used')}"
            )
            cap = 1600 if t.get("review") else 280
            log("     reply: " + reply[:cap].replace("\n", " "))
        except Exception as e:
            verdicts.append(False)
            log(f"  run{run + 1}: ERROR {e!r}")
    if all(verdicts):
        v = "PASS"
    elif any(verdicts):
        v = "INCONSISTENT"
    else:
        v = "FAIL"
    if t.get("review"):
        v += " (review)"
    summary.append((t["id"], v))

log("\n" + "=" * 74)
log("SUMMARY")
for tid, v in summary:
    log(f"  {v:18} {tid}")

(HERE / "verify_report.txt").write_text("\n".join(out), encoding="utf-8")
print("DONE - wrote verify_report.txt")
