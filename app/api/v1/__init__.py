"""
API v1 routers
"""
from fastapi import APIRouter

from .brands import router as brands_router
from .products import router as products_router
from .categories import router as categories_router
from .health import router as health_router
from .search import router as search_router

api_router = APIRouter()

# Include routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(brands_router, prefix="/brands", tags=["brands"])
api_router.include_router(products_router, prefix="/products", tags=["products"])
api_router.include_router(categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
