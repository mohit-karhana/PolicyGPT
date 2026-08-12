"""Database engine and session factory.

We use synchronous SQLAlchemy 2.0 with psycopg 3:

- FastAPI runs sync endpoints in a threadpool, so sync DB access does not
  block the event loop.
- Celery workers (Phase 2) are synchronous, so the same session factory can
  be shared between the API and background tasks.
- Sync code keeps the learning focus on the AI concepts instead of on async
  plumbing.

Sessions are created per-request via the `get_db` dependency in
`app.api.dependencies`.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # transparently recover from dropped connections
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
