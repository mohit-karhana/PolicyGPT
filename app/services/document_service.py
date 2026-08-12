"""Document operations: upload, reads, and the processing pipeline.

Upload is deliberately split from processing:

- `create_document` runs inside the API request: validate, store the file,
  create the row with status `pending`. It must stay fast.
- `process_document_pipeline` runs inside a Celery worker: extract text
  page by page and advance the status. Heavy work never blocks the API.
"""

import uuid

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    DocumentNotFoundError,
    FileTooLargeError,
    InvalidFileTypeError,
)
from app.core.logging import get_logger
from app.models.chunk import DocumentChunk
from app.models.document import Document, ProcessingStatus
from app.services import chunking_service, embedding_service, pdf_service
from app.services.policy_service import get_policy
from app.services.storage_service import get_storage

logger = get_logger(__name__)

PDF_MAGIC_BYTES = b"%PDF-"


def create_document(db: Session, policy_id: uuid.UUID, upload: UploadFile) -> Document:
    """Validate an uploaded PDF, store the file, and create a pending row.

    Validation happens in cheap-to-expensive order: extension, size,
    magic bytes. Full PDF parsing is left to the background worker.
    """
    get_policy(db, policy_id)  # 404 early for unknown policies

    filename = upload.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise InvalidFileTypeError("Only PDF files are accepted (.pdf extension required)")

    upload.file.seek(0, 2)  # seek to end to measure size without reading
    size_bytes = upload.file.tell()
    upload.file.seek(0)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileTooLargeError(
            f"File is {size_bytes / 1024 / 1024:.1f} MB; "
            f"the maximum is {settings.max_upload_size_mb} MB"
        )

    # Content-Type headers are client-controlled, so check the file's actual
    # bytes instead of trusting them. The PDF spec allows readers to accept
    # a header that appears within the first 1024 bytes (some generators
    # prepend junk), so scan that window rather than only offset 0.
    if PDF_MAGIC_BYTES not in upload.file.read(1024):
        raise InvalidFileTypeError(
            "File content is not a valid PDF (no %PDF header found)"
        )
    upload.file.seek(0)

    document_id = uuid.uuid4()
    # Store under a server-generated name; never trust client filenames
    # for filesystem paths.
    file_path = get_storage().save(upload.file, f"{policy_id}/{document_id}.pdf")

    document = Document(
        id=document_id,
        policy_id=policy_id,
        filename=filename,
        file_path=file_path,
        processing_status=ProcessingStatus.PENDING.value,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    logger.info(
        "Document uploaded: id=%s policy=%s filename=%r size_bytes=%d",
        document.id,
        policy_id,
        filename,
        size_bytes,
    )
    return document


def process_document_pipeline(db: Session, document_id: uuid.UUID) -> None:
    """Run the full ingestion pipeline for one document.

    PDF -> extract pages -> clean -> chunk -> embed (batched) -> store
    chunks + embeddings in pgvector -> mark completed.

    Idempotent: reprocessing a document replaces its chunks. Called from the
    Celery task; kept as a plain function so it can be tested with any
    database session and no broker.
    """
    document = get_document(db, document_id)
    document.processing_status = ProcessingStatus.PROCESSING.value
    db.commit()
    logger.info("Document processing started: id=%s", document_id)

    try:
        pages = pdf_service.extract_pages(document.file_path)
        drafts = chunking_service.chunk_pages(pages)

        embeddings: list[list[float]] = []
        if drafts:
            service = embedding_service.get_embedding_service()
            embeddings = service.embed_documents([d.content for d in drafts])

        # Replace any chunks from a previous processing run.
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        for draft, embedding in zip(drafts, embeddings, strict=True):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    policy_id=document.policy_id,
                    page_number=draft.page_number,
                    section=draft.section,
                    chunk_index=draft.chunk_index,
                    content=draft.content,
                    embedding=embedding,
                    chunk_metadata={"char_count": len(draft.content)},
                )
            )

        document.page_count = len(pages)
        document.processing_status = ProcessingStatus.COMPLETED.value
        db.commit()
        logger.info(
            "Document processing completed: id=%s pages=%d chunks=%d",
            document_id,
            len(pages),
            len(drafts),
        )
    except Exception:
        db.rollback()
        document.processing_status = ProcessingStatus.FAILED.value
        db.commit()
        logger.exception("Document processing failed: id=%s", document_id)
        raise


def embed_missing_chunks(db: Session, document_id: uuid.UUID) -> int:
    """Generate embeddings for chunks that don't have one yet.

    Backfill utility (used by the `generate_document_embeddings` task), e.g.
    after switching embedding models and clearing the embedding column.
    """
    document = get_document(db, document_id)
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .where(DocumentChunk.embedding.is_(None))
            .order_by(DocumentChunk.chunk_index)
        )
    )
    if not chunks:
        return 0

    service = embedding_service.get_embedding_service()
    embeddings = service.embed_documents([c.content for c in chunks])
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        chunk.embedding = embedding
    db.commit()
    logger.info(
        "Embeddings backfilled: document=%s chunks=%d", document_id, len(chunks)
    )
    return len(chunks)


def get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(document_id)
    return document


def list_documents_for_policy(db: Session, policy_id: uuid.UUID) -> list[Document]:
    # Raises PolicyNotFoundError for unknown policies instead of returning
    # a misleading empty list.
    get_policy(db, policy_id)
    return list(
        db.scalars(
            select(Document)
            .where(Document.policy_id == policy_id)
            .order_by(Document.created_at.desc())
        )
    )
