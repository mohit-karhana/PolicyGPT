"""Document model.

A Document is one uploaded PDF belonging to a policy. Processing happens
asynchronously (Celery, Phase 2), so the row tracks a `processing_status`
lifecycle that clients can poll:

    pending -> processing -> completed
                          -> failed
"""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.chunk import DocumentChunk
    from app.models.policy import Policy


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))
    # Stored as a plain string (not a native DB enum) so adding a status later
    # is a code change, not a migration.
    processing_status: Mapped[str] = mapped_column(
        String(20), default=ProcessingStatus.PENDING.value
    )
    page_count: Mapped[int | None]

    policy: Mapped["Policy"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename!r} status={self.processing_status}>"
