"""Document endpoints: upload and reads.

Upload returns immediately with status `pending`; a Celery worker processes
the PDF in the background. Poll `GET /documents/{id}` until the status is
`completed` (or `failed`).
"""

import uuid

from fastapi import APIRouter, UploadFile, status

from app.api.dependencies import DbSession
from app.schemas.common import ErrorResponse
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services import document_service
from app.tasks.document_tasks import queue_document_processing

router = APIRouter(tags=["documents"])


@router.post(
    "/policies/{policy_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse, "description": "Policy not found"},
        413: {"model": ErrorResponse, "description": "File too large"},
        415: {"model": ErrorResponse, "description": "Not a PDF file"},
    },
    summary="Upload a policy PDF",
)
def upload_document(policy_id: uuid.UUID, file: UploadFile, db: DbSession) -> DocumentResponse:
    """Upload a PDF for this policy.

    The file is validated and stored, then processed **asynchronously**.
    The response has `processing_status: pending`; poll
    `GET /api/v1/documents/{id}` until it becomes `completed`.
    """
    document = document_service.create_document(db, policy_id, file)
    queue_document_processing(document.id)
    return DocumentResponse.model_validate(document)


@router.get(
    "/policies/{policy_id}/documents",
    response_model=DocumentListResponse,
    responses={404: {"model": ErrorResponse, "description": "Policy not found"}},
    summary="List documents for a policy",
)
def list_policy_documents(policy_id: uuid.UUID, db: DbSession) -> DocumentListResponse:
    documents = document_service.list_documents_for_policy(db, policy_id)
    items = [DocumentResponse.model_validate(d) for d in documents]
    return DocumentListResponse(items=items, total=len(items))


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
    summary="Get a document and its processing status",
)
def get_document(document_id: uuid.UUID, db: DbSession) -> DocumentResponse:
    """Fetch a document, including its `processing_status` for polling."""
    return DocumentResponse.model_validate(document_service.get_document(db, document_id))
