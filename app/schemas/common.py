"""Schemas shared across endpoints (error shape, pagination)."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Consistent error body returned by all error responses.

    Example: {"error": {"code": "policy_not_found", "message": "..."}}
    """

    error: ErrorDetail
