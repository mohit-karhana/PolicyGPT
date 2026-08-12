from pathlib import Path

import pytest

from app.core.exceptions import InvalidPdfError
from app.services import pdf_service
from tests.pdf_factory import make_pdf


def write_pdf(tmp_path: Path, pages: list[str]) -> str:
    path = tmp_path / "test.pdf"
    path.write_bytes(make_pdf(pages))
    return str(path)


def test_extract_pages_is_page_aware(tmp_path: Path) -> None:
    path = write_pdf(
        tmp_path,
        ["Diabetes is covered after 24 months.", "Maternity waiting period is 36 months."],
    )

    pages = pdf_service.extract_pages(path)

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "Diabetes is covered" in pages[0].text
    assert pages[1].page_number == 2
    assert "Maternity waiting period" in pages[1].text


def test_extract_pages_keeps_empty_pages(tmp_path: Path) -> None:
    """Pages without text (e.g. scans) must not shift page numbering."""
    path = write_pdf(tmp_path, ["First page text", "", "Third page text"])

    pages = pdf_service.extract_pages(path)

    assert len(pages) == 3
    assert pages[1].text == ""
    assert pages[2].page_number == 3


def test_extract_pages_multiline_text(tmp_path: Path) -> None:
    path = write_pdf(tmp_path, ["Room rent limit:\n2% of sum insured per day"])

    pages = pdf_service.extract_pages(path)

    assert "Room rent limit: 2% of sum insured per day" in pages[0].text


def test_extract_pages_tolerates_junk_before_header(tmp_path: Path) -> None:
    """Stray bytes before %PDF shift all xref offsets; stripping them must
    restore parseability (real-world case: some insurer PDFs)."""
    path = tmp_path / "junk-prefix.pdf"
    path.write_bytes(b"\n\n\r\n\r" + make_pdf(["Diabetes is covered."]))

    pages = pdf_service.extract_pages(str(path))

    assert len(pages) == 1
    assert "Diabetes is covered" in pages[0].text


def test_extract_pages_rejects_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.4 this is not really a pdf")

    with pytest.raises(InvalidPdfError):
        pdf_service.extract_pages(str(path))


class TestCleanText:
    def test_collapses_whitespace(self) -> None:
        assert pdf_service.clean_text("too   many    spaces") == "too many spaces"

    def test_joins_hyphenated_line_breaks(self) -> None:
        assert pdf_service.clean_text("cover-\nage details") == "coverage details"

    def test_newlines_become_spaces(self) -> None:
        assert pdf_service.clean_text("line one\nline two") == "line one line two"

    def test_removes_control_characters(self) -> None:
        assert pdf_service.clean_text("text\x00with\x0cjunk") == "textwithjunk"

    def test_strips_edges(self) -> None:
        assert pdf_service.clean_text("  padded  ") == "padded"
