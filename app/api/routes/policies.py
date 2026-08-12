"""Policy CRUD endpoints."""

import uuid

from fastapi import APIRouter, Query, status

from app.api.dependencies import DbSession
from app.schemas.common import ErrorResponse
from app.schemas.policy import (
    PolicyCreate,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdate,
)
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["policies"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Policy not found"}}


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a policy",
)
def create_policy(data: PolicyCreate, db: DbSession) -> PolicyResponse:
    """Create an insurance policy. Documents (PDFs) are uploaded to it separately."""
    policy = policy_service.create_policy(db, data)
    return PolicyResponse.model_validate(policy)


@router.get("", response_model=PolicyListResponse, summary="List policies")
def list_policies(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PolicyListResponse:
    policies, total = policy_service.list_policies(db, limit=limit, offset=offset)
    return PolicyListResponse(
        items=[PolicyResponse.model_validate(p) for p in policies],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    responses=NOT_FOUND,
    summary="Get a policy",
)
def get_policy(policy_id: uuid.UUID, db: DbSession) -> PolicyResponse:
    return PolicyResponse.model_validate(policy_service.get_policy(db, policy_id))


@router.patch(
    "/{policy_id}",
    response_model=PolicyResponse,
    responses=NOT_FOUND,
    summary="Update a policy",
)
def update_policy(policy_id: uuid.UUID, data: PolicyUpdate, db: DbSession) -> PolicyResponse:
    """Partially update a policy; only the provided fields are changed."""
    return PolicyResponse.model_validate(policy_service.update_policy(db, policy_id, data))


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    summary="Delete a policy",
)
def delete_policy(policy_id: uuid.UUID, db: DbSession) -> None:
    """Delete a policy and (via cascade) all of its documents."""
    policy_service.delete_policy(db, policy_id)
