"""Request/response schemas for the ask (RAG) endpoint."""

import uuid

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    debug: bool = Field(
        default=False,
        description="Also return the retrieved chunks that were given to the LLM",
    )


class Citation(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    section: str | None
    similarity_score: float


class RetrievedChunkDebug(BaseModel):
    chunk_id: uuid.UUID
    page_number: int
    section: str | None
    similarity_score: float
    content: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunkDebug] | None = Field(
        default=None, description="Only present when debug=true"
    )
