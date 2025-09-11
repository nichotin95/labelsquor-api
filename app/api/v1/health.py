"""
Health check endpoints
"""
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.api.deps import AsyncSessionDep
from app.schemas.common import HealthCheckResponse
from app.core.config import settings
from app.core.cache import get_cache
from app.core.logging import log


router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Basic health check"""
    return HealthCheckResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
        version=settings.VERSION,
        database="unknown"
    )


@router.get("/health/live", response_model=Dict[str, Any])
async def liveness_probe() -> Dict[str, Any]:
    """Kubernetes liveness probe"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/ready", response_model=Dict[str, Any])
async def readiness_probe(session: AsyncSessionDep) -> Dict[str, Any]:
    """
    Kubernetes readiness probe - checks all dependencies
    """
    checks = {
        "database": False,
        "cache": False
    }
    
    # Check database
    try:
        result = await session.execute(text("SELECT 1"))
        checks["database"] = result.scalar() == 1
    except Exception as e:
        log.error(f"Database health check failed: {e}")
    
    # Check cache
    try:
        cache = get_cache()
        test_key = "health:check"
        await cache.set(test_key, "ok", ttl=10)
        value = await cache.get(test_key)
        checks["cache"] = value == "ok"
    except Exception as e:
        log.error(f"Cache health check failed: {e}")
    
    # Overall status
    all_healthy = all(checks.values())
    
    return {
        "status": "ok" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }


@router.get("/health/detailed", response_model=Dict[str, Any])
async def detailed_health(session: AsyncSessionDep) -> Dict[str, Any]:
    """
    Detailed health check with component statuses
    """
    health_data = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "components": {}
    }
    
    # Database check with details
    try:
        # Check connection
        result = await session.execute(text("SELECT version()"))
        db_version = result.scalar()
        
        # Check table counts
        product_count = await session.execute(text("SELECT COUNT(*) FROM product"))
        brand_count = await session.execute(text("SELECT COUNT(*) FROM brand"))
        
        health_data["components"]["database"] = {
            "status": "healthy",
            "version": db_version,
            "metrics": {
                "products": product_count.scalar(),
                "brands": brand_count.scalar()
            }
        }
    except Exception as e:
        health_data["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_data["status"] = "degraded"
    
    # Cache check
    try:
        cache = get_cache()
        await cache.set("health:detailed", "test", ttl=5)
        await cache.get("health:detailed")
        
        health_data["components"]["cache"] = {
            "status": "healthy",
            "type": cache.__class__.__name__
        }
    except Exception as e:
        health_data["components"]["cache"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_data["status"] = "degraded"
    
    # Feature flags
    health_data["features"] = {
        "ocr": settings.ENABLE_OCR,
        "barcode_scan": settings.ENABLE_BARCODE_SCAN,
        "graphql": settings.ENABLE_GRAPHQL,
        "webhooks": settings.ENABLE_WEBHOOKS
    }
    
    return health_data
