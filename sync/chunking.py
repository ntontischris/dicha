"""Text chunking utilities for code and documentation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A text chunk with metadata about its position."""

    name: str
    text: str
    index: int = 0
    total: int = 1


# -- PHP function splitter --------------------------------------------

_FUNC_PATTERN = re.compile(
    r"(?:/\*\*[\s\S]*?\*/\s*)?"
    r"(?:(?:public|private|protected|static)\s+)*"
    r"function\s+(\w+)\s*\([^)]*\)\s*\{",
)


def split_php_functions(code: str) -> list[Chunk]:
    """Split PHP code into individual function blocks.

    Falls back to size-based splitting if no functions found.
    """
    matches = list(_FUNC_PATTERN.finditer(code))

    if not matches:
        raw = split_by_size(code, max_chars=2000)
        return [
            Chunk(name=f"section_{i+1}", text=c, index=i, total=len(raw))
            for i, c in enumerate(raw)
        ]

    chunks: list[Chunk] = []

    # Header before first function (hooks, requires, etc.)
    if matches[0].start() > 100:
        header = code[: matches[0].start()].strip()
        if header:
            chunks.append(Chunk(name="header_and_hooks", text=header))

    # Each function block
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(code)
        block = code[start:end].strip()
        if block:
            chunks.append(Chunk(name=match.group(1), text=block))

    # Set index/total
    for i, chunk in enumerate(chunks):
        chunk.index = i
        chunk.total = len(chunks)

    return chunks


# -- Markdown heading splitter ----------------------------------------

_HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def split_markdown(text: str, max_chars: int = 2000) -> list[Chunk]:
    """Split markdown by ## headings, preserving parent heading as context.

    Each chunk gets the top-level heading prepended for embedding context.
    Large sections are sub-split by size.
    """
    headings = list(_HEADING_PATTERN.finditer(text))

    if not headings:
        raw = split_by_size(text, max_chars)
        return [
            Chunk(name=f"section_{i+1}", text=c, index=i, total=len(raw))
            for i, c in enumerate(raw)
        ]

    # Find the top-level heading (fewest #)
    min_level = min(len(m.group(1)) for m in headings)
    parent_heading = ""
    for m in headings:
        if len(m.group(1)) == min_level:
            parent_heading = m.group(0)
            break

    chunks: list[Chunk] = []

    # Content before first heading
    pre = text[: headings[0].start()].strip()
    if pre and len(pre) > 30:
        chunks.append(Chunk(name="introduction", text=pre))

    # Each heading section
    for i, heading in enumerate(headings):
        start = heading.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        section = text[start:end].strip()

        if not section or len(section) < 10:
            continue

        heading_text = heading.group(2)

        # If section is too large, sub-split
        if len(section) > max_chars:
            sub_chunks = split_by_size(section, max_chars)
            for j, sub in enumerate(sub_chunks):
                name = f"{heading_text} (part {j+1})" if len(sub_chunks) > 1 else heading_text
                # Prepend parent heading for context
                ctx = f"{parent_heading}\n\n{sub}" if parent_heading not in sub else sub
                chunks.append(Chunk(name=name, text=ctx))
        else:
            # Prepend parent heading if this isn't the parent itself
            ctx = f"{parent_heading}\n\n{section}" if parent_heading not in section else section
            chunks.append(Chunk(name=heading_text, text=ctx))

    for i, chunk in enumerate(chunks):
        chunk.index = i
        chunk.total = len(chunks)

    return chunks


# -- Size-based splitter (universal fallback) -------------------------

def split_by_size(text: str, max_chars: int = 2000) -> list[str]:
    """Split text into chunks of ~max_chars, breaking at newlines."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        # Find last newline before max_chars
        break_point = remaining.rfind("\n", 0, max_chars)

        # If no good newline, force cut
        if break_point < max_chars * 0.3:
            break_point = max_chars

        chunks.append(remaining[:break_point])
        remaining = remaining[break_point:].lstrip("\n")

    return [c for c in chunks if c.strip()]


# -- Helpers -----------------------------------------------------------

def truncate_text(text: str, max_chars: int = 8000) -> str:
    """Hard truncate at max_chars."""
    return text[:max_chars] if len(text) > max_chars else text


def is_valid_chunk(text: str, min_chars: int = 10) -> bool:
    """Check if a chunk has enough content to be worth embedding."""
    return len(text.strip()) >= min_chars
