"""
Custom middleware for the application
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette_context import context

from app.core.logging import log


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests and responses"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Set in context
        context["request_id"] = request_id

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Add request timing information"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Start timing
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        process_time = time.time() - start_time

        # Add to response headers
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))

        # Log slow requests
        if process_time > 1.0:  # More than 1 second
            log.warning(
                "Slow request detected",
                method=request.method,
                path=request.url.path,
                duration_ms=round(process_time * 1000, 2),
                status_code=response.status_code,
            )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy (adjust as needed)
        if request.url.path.startswith("/api"):
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"

        # Remove server header
        response.headers.pop("server", None)

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with structured data"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get request info
        request_id = context.get("request_id", "no-id")

        # Log request
        log.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            client_host=request.client.host if request.client else None,
        )

        # Process request
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Log response
        log.info(
            "Request completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        return response
