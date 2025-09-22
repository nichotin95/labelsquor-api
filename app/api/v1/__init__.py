"""
API v1 routers
"""

from fastapi import APIRouter

from .brands import router as brands_router
from .categories import router as categories_router
from .crawler import router as crawler_router
from .health import router as health_router
from .products import router as products_router
from .quota import router as quota_router
from .search import router as search_router
from .workflow import router as workflow_router

api_router = APIRouter()

# Include routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(brands_router, prefix="/brands", tags=["brands"])
api_router.include_router(products_router, prefix="/products", tags=["products"])
api_router.include_router(categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(crawler_router, tags=["crawler"])
api_router.include_router(workflow_router, prefix="/workflow", tags=["workflow"])
api_router.include_router(quota_router, prefix="/quota", tags=["quota"])
