"""Ask endpoint: RAG-powered question answering with citations."""

import uuid

from fastapi import APIRouter

from app.api.dependencies import DbSession
from app.schemas.chat import AskRequest, AskResponse, Citation, RetrievedChunkDebug
from app.schemas.common import ErrorResponse
from app.services import rag_service

router = APIRouter(tags=["chat"])


@router.post(
    "/policies/{policy_id}/ask",
    response_model=AskResponse,
    response_model_exclude_none=True,
    responses={
        404: {"model": ErrorResponse, "description": "Policy not found"},
        409: {"model": ErrorResponse, "description": "No processed documents"},
        503: {"model": ErrorResponse, "description": "LLM unavailable or not configured"},
    },
    summary="Ask a question about a policy (RAG)",
)
def ask_question(policy_id: uuid.UUID, data: AskRequest, db: DbSession) -> AskResponse:
    """Answer a question grounded in the policy's documents.

    Pipeline: embed question -> pgvector search -> top-K chunks -> prompt ->
    LLM -> answer. Citations point back to the exact pages and chunks used.
    Set `debug: true` to also see the retrieved chunks.
    """
    result = rag_service.ask(db, policy_id, data.question, data.top_k)
    return AskResponse(
        answer=result.answer,
        citations=[
            Citation(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                page_number=c.page_number,
                section=c.section,
                similarity_score=c.similarity,
            )
            for c in result.chunks
        ],
        retrieved_chunks=(
            [
                RetrievedChunkDebug(
                    chunk_id=c.chunk_id,
                    page_number=c.page_number,
                    section=c.section,
                    similarity_score=c.similarity,
                    content=c.content,
                )
                for c in result.chunks
            ]
            if data.debug
            else None
        ),
    )
