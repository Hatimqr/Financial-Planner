"""Error handling and structured error responses."""

import logging
from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error class."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(APIError):
    """Validation error."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(APIError):
    """Resource conflict error."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
            details=details,
        )


class AccountingError(APIError):
    """Accounting/business logic error."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="ACCOUNTING_ERROR",
            status_code=400,
            details=details,
        )


def create_error_response(
    message: str,
    code: str,
    status_code: int = 500,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create a structured error response."""
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions."""
    logger.warning(
        f"API Error: {exc.code} - {exc.message}",
        extra={
            "error_code": exc.code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": str(request.url.path),
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            message=exc.message,
            code=exc.code,
            status_code=exc.status_code,
            details=exc.details,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException."""
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": str(request.url.path),
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            message=str(exc.detail),
            code="HTTP_ERROR",
            status_code=exc.status_code,
        ),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "path": str(request.url.path),
            "method": request.method,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content=create_error_response(
            message="Internal server error",
            code="INTERNAL_ERROR",
            status_code=500,
        ),
    )
