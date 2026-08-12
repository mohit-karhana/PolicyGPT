"""Celery application.

Redis is both the broker (queues task messages) and the result backend.
The API enqueues a task and returns immediately; a separate worker process
(the `celery` service in docker-compose) picks it up:

    FastAPI --> Redis queue --> Celery worker --> PostgreSQL

Run a worker with:

    celery -A app.tasks.celery_app worker --loglevel=info
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "policygpt",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.document_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,  # re-deliver if a worker dies mid-task
    worker_prefetch_multiplier=1,  # one task at a time per worker process
    broker_connection_retry_on_startup=True,
)
