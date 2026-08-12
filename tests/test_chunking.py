import pytest

from app.services.chunking_service import (
    chunk_pages,
    chunk_text,
    detect_section,
)
from app.services.pdf_service import PageText


class TestChunkText:
    def test_respects_max_size(self) -> None:
        text = "word " * 300  # 1500 chars
        chunks = chunk_text(text, chunk_size=500, chunk_overlap=100)

        assert all(len(c) <= 500 for c in chunks)
        assert len(chunks) > 1

    def test_short_text_is_single_chunk(self) -> None:
        assert chunk_text("short text", chunk_size=500, chunk_overlap=100) == ["short text"]

    def test_empty_text_gives_no_chunks(self) -> None:
        assert chunk_text("   ", chunk_size=500, chunk_overlap=100) == []

    def test_consecutive_chunks_overlap(self) -> None:
        text = " ".join(f"w{i}" for i in range(200))
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=30)

        for previous, current in zip(chunks, chunks[1:]):
            # The tail of one chunk reappears at the head of the next, so
            # sentences cut at a boundary survive in at least one chunk.
            tail_word = previous.split()[-1]
            assert tail_word in current.split()

    def test_does_not_split_words(self) -> None:
        text = " ".join(["supercalifragilistic"] * 50)
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)

        for chunk in chunks:
            for word in chunk.split():
                assert word == "supercalifragilistic"

    def test_no_content_is_lost(self) -> None:
        text = " ".join(f"w{i}" for i in range(500))
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)

        seen = set()
        for chunk in chunks:
            seen.update(chunk.split())
        assert seen == set(text.split())

    def test_overlap_must_be_smaller_than_size(self) -> None:
        with pytest.raises(ValueError):
            chunk_text("some text", chunk_size=100, chunk_overlap=100)


class TestChunkPages:
    def test_keeps_page_numbers_and_global_index(self) -> None:
        pages = [
            PageText(page_number=1, text="a " * 400),
            PageText(page_number=2, text="b " * 400),
        ]
        drafts = chunk_pages(pages, chunk_size=300, chunk_overlap=50)

        assert {d.page_number for d in drafts} == {1, 2}
        assert [d.chunk_index for d in drafts] == list(range(len(drafts)))
        # Chunks never span pages.
        for draft in drafts:
            assert set(draft.content.split()) <= ({"a"} if draft.page_number == 1 else {"b"})

    def test_detects_sections(self) -> None:
        pages = [
            PageText(page_number=1, text="Section 2: Pre-existing Diseases. Diabetes is covered after 24 months."),
            PageText(page_number=2, text="No heading on this page."),
        ]
        drafts = chunk_pages(pages, chunk_size=500, chunk_overlap=100)

        assert drafts[0].section == "Pre-existing Diseases"
        assert drafts[-1].section is None

    def test_skips_empty_pages(self) -> None:
        pages = [PageText(page_number=1, text=""), PageText(page_number=2, text="content")]
        drafts = chunk_pages(pages, chunk_size=500, chunk_overlap=100)

        assert len(drafts) == 1
        assert drafts[0].page_number == 2


def test_detect_section_variants() -> None:
    assert detect_section("Section 4: Exclusions apply here") == "Exclusions"
    assert detect_section("Section 12 - Maternity Benefits and more") == "Maternity Benefits"
    assert detect_section("no heading at all") is None
