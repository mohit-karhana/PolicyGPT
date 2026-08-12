"""Request/response schemas for document endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import ProcessingStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    filename: str
    processing_status: ProcessingStatus
    page_count: int | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
