"""
Request ID middleware
"""

import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests"""

    async def dispatch(self, request: Request, call_next):
        # Generate request ID if not provided
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Add to request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers["X-Request-ID"] = request_id

        return response
