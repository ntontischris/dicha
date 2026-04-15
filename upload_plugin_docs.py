"""Upload plugin reference docs to Supabase via the /docs/bulk webhook endpoint.

Usage:
    python upload_plugin_docs.py [--endpoint URL] [--secret SECRET] [--dry-run]

    --endpoint   Webhook base URL (default: $WEBHOOK_URL or http://localhost:8000)
    --secret     Webhook secret for X-Webhook-Secret header (default: $WEBHOOK_SECRET)
    --dry-run    Print chunks without uploading

The script reads all .md files from woo-agent/plugin_docs/, splits each file into
sections, and bulk-uploads them as global company docs with category="plugin_docs".
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

# Ensure stdout/stderr can handle Unicode on all platforms (e.g. Windows cp1253)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLUGIN_DOCS_DIR = Path(__file__).parent / "plugin_docs"
MAX_CHUNK_CHARS = 3000
MIN_CHUNK_CHARS = 100

# Woodmart-specific section delimiters
_WOODMART_MAJOR_RE = re.compile(
    r"^={6,}\s*\n\s*SECTION:\s*(.+?)\s*\n\s*={6,}",
    re.MULTILINE,
)
_WOODMART_MINOR_RE = re.compile(r"^[ \t]*---\s+(.+?)\s+---[ \t]*$", re.MULTILINE)

# Standard markdown: --- separators and ### headers
_MD_SEPARATOR_RE = re.compile(r"^---[ \t]*$", re.MULTILINE)
_MD_H3_RE = re.compile(r"^#{1,3}\s+(.+)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class DocChunk(NamedTuple):
    title: str
    content: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_doc_title(path: Path) -> str:
    """Convert filename to a human-readable title."""
    stem = path.stem.replace("-", " ").replace("_", " ")
    return stem.title()


def _sub_split(text: str, max_chars: int) -> list[str]:
    """Split oversized text first by paragraphs, then by hard character limit."""
    if len(text) <= max_chars:
        return [text]

    # Try splitting on blank lines (paragraphs)
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > max_chars and current_parts:
            chunks.append("\n\n".join(current_parts).strip())
            current_parts = []
            current_len = 0
        if para_len > max_chars:
            # Hard split the paragraph itself
            for i in range(0, para_len, max_chars):
                chunks.append(para[i : i + max_chars].strip())
        else:
            current_parts.append(para)
            current_len += para_len + 2  # +2 for "\n\n"

    if current_parts:
        chunks.append("\n\n".join(current_parts).strip())

    return [c for c in chunks if c]


def _make_chunks(doc_title: str, sections: list[tuple[str, str]]) -> list[DocChunk]:
    """Convert (section_name, section_text) pairs into DocChunk list.

    Ensures unique titles via part numbers and dedup counters.
    """
    chunks: list[DocChunk] = []
    title_counts: dict[str, int] = {}
    for section_name, section_text in sections:
        section_text = section_text.strip()
        if len(section_text) < MIN_CHUNK_CHARS:
            continue
        base_title = f"{doc_title} — {section_name}" if section_name else doc_title
        parts = [p.strip() for p in _sub_split(section_text, MAX_CHUNK_CHARS)
                 if len(p.strip()) >= MIN_CHUNK_CHARS]
        for i, part in enumerate(parts):
            title = f"{base_title} (part {i + 1})" if len(parts) > 1 else base_title
            if title in title_counts:
                title_counts[title] += 1
                title = f"{title} [{title_counts[title]}]"
            else:
                title_counts[title] = 1
            chunks.append(DocChunk(title=title, content=part))
    return chunks


# ---------------------------------------------------------------------------
# Per-file chunking strategies
# ---------------------------------------------------------------------------

def _chunk_woodmart(doc_title: str, text: str) -> list[DocChunk]:
    """Split on ====== SECTION: Name ====== major headers, then --- Sub --- minors."""
    major_splits = _WOODMART_MAJOR_RE.split(text)
    # split() with one capturing group gives: [pre, name1, body1, name2, body2, ...]
    sections: list[tuple[str, str]] = []

    # Leading text before first section (usually the file header)
    if major_splits[0].strip():
        sections.append(("Overview", major_splits[0]))

    # Pairs: (section_name, section_body)
    for i in range(1, len(major_splits) - 1, 2):
        section_name = major_splits[i].strip()
        section_body = major_splits[i + 1] if i + 1 < len(major_splits) else ""

        # Further split section_body on --- Subsection --- lines
        minor_splits = _WOODMART_MINOR_RE.split(section_body)
        if len(minor_splits) == 1:
            # No subsections
            sections.append((section_name, section_body))
        else:
            # Leading content of this section before first subsection
            if minor_splits[0].strip():
                sections.append((section_name, minor_splits[0]))
            # Subsection pairs
            for j in range(1, len(minor_splits) - 1, 2):
                sub_name = minor_splits[j].strip()
                sub_body = minor_splits[j + 1] if j + 1 < len(minor_splits) else ""
                full_name = f"{section_name} — {sub_name}"
                sections.append((full_name, sub_body))

    return _make_chunks(doc_title, sections)


def _chunk_standard(doc_title: str, text: str) -> list[DocChunk]:
    """Split on --- separators first, then on ### headers within each part."""
    # Step 1: split on horizontal rules
    hr_parts = _MD_SEPARATOR_RE.split(text)

    # Step 2: within each HR part, split on ### headers
    raw_sections: list[tuple[str, str]] = []
    for part in hr_parts:
        part = part.strip()
        if not part:
            continue
        h3_matches = list(_MD_H3_RE.finditer(part))
        if not h3_matches:
            raw_sections.append(("", part))
            continue
        # Text before the first header
        before = part[: h3_matches[0].start()].strip()
        if before:
            raw_sections.append(("", before))
        # Each header + its content
        for idx, match in enumerate(h3_matches):
            header = match.group(1).strip()
            start = match.end()
            end = h3_matches[idx + 1].start() if idx + 1 < len(h3_matches) else len(part)
            body = part[start:end].strip()
            raw_sections.append((header, body))

    # Merge anonymous leading sections into the first named one (or keep as Overview)
    sections: list[tuple[str, str]] = []
    for name, body in raw_sections:
        if not name:
            if sections and not sections[-1][0]:
                # Merge consecutive nameless parts
                prev_name, prev_body = sections.pop()
                sections.append(("", prev_body + "\n\n" + body))
            else:
                sections.append(("Overview" if not sections else "", body))
        else:
            sections.append((name, body))

    return _make_chunks(doc_title, sections)


