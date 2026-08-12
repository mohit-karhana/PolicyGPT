"""DocumentChunk model — the heart of the retrieval system.

Each row is one small piece of a document's text together with its embedding
vector. This is what similarity search runs against, and its metadata
(page_number, section, chunk_index) is what makes citations possible:

    Policy -> Document -> Page -> Chunk

The embedding column uses the pgvector `vector` type. Its dimension comes
from settings (`EMBEDDING_DIMENSION`) — the single place it is defined.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    # Denormalized from the document so per-policy similarity search filters
    # on one indexed column instead of joining through documents.
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int]
    section: Mapped[str | None] = mapped_column(String(255))
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    # Nullable so chunks can be stored first and embedded in a later step.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimension)
    )
    # `metadata` is reserved by SQLAlchemy's declarative base, hence the
    # attribute name chunk_metadata mapped onto a column named "metadata".
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk id={self.id} document={self.document_id} "
            f"page={self.page_number} index={self.chunk_index}>"
        )
