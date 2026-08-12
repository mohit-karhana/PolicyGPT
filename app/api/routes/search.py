"""Semantic search endpoints — retrieval only, NO LLM involved.

These exist so raw vector-search behavior stays observable: you see exactly
which chunks match a query and how strongly, before any LLM enters the
picture.
"""

import uuid

from fastapi import APIRouter

from app.api.dependencies import DbSession
from app.schemas.common import ErrorResponse
from app.schemas.search import (
    DebugSearchRequest,
    DebugSearchResponse,
    DebugSearchResultItem,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.services import retrieval_service

router = APIRouter(tags=["search"])

SEARCH_ERRORS = {
    404: {"model": ErrorResponse, "description": "Policy not found"},
    409: {"model": ErrorResponse, "description": "No processed documents to search"},
}


@router.post(
    "/policies/{policy_id}/search",
    response_model=SearchResponse,
    responses=SEARCH_ERRORS,
    summary="Semantic search within a policy (no LLM)",
)
def search_policy(policy_id: uuid.UUID, data: SearchRequest, db: DbSession) -> SearchResponse:
    """Embed the query and return the most semantically similar chunks.

    Similarity is cosine similarity (1.0 = identical meaning). This endpoint
    never calls the LLM — it exposes raw retrieval results.
    """
    chunks = retrieval_service.semantic_search(db, policy_id, data.query, data.top_k)
    return SearchResponse(
        query=data.query,
        results=[
            SearchResultItem(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                page_number=c.page_number,
                section=c.section,
                content=c.content,
                similarity_score=c.similarity,
            )
            for c in chunks
        ],
    )


@router.post(
    "/debug/search",
    response_model=DebugSearchResponse,
    responses=SEARCH_ERRORS,
    summary="Debug retrieval: ranked chunks with similarity scores",
)
def debug_search(data: DebugSearchRequest, db: DbSession) -> DebugSearchResponse:
    """Same retrieval as the search endpoint, formatted as a ranked list —
    useful for learning how embeddings and vector search behave."""
    chunks = retrieval_service.semantic_search(db, data.policy_id, data.query, data.top_k)
    return DebugSearchResponse(
        query=data.query,
        results=[
            DebugSearchResultItem(
                rank=i,
                page=c.page_number,
                section=c.section,
                similarity=c.similarity,
                chunk_id=c.chunk_id,
                content=c.content,
            )
            for i, c in enumerate(chunks, start=1)
        ],
    )
