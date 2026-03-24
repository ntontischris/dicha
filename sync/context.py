"""Contextual Retrieval: generate LLM context for each chunk before embedding.

Based on Anthropic's technique — reduces retrieval failures by ~49%.
Uses GPT-4o-mini for cost efficiency (~$0.0003 per chunk).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

import config

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert at WooCommerce code analysis. Your job is to write a short \
context summary (2-4 sentences) for a code/documentation chunk that will be \
used for search retrieval.

The context MUST include:
- What this code/doc is about (shipping, payments, checkout, etc.)
- What specific WooCommerce hooks or functions it uses
- What it does in plain language (Greek or English, match the content)
- The shop/project it belongs to (if mentioned)

Be specific and factual. Do NOT explain what the code does line by line. \
Focus on WHAT it is and WHY someone would search for it."""

_SETTINGS_SYSTEM_PROMPT = """\
You are an expert at WooCommerce configuration analysis. Your job is to write a short \
context summary (2-4 sentences) for a plugin/theme settings chunk that will be \
used for search retrieval.

The context MUST include:
- The plugin or theme name and what it does
- The KEY settings that affect store behavior (not all settings, just important ones)
- What the current values mean in plain language
- Which WooCommerce admin pages or hooks relate to these settings

Be specific about VALUES. Do NOT just list setting names — explain what they mean. \
Focus on WHAT the configuration does and WHY someone would search for it."""

_USER_TEMPLATE = """\
Full document title: {title}
Document type: {doc_type}
Project: {project_id}

--- FULL DOCUMENT CONTEXT ---
{full_text}

--- CHUNK TO CONTEXTUALIZE ---
{chunk_text}

Write a 2-4 sentence context summary for the chunk above."""


async def generate_context_for_chunk(
    client: AsyncOpenAI,
    chunk_text: str,
    full_text: str,
    title: str,
    doc_type: str,
    project_id: str,
) -> str:
    """Generate contextual summary for a single chunk."""
    user_msg = _USER_TEMPLATE.format(
        title=title,
        doc_type=doc_type,
        project_id=project_id,
        full_text=full_text[:4000],  # limit full doc context
        chunk_text=chunk_text[:2000],
    )

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=config.CONTEXT_MODEL,
                messages=[
                    {"role": "system", "content": _SETTINGS_SYSTEM_PROMPT if doc_type == "plugin_settings_doc" else _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=200,
                temperature=0,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            if attempt == 0:
                logger.warning("Context generation failed for '%s', retrying: %s", title, e)
                await asyncio.sleep(1)
            else:
                logger.error("Context generation failed permanently for '%s': %s", title, e)
                return ""
    return ""


async def generate_contexts_batch(
    client: AsyncOpenAI,
    chunks: list[dict],
    full_texts: dict[str, str],
    concurrency: int = 10,
) -> list[str]:
    """Generate context for multiple chunks with concurrency limit.

    Args:
        chunks: list of dicts with keys: text, title, type, project_id, source_id
        full_texts: mapping source_id -> full original text (for context)
        concurrency: max parallel LLM calls

    Returns:
        list of context strings aligned with input chunks
    """
    semaphore = asyncio.Semaphore(concurrency)
    results: list[str] = [""] * len(chunks)

    async def _process(idx: int, chunk: dict) -> None:
        async with semaphore:
            full_text = full_texts.get(chunk.get("source_id", ""), chunk["text"])
            ctx = await generate_context_for_chunk(
                client=client,
                chunk_text=chunk["text"],
                full_text=full_text,
                title=chunk.get("title", ""),
                doc_type=chunk.get("type", ""),
                project_id=chunk.get("project_id", ""),
            )
            results[idx] = ctx

    tasks = [_process(i, chunk) for i, chunk in enumerate(chunks)]
    await asyncio.gather(*tasks)

    generated = sum(1 for r in results if r)
    logger.info(
        "Generated context for %d/%d chunks (%.0f%%)",
        generated, len(chunks), (generated / max(len(chunks), 1)) * 100,
    )

    return results
