"""Application exceptions.

Services raise these domain exceptions; a single FastAPI exception handler
(registered in `app.main`) converts them into a consistent JSON error shape:

    {"error": {"code": "policy_not_found", "message": "..."}}

Routes and services never build HTTP error responses by hand, and internal
stack traces are never exposed to API clients.
"""


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class PolicyNotFoundError(NotFoundError):
    error_code = "policy_not_found"

    def __init__(self, policy_id: object) -> None:
        super().__init__(f"Policy '{policy_id}' not found")


class DocumentNotFoundError(NotFoundError):
    error_code = "document_not_found"

    def __init__(self, document_id: object) -> None:
        super().__init__(f"Document '{document_id}' not found")


class InvalidFileTypeError(AppError):
    status_code = 415
    error_code = "invalid_file_type"


class FileTooLargeError(AppError):
    status_code = 413
    error_code = "file_too_large"


class InvalidPdfError(AppError):
    """Raised when a file claims to be a PDF but cannot be parsed."""

    status_code = 400
    error_code = "invalid_pdf"


class NoProcessedDocumentsError(AppError):
    """Search/ask on a policy that has no searchable chunks yet."""

    status_code = 409
    error_code = "no_processed_documents"


class LLMUnavailableError(AppError):
    status_code = 503
    error_code = "llm_unavailable"
