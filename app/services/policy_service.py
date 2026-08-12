"""Policy CRUD operations.

Route handlers stay thin: they parse/validate input and delegate here.
This keeps business logic testable without HTTP and reusable from Celery
tasks later.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import PolicyNotFoundError
from app.core.logging import get_logger
from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate

logger = get_logger(__name__)


def create_policy(db: Session, data: PolicyCreate) -> Policy:
    policy = Policy(**data.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    logger.info("Policy created: id=%s name=%r", policy.id, policy.name)
    return policy


def get_policy(db: Session, policy_id: uuid.UUID) -> Policy:
    policy = db.get(Policy, policy_id)
    if policy is None:
        raise PolicyNotFoundError(policy_id)
    return policy


def list_policies(db: Session, limit: int, offset: int) -> tuple[list[Policy], int]:
    total = db.scalar(select(func.count()).select_from(Policy)) or 0
    policies = list(
        db.scalars(
            select(Policy).order_by(Policy.created_at.desc()).limit(limit).offset(offset)
        )
    )
    return policies, total


def update_policy(db: Session, policy_id: uuid.UUID, data: PolicyUpdate) -> Policy:
    policy = get_policy(db, policy_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    logger.info("Policy updated: id=%s", policy.id)
    return policy


def delete_policy(db: Session, policy_id: uuid.UUID) -> None:
    policy = get_policy(db, policy_id)
    db.delete(policy)
    db.commit()
    logger.info("Policy deleted: id=%s", policy_id)
