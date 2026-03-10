"""One-time re-ingest script for existing docs after source_id migration.

After deploying the hash-based source_id fix (P1-1), existing docs have old
source_ids (doc-{title[:50]}-parent). This script triggers re-ingestion via
the /api/re-ingest endpoint for all projects + _global docs.

Usage:
    python re_ingest_docs.py

Requires:
    SUPABASE_URL, SUPABASE_KEY, and the webhook service running.
"""

from __future__ import annotations

import logging
import os
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    base_url = os.getenv("WEBHOOK_URL", "http://localhost:8000")
    secret = os.getenv("WEBHOOK_SECRET", "")
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {secret}",
        "X-Webhook-Secret": secret,
    }

    sb_headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    # 1. Fetch all project_ids from Supabase
    with httpx.Client(timeout=30) as client:
        r = client.get(
            f"{supabase_url}/rest/v1/projects?select=project_id",
            headers=sb_headers,
        )
        r.raise_for_status()
        projects = [p["project_id"] for p in r.json()]

    # Always include _global
    all_ids = ["_global"] + projects
    logger.info("Re-ingesting %d targets: %s", len(all_ids), all_ids)

    # 2. Call /api/re-ingest for each
    with httpx.Client(timeout=120) as client:
        for pid in all_ids:
            logger.info("Re-ingesting: %s", pid)
            try:
                r = client.post(
                    f"{base_url}/api/re-ingest?project_id={pid}",
                    headers=headers,
                )
                r.raise_for_status()
                result = r.json()
                logger.info(
                    "  Done: %d docs found → %d rows created",
                    result.get("docs_found", 0),
                    result.get("rows_created", 0),
                )
            except httpx.HTTPStatusError as e:
                logger.error("  Failed for %s: %d %s", pid, e.response.status_code, e.response.text[:200])
            except Exception as e:
                logger.error("  Error for %s: %s", pid, e)

    logger.info("Re-ingestion complete.")


if __name__ == "__main__":
    main()
