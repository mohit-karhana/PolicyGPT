"""Health check endpoint.

Reports API liveness and database connectivity. Used by Docker Compose
healthchecks and useful as a first smoke test after `docker compose up`.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.dependencies import DbSession
from app.core.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check(db: DbSession) -> HealthResponse:
    """Check that the API is up and can reach the database."""
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # pragma: no cover - only hit when the DB is down
        database = "unavailable"
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        environment=settings.app_env,
        database=database,
    )
