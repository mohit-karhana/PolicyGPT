"""Structured logging setup.

Every log line carries a timestamp, level, logger name and message. Services
log key pipeline events (document uploaded, chunks created, embeddings
generated, ...) so the whole RAG pipeline can be followed in the logs.

Use `get_logger(__name__)` in modules instead of the root logger so log lines
are attributable to the module that produced them.
"""

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
    # Quiet down noisy third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
