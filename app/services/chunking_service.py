"""Chunking: split page text into small overlapping pieces.

Why chunk at all? Embedding models represent a whole text as ONE vector.
A 40-page policy squeezed into one vector loses all detail, and retrieval
could only ever say "somewhere in this document". Small chunks give each
topic its own vector, so a question about diabetes matches the specific
paragraph about diabetes. See docs/chunking.md for the full discussion.

The algorithm here is a deliberately simple sliding window over characters:

    |------ chunk 1 ------|
                    |------ chunk 2 ------|
                                    |------ chunk 3 ------|
                    <-- overlap -->

- Window size and overlap come from settings (CHUNK_SIZE, CHUNK_OVERLAP).
- Windows are pulled back to the nearest space so words are never split.
- Chunks never cross page boundaries, so every chunk has ONE page number
  and citations stay exact.
"""

import re
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.services.pdf_service import PageText

logger = get_logger(__name__)

# Matches headings like "Section 3: Maternity Benefits" and captures the
# title: a run of Capitalized words. Capture stops at the first lowercase
# word or punctuation, so "Section 4: Exclusions apply here" yields
# "Exclusions", not the whole sentence.
SECTION_PATTERN = re.compile(
    r"Section\s+\d+\s*[:.\-]\s*([A-Z][A-Za-z&,\-]*(?:\s+[A-Z][A-Za-z&,\-]*)*)"
)


@dataclass(frozen=True)
class ChunkDraft:
    """A chunk with its citation metadata, before it is stored/embedded."""

    page_number: int
    section: str | None
    chunk_index: int
    content: str


def detect_section(page_text: str) -> str | None:
    """Best-effort section title for a page (e.g. 'Pre-existing Diseases').

    Simple heuristic on purpose: if the page contains a "Section N: Title"
    heading, use that title. Pages without one get None — the citation then
    falls back to just the page number.
    """
    match = SECTION_PATTERN.search(page_text)
    return match.group(1).strip() if match else None


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping chunks of at most `chunk_size` characters."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Pull the cut point back to the last space so words stay whole.
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        # Step forward, re-including `chunk_overlap` characters of the
        # previous chunk so sentences on the boundary appear in both.
        next_start = end - chunk_overlap
        # If that lands mid-word, widen the overlap back to the previous
        # space so the next chunk starts on a whole word.
        if next_start > 0 and text[next_start - 1] != " ":
            previous_space = text.rfind(" ", 0, next_start)
            if previous_space >= 0:
                next_start = previous_space + 1
        start = max(next_start, start + 1)
    return chunks


def chunk_pages(
    pages: list[PageText],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[ChunkDraft]:
    """Chunk every page of a document, keeping page/section metadata.

    `chunk_index` is a running counter across the whole document, preserving
    reading order.
    """
    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap

    drafts: list[ChunkDraft] = []
    index = 0
    for page in pages:
        section = detect_section(page.text)
        for content in chunk_text(page.text, size, overlap):
            drafts.append(
                ChunkDraft(
                    page_number=page.page_number,
                    section=section,
                    chunk_index=index,
                    content=content,
                )
            )
            index += 1

    logger.info(
        "Chunks created: pages=%d chunks=%d size=%d overlap=%d",
        len(pages),
        len(drafts),
        size,
        overlap,
    )
    return drafts
