"""One-time upload of plugin reference docs as company docs."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

DOCS_DIR = Path(__file__).parent.parent.parent / "plugin"

FILES = [
    ("wc-smart-cod.md", "WC Smart COD - Settings Reference", "payments"),
    ("wc-cash-on-pickup.md", "WC Cash on Pickup - Settings Reference", "payments"),
    ("weight-based-shipping-for-woocommerce.md", "Weight-Based Shipping - Settings Reference", "shipping"),
    ("wp-rocket.md", "WP Rocket - Settings Reference", "performance"),
    ("woodmart_settings_report (1).txt", "Woodmart Theme - Settings Reference", "theme"),
]


def main() -> None:
    documents = []
    for filename, title, category in FILES:
        path = DOCS_DIR / filename
        if not path.exists():
            print(f"SKIP: {filename} not found")
            continue
        content = path.read_text(encoding="utf-8")
        documents.append({
            "project_id": "_global",
            "type": "company_doc",
            "title": title,
            "content": content,
            "category": category,
        })
        print(f"  OK: {title} ({len(content)} chars)")

    if not documents:
        print("No documents to upload")
        sys.exit(1)

    payload = {
        "project_id": "_global",
        "type": "company_doc",
        "category": "general",
        "documents": documents,
    }

    headers = {}
    if WEBHOOK_SECRET:
        headers["Authorization"] = f"Bearer {WEBHOOK_SECRET}"

    print(f"\nUploading {len(documents)} docs to {WEBHOOK_URL}/docs/bulk ...")
    r = httpx.post(f"{WEBHOOK_URL}/docs/bulk", json=payload, headers=headers, timeout=120)
    r.raise_for_status()
    print(f"Result: {r.json()}")


if __name__ == "__main__":
    main()
