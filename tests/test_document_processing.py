"""Tests for the background processing pipeline.

The Celery task is a thin wrapper, so the pipeline is tested by calling
`process_document_pipeline` directly with a test session — no broker needed.
"""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidPdfError
from app.models import Document, DocumentChunk, Policy, ProcessingStatus
from app.services.document_service import process_document_pipeline
from tests.pdf_factory import make_pdf


def seed_document(db_session: Session, file_path: str) -> Document:
    policy = Policy(name="Pipeline Test Policy")
    document = Document(
        policy=policy,
        filename="policy.pdf",
        file_path=file_path,
        processing_status=ProcessingStatus.PENDING.value,
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_pipeline_completes_and_counts_pages(
    db_session: Session, tmp_path: Path, fake_embeddings
) -> None:
    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(make_pdf(["Page one text", "Page two text", "Page three text"]))
    document = seed_document(db_session, str(pdf))

    process_document_pipeline(db_session, document.id)

    db_session.refresh(document)
    assert document.processing_status == ProcessingStatus.COMPLETED.value
    assert document.page_count == 3


def test_pipeline_stores_chunks_with_embeddings_and_metadata(
    db_session: Session, tmp_path: Path, fake_embeddings
) -> None:
    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(
        make_pdf(
            [
                "Section 1: Coverage. Hospitalization is covered up to the sum insured.",
                "Section 2: Exclusions. Cosmetic surgery is not covered.",
            ]
        )
    )
    document = seed_document(db_session, str(pdf))

    process_document_pipeline(db_session, document.id)

    chunks = list(
        db_session.scalars(
            select(DocumentChunk).order_by(DocumentChunk.chunk_index)
        )
    )
    assert len(chunks) == 2
    first = chunks[0]
    assert first.policy_id == document.policy_id
    assert first.page_number == 1
    assert first.section == "Coverage"
    assert "Hospitalization is covered" in first.content
    assert first.embedding is not None and len(first.embedding) == 384
    assert first.chunk_metadata == {"char_count": len(first.content)}
    assert chunks[1].section == "Exclusions"


def test_pipeline_is_idempotent(
    db_session: Session, tmp_path: Path, fake_embeddings
) -> None:
    """Reprocessing must replace chunks, not duplicate them."""
    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(make_pdf(["Some policy text"]))
    document = seed_document(db_session, str(pdf))

    process_document_pipeline(db_session, document.id)
    process_document_pipeline(db_session, document.id)

    count = len(list(db_session.scalars(select(DocumentChunk))))
    assert count == 1


def test_pipeline_marks_failed_on_corrupt_pdf(
    db_session: Session, tmp_path: Path
) -> None:
    pdf = tmp_path / "corrupt.pdf"
    pdf.write_bytes(b"%PDF- garbage that will not parse")
    document = seed_document(db_session, str(pdf))

    with pytest.raises(InvalidPdfError):
        process_document_pipeline(db_session, document.id)

    db_session.refresh(document)
    assert document.processing_status == ProcessingStatus.FAILED.value
    assert document.page_count is None
