"""Request/response schemas for policy endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Human-readable policy name")
    provider: str | None = Field(default=None, max_length=255, description="Insurer name")
    policy_number: str | None = Field(default=None, max_length=100)
    description: str | None = None


class PolicyUpdate(BaseModel):
    """Partial update; only the provided fields are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider: str | None = Field(default=None, max_length=255)
    policy_number: str | None = Field(default=None, max_length=100)
    description: str | None = None


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    provider: str | None
    policy_number: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class PolicyListResponse(BaseModel):
    items: list[PolicyResponse]
    total: int
    limit: int
    offset: int
