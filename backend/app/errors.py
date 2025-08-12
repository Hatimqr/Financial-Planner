"""
Structured error handling for the financial planning application.

This module implements the error envelope format and provides FastAPI exception
handlers for consistent error responses across the API.
"""

import uuid
from typing import Any, Dict, Optional, Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging import get_logger, log_error

logger = get_logger("financial_planning.errors")


class ErrorDetail(BaseModel):
    """Error detail model for structured error responses."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""
    ok: bool = False
    error: ErrorDetail
    request_id: Optional[str] = None


class FinancialPlanningError(Exception):
    """Base exception class for application-specific errors."""
    
    def __init__(
        self,
        message: str,
        code: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)


class ValidationError(FinancialPlanningError):
    """Error for data validation failures."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class NotFoundError(FinancialPlanningError):
    """Error for resource not found."""
    
    def __init__(
        self,
        resource: str,
        resource_id: Optional[Union[str, int]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"{resource} not found"
        if resource_id:
            message += f" (ID: {resource_id})"
        
        super().__init__(
            message=message,
            code="NOT_FOUND",
            details=details,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(FinancialPlanningError):
    """Error for resource conflicts."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="CONFLICT",
            details=details,
            status_code=status.HTTP_409_CONFLICT,
        )


class AuthenticationError(FinancialPlanningError):
    """Error for authentication failures."""
    
    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            details=details,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(FinancialPlanningError):
    """Error for authorization failures."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR", 
            details=details,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class BusinessLogicError(FinancialPlanningError):
    """Error for business logic violations."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="BUSINESS_LOGIC_ERROR",
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class ExternalServiceError(FinancialPlanningError):
    """Error for external service failures."""
    
    def __init__(
        self,
        service: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"{service} service error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details=details,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


def create_error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Create a standardized error response."""
    return ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
        ),
        request_id=request_id,
    )


def get_request_id(request: Request) -> str:
    """Get or generate a request ID for tracing."""
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    return request_id


async def financial_planning_exception_handler(
    request: Request,
    exc: FinancialPlanningError,
) -> JSONResponse:
    """Handle application-specific exceptions."""
    request_id = get_request_id(request)
    
    # Log the error with context
    log_error(
        logger,
        exc,
        context={
            "method": request.method,
            "url": str(request.url),
            "error_code": exc.code,
        },
        request_id=request_id,
    )
    
    error_response = create_error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    request_id = get_request_id(request)
    
    # Map HTTP status codes to error codes
    status_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN", 
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }
    
    error_code = status_code_map.get(exc.status_code, "HTTP_ERROR")
    
    # Log non-client errors
    if exc.status_code >= 500:
        log_error(
            logger,
            Exception(f"HTTP {exc.status_code}: {exc.detail}"),
            context={
                "method": request.method,
                "url": str(request.url),
                "status_code": exc.status_code,
            },
            request_id=request_id,
        )
    
    error_response = create_error_response(
        code=error_code,
        message=str(exc.detail),
        request_id=request_id,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    request_id = get_request_id(request)
    
    # Extract validation details
    validation_details = []
    for error in exc.errors():
        validation_details.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input"),
        })
    
    logger.warning(
        f"Validation error for {request.method} {request.url}",
        extra={
            "request_id": request_id,
            "validation_errors": validation_details,
        },
    )
    
    error_response = create_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"validation_errors": validation_details},
        request_id=request_id,
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(),
    )


async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle unexpected exceptions."""
    request_id = get_request_id(request)
    
    # Log the unexpected error
    log_error(
        logger,
        exc,
        context={
            "method": request.method,
            "url": str(request.url),
            "exception_type": type(exc).__name__,
        },
        request_id=request_id,
    )
    
    error_response = create_error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        request_id=request_id,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(FinancialPlanningError, financial_planning_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)