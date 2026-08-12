"""Background tasks for document processing.

Tasks are thin wrappers: they open a DB session and delegate to service
functions. All real logic lives in `app.services.document_service`, which
keeps it testable without a running broker.
"""

import uuid

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.services import document_service
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="process_document")
def process_document(document_id: str) -> None:
    """Extract and process one uploaded document (see the service pipeline)."""
    db = SessionLocal()
    try:
        document_service.process_document_pipeline(db, uuid.UUID(document_id))
    finally:
        db.close()


@celery_app.task(name="generate_document_embeddings")
def generate_document_embeddings(document_id: str) -> int:
    """Backfill embeddings for chunks that don't have one yet."""
    db = SessionLocal()
    try:
        return document_service.embed_missing_chunks(db, uuid.UUID(document_id))
    finally:
        db.close()


def queue_document_processing(document_id: uuid.UUID) -> None:
    """Enqueue processing for a document. Called by the API after upload."""
    process_document.delay(str(document_id))
    logger.info("Document processing queued: id=%s", document_id)
