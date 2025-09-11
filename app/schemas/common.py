"""
Common schemas used across the API
"""
from typing import Optional, Generic, TypeVar, List
from pydantic import BaseModel, Field


T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""
    skip: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=20, ge=1, le=100, description="Number of items to return")


class SearchParams(BaseModel):
    """Search parameters"""
    q: Optional[str] = Field(None, description="Search query")
    category_id: Optional[str] = Field(None, description="Filter by category")
    include_descendants: bool = Field(default=False, description="Include category descendants")
    min_score: Optional[int] = Field(None, ge=0, le=100)
    max_score: Optional[int] = Field(None, ge=0, le=100)
    allergens: Optional[List[str]] = Field(None, description="Filter by allergens")
    claims: Optional[List[str]] = Field(None, description="Filter by claims")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T]
    total: int
    skip: int
    limit: int
    has_more: bool


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = "ok"
    timestamp: str
    version: str
    database: str = "connected"
