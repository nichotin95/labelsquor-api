"""
Custom exceptions for the application
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class BaseAPIException(HTTPException):
    """Base exception for API errors"""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"
    headers: Optional[Dict[str, str]] = None
    
    def __init__(
        self,
        detail: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        super().__init__(
            status_code=self.status_code,
            detail=detail or self.detail,
            headers=headers or self.headers
        )
        # Store any additional context
        self.context = kwargs


class NotFoundError(BaseAPIException):
    """Resource not found"""
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class ConflictError(BaseAPIException):
    """Conflict with existing resource"""
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource conflict"


class ValidationError(BaseAPIException):
    """Validation error"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation error"


class UnauthorizedError(BaseAPIException):
    """Unauthorized access"""
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Unauthorized"
    headers = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(BaseAPIException):
    """Forbidden access"""
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Forbidden"


class BadRequestError(BaseAPIException):
    """Bad request"""
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad request"


class DatabaseError(BaseAPIException):
    """Database operation error"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Database error"


class ExternalServiceError(BaseAPIException):
    """External service error"""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "External service unavailable"


class RateLimitError(BaseAPIException):
    """Rate limit exceeded"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Rate limit exceeded"


class BusinessLogicError(BaseAPIException):
    """Business logic violation"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Business logic error"


# Error response models for OpenAPI documentation
class ErrorDetail(BaseModel):
    """Error detail model"""
    message: str
    type: str
    context: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: ErrorDetail
    correlation_id: Optional[str] = None
    timestamp: str


# Exception handlers
async def handle_api_exception(request, exc: BaseAPIException) -> JSONResponse:
    """Handle API exceptions with structured response"""
    from starlette_context import context
    import json
    from datetime import datetime
    
    error_response = {
        "error": {
            "message": exc.detail,
            "type": exc.__class__.__name__,
            "context": getattr(exc, "context", {})
        },
        "correlation_id": context.get("correlation_id", "no-context"),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
        headers=getattr(exc, "headers", None)
    )


async def handle_unexpected_exception(request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    from starlette_context import context
    from app.core.logging import log
    import json
    from datetime import datetime
    
    # Log the full exception
    log.exception("Unexpected error", exc_info=exc)
    
    # Don't expose internal errors in production
    if settings.DEBUG:
        detail = str(exc)
    else:
        detail = "An unexpected error occurred"
    
    error_response = {
        "error": {
            "message": detail,
            "type": "InternalServerError",
            "context": {}
        },
        "correlation_id": context.get("correlation_id", "no-context"),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )


# Import these for the handlers
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.core.config import settings
