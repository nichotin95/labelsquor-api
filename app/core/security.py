"""
Security utilities for API authentication and authorization
"""

import os
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.api_key import APIKeyHeader

from app.core.config import settings
from app.core.logging import log

# API Key authentication for admin endpoints
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_admin_api_key(api_key: Optional[str] = Security(api_key_header)) -> bool:
    """
    Verify admin API key for protected endpoints
    
    Args:
        api_key: API key from X-API-Key header
        
    Returns:
        True if valid, raises HTTPException if invalid
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required for admin endpoints",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Get admin API key from environment
    admin_api_key = os.getenv("ADMIN_API_KEY")
    if not admin_api_key:
        log.error("ADMIN_API_KEY not configured in environment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error"
        )
    
    if api_key != admin_api_key:
        log.warning(f"Invalid API key attempt: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    log.info("Admin API key verified successfully")
    return True


async def verify_consumer_access(
    authorization: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> bool:
    """
    Verify consumer access (optional authentication for rate limiting)
    
    Args:
        authorization: Bearer token (optional)
        
    Returns:
        True (always allows access, but logs for rate limiting)
    """
    if authorization:
        # Optional: Implement user authentication here
        # For now, just log for analytics
        log.info(f"Consumer access with token: {authorization.credentials[:8]}...")
    else:
        log.info("Anonymous consumer access")
    
    return True


def get_client_ip(request) -> str:
    """
    Get client IP address for rate limiting and logging
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address
    """
    # Check for forwarded headers (behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection
    return request.client.host if request.client else "unknown"


class SecurityHeaders:
    """Security headers for API responses"""
    
    @staticmethod
    def get_security_headers() -> dict:
        """Get security headers for responses"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }


# Rate limiting configuration
RATE_LIMITS = {
    "consumer": "100/minute",   # Consumer product search/details
    "admin": "10/minute",       # Admin crawler operations
    "ai_analysis": "5/minute",  # AI analysis endpoints
    "health": "1000/minute"     # Health checks
}
