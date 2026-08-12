"""Request/response schemas for semantic search endpoints."""

import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000, description="Natural-language question")
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="How many chunks to retrieve (defaults to TOP_K setting)",
    )


class SearchResultItem(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    section: str | None
    content: str
    similarity_score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]


class DebugSearchRequest(BaseModel):
    policy_id: uuid.UUID
    query: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=50)


class DebugSearchResultItem(BaseModel):
    rank: int
    page: int
    section: str | None
    similarity: float
    chunk_id: uuid.UUID
    content: str


class DebugSearchResponse(BaseModel):
    query: str
    results: list[DebugSearchResultItem]
