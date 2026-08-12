"""Shared FastAPI dependencies.

`get_db` yields one SQLAlchemy session per request and guarantees it is
closed afterwards. Tests override this dependency to point at a test
database without touching application code.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
