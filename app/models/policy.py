"""Policy model.

A Policy is the top-level entity: one insurance policy that a user wants to
ask questions about. Documents (the actual PDFs) belong to a policy, and in
later phases chunks and answers trace back to it:

    Policy -> Document -> Page -> Chunk
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document


class Policy(Base, TimestampMixin):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str | None] = mapped_column(String(255))
    policy_number: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Policy id={self.id} name={self.name!r}>"