def _chunk_file(path: Path) -> list[DocChunk]:
    """Dispatch to the right chunking strategy based on file content."""
    text = path.read_text(encoding="utf-8")
    doc_title = _derive_doc_title(path)

    if _WOODMART_MAJOR_RE.search(text):
        return _chunk_woodmart(doc_title, text)
    return _chunk_standard(doc_title, text)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def _build_payload(chunks: list[DocChunk]) -> dict:
    return {
        "project_id": "_global",
        "type": "company_doc",
        "category": "plugin_docs",
        "documents": [
            {
                "project_id": "_global",
                "type": "company_doc",
                "title": c.title,
                "content": c.content,
                "category": "plugin_docs",
            }
            for c in chunks
        ],
    }


def _upload(chunks: list[DocChunk], endpoint: str, secret: str | None) -> None:
    payload = _build_payload(chunks)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    url = endpoint.rstrip("/") + "/docs/bulk"
    print(f"  POST {url}  ({len(chunks)} chunks) ...", end=" ", flush=True)
    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=payload, headers=headers)
    if resp.status_code in (200, 201):
        print(f"OK ({resp.status_code})")
    else:
        print(f"FAILED ({resp.status_code})")
        print(f"  Response: {resp.text[:300]}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload plugin reference docs to Supabase via /docs/bulk."
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("WEBHOOK_URL", "http://localhost:8000"),
        help="Webhook base URL (default: $WEBHOOK_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--secret",
        default=os.environ.get("WEBHOOK_SECRET"),
        help="Webhook secret (default: $WEBHOOK_SECRET)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show chunks without uploading",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    md_files = sorted(PLUGIN_DOCS_DIR.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {PLUGIN_DOCS_DIR}", file=sys.stderr)
        sys.exit(1)

    all_chunks: list[DocChunk] = []

    for path in md_files:
        chunks = _chunk_file(path)
        print(f"{path.name}: {len(chunks)} chunks")
        if args.dry_run:
            for i, chunk in enumerate(chunks, 1):
                bar = "-" * 60
                print(f"  [{i}/{len(chunks)}] {chunk.title}")
                print(f"  {bar}")
                preview = chunk.content[:200].replace("\n", " ")
                if len(chunk.content) > 200:
                    preview += f"... ({len(chunk.content)} chars total)"
                print(f"  {preview}")
                print()
        all_chunks.extend(chunks)

    print(f"\nTotal: {len(all_chunks)} chunks from {len(md_files)} files")

    if args.dry_run:
        print("[dry-run] No upload performed.")
        return

    # Upload per-file to avoid huge batches
    print("\nUploading...")
    for path in md_files:
        file_chunks = _chunk_file(path)
        if file_chunks:
            _upload(file_chunks, args.endpoint, args.secret)

    print(f"\nDone. {len(all_chunks)} chunks uploaded across {len(md_files)} files.")


if __name__ == "__main__":
    main()
