"""PDF text extraction and cleaning.

Extraction is page-aware: we keep (page_number, text) pairs instead of one
big string, because citations later must point to a page ("Page 18 —
Pre-existing Diseases"). If pages were merged here, that provenance would be
unrecoverable.
"""

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.exceptions import InvalidPdfError
from app.core.logging import get_logger

logger = get_logger(__name__)

PDF_HEADER = b"%PDF-"


def _open_pdf(file_path: str) -> PdfReader:
    """Open a PDF, tolerating junk bytes before the %PDF header.

    Some real-world PDFs are prefixed with stray bytes (e.g. newlines added
    by a download or export tool). That prefix shifts every byte offset in
    the file, which breaks the xref table the parser relies on. Stripping
    the prefix restores the original offsets.
    """
    with open(file_path, "rb") as f:
        data = f.read()

    header_at = data.find(PDF_HEADER, 0, 1024)
    if header_at == -1:
        raise InvalidPdfError("No %PDF header found in file")
    if header_at > 0:
        logger.warning(
            "Stripping %d junk bytes before PDF header: file=%s", header_at, file_path
        )
        data = data[header_at:]

    return PdfReader(io.BytesIO(data))


@dataclass(frozen=True)
class PageText:
    """Extracted text of one PDF page (1-based page numbers)."""

    page_number: int
    text: str


def extract_pages(file_path: str) -> list[PageText]:
    """Extract text from every page of a PDF, preserving page numbers.

    Pages that contain no extractable text (e.g. scanned images) yield an
    empty string; they are kept so page numbering stays correct.
    """
    try:
        reader = _open_pdf(file_path)
        pages = [
            PageText(page_number=i, text=clean_text(page.extract_text() or ""))
            for i, page in enumerate(reader.pages, start=1)
        ]
    except PdfReadError as exc:
        raise InvalidPdfError(f"Could not read PDF: {exc}") from exc

    logger.info(
        "Pages extracted: file=%s pages=%d empty_pages=%d",
        file_path,
        len(pages),
        sum(1 for p in pages if not p.text),
    )
    return pages


def clean_text(text: str) -> str:
    """Normalize raw PDF text so chunking and embedding work on clean input.

    PDF extraction produces artifacts: stray control characters, words
    hyphen-split across line breaks, and erratic whitespace. Each step below
    fixes one of those, and nothing more — cleaning must never change the
    meaning of policy text.
    """
    # Remove control characters (except newlines, which we handle next).
    text = re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", "", text)
    # Re-join words that were hyphenated across a line break: "cover-\nage".
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Line breaks inside a paragraph become spaces.
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    # Collapse runs of whitespace.
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
