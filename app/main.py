"""PolicyGPT API entrypoint.

Wires together routers, exception handlers and logging. Business logic lives
in `app.services`; this module only handles application composition.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import chat, documents, health, policies, search
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

DESCRIPTION = """
AI-powered insurance policy assistant.

Upload insurance policy PDFs and ask questions like *"Is diabetes covered?"*.
Answers are grounded in the uploaded documents using embeddings, pgvector
similarity search and RAG, with citations back to the exact page and chunk.

Typical flow: create a policy → upload a PDF → poll the document status →
`search` (raw retrieval, no LLM) or `ask` (RAG answer with citations).
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.include_router(health.router)
    app.include_router(policies.router, prefix=settings.api_v1_prefix)
    app.include_router(documents.router, prefix=settings.api_v1_prefix)
    app.include_router(search.router, prefix=settings.api_v1_prefix)
    app.include_router(chat.router, prefix=settings.api_v1_prefix)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Convert domain exceptions into the consistent error shape."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Log unexpected errors; never leak stack traces to clients."""
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal error occurred.",
                }
            },
        )

    return app


app = create_app()
