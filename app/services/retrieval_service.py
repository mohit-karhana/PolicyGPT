"""Semantic retrieval with pgvector — kept deliberately explicit.

The whole trick is one SQL query:

    SELECT *, embedding <=> :query_vector AS distance
    FROM document_chunks
    WHERE policy_id = :policy_id
    ORDER BY distance
    LIMIT :top_k

`<=>` is pgvector's cosine-distance operator (0 = identical direction,
2 = opposite). We report `similarity = 1 - distance` so higher = better.
The SQLAlchemy expression below compiles to exactly that query.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NoProcessedDocumentsError
from app.core.logging import get_logger
from app.models.chunk import DocumentChunk
from app.models.document import Document, ProcessingStatus
from app.services import embedding_service
from app.services.policy_service import get_policy

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    """One search hit with everything needed to display and cite it."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    section: str | None
    content: str
    similarity: float


def search_chunks(
    db: Session,
    policy_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int,
) -> list[RetrievedChunk]:
    """Return the top_k chunks of a policy closest to the query embedding."""
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    rows = db.execute(
        select(DocumentChunk, distance.label("distance"))
        .where(DocumentChunk.policy_id == policy_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    ).all()

    results = [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            section=chunk.section,
            content=chunk.content,
            similarity=round(1.0 - row_distance, 4),
        )
        for chunk, row_distance in rows
    ]
    logger.info(
        "Vector search executed: policy=%s top_k=%d retrieved=%d similarities=%s",
        policy_id,
        top_k,
        len(results),
        [r.similarity for r in results],
    )
    return results


def ensure_policy_searchable(db: Session, policy_id: uuid.UUID) -> None:
    """Raise a helpful error if the policy has nothing to search yet."""
    get_policy(db, policy_id)  # 404 for unknown policies

    chunk_count = db.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.policy_id == policy_id)
    )
    if chunk_count:
        return

    statuses = set(
        db.scalars(
            select(Document.processing_status).where(Document.policy_id == policy_id)
        )
    )
    if not statuses:
        raise NoProcessedDocumentsError(
            "No documents uploaded for this policy yet. Upload a PDF first."
        )
    if statuses & {ProcessingStatus.PENDING.value, ProcessingStatus.PROCESSING.value}:
        raise NoProcessedDocumentsError(
            "Documents are still being processed. Try again shortly."
        )
    raise NoProcessedDocumentsError(
        "Document processing failed or produced no text; nothing to search."
    )


def semantic_search(
    db: Session,
    policy_id: uuid.UUID,
    query: str,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Full search pipeline: embed the query, then vector-search the policy.

    The query is embedded with the SAME model as the chunks — vectors from
    different models live in different spaces and cannot be compared.
    """
    ensure_policy_searchable(db, policy_id)
    k = top_k if top_k is not None else settings.top_k
    query_embedding = embedding_service.get_embedding_service().embed_text(query)
    return search_chunks(db, policy_id, query_embedding, k)
