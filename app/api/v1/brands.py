"""
Brand API endpoints with advanced features
"""
from typing import List, Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status, Response, BackgroundTasks
from fastapi_cache.decorator import cache
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import (
    BrandServiceDep, PaginationDep, RequestIdDep, RateLimitDep,
    get_current_user_optional, TokenData
)
from app.schemas.brand import BrandCreate, BrandUpdate, BrandRead, BrandReadWithProducts
from app.schemas.common import PaginatedResponse
from app.core.logging import log
from app.core.cache import CacheKey


router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/",
    response_model=PaginatedResponse[BrandRead],
    summary="List brands",
    description="Get paginated list of brands with optional search"
)
@cache(expire=60)  # Cache for 1 minute
async def list_brands(
    brand_service: BrandServiceDep,
    pagination: PaginationDep,
    request_id: RequestIdDep,
    q: Optional[str] = Query(None, description="Search query"),
    country: Optional[str] = Query(None, max_length=2, description="Filter by country code"),
    _: RateLimitDep = Depends()
) -> PaginatedResponse[BrandRead]:
    """
    List brands with pagination and search.
    
    - **q**: Search brands by name
    - **country**: Filter by 2-letter ISO country code
    - **skip**: Number of items to skip
    - **limit**: Number of items to return (max 100)
    """
    log.info(f"Listing brands", request_id=request_id, query=q, country=country)
    
    if q:
        # Search brands
        brands = await brand_service.search_brands(q, pagination.skip, pagination.limit)
        total = await brand_service.count_search_results(q)
    else:
        # List all brands
        filters = {"country": country} if country else {}
        brands = await brand_service.list_brands(
            skip=pagination.skip,
            limit=pagination.limit,
            filters=filters
        )
        total = await brand_service.count_brands(filters=filters)
    
    return PaginatedResponse(
        items=brands,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        has_more=total > pagination.skip + pagination.limit
    )


@router.get(
    "/top",
    response_model=List[dict],
    summary="Get top brands",
    description="Get top brands by product count"
)
@cache(expire=300)  # Cache for 5 minutes
async def get_top_brands(
    brand_service: BrandServiceDep,
    limit: int = Query(10, ge=1, le=50, description="Number of brands to return"),
    country: Optional[str] = Query(None, max_length=2, description="Filter by country code")
) -> List[dict]:
    """Get top brands ranked by product count"""
    return await brand_service.get_top_brands(limit=limit, country=country)


@router.post(
    "/",
    response_model=BrandRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create brand",
    description="Create a new brand"
)
@limiter.limit("10/hour")  # Rate limit brand creation
async def create_brand(
    request: Request,
    brand_service: BrandServiceDep,
    brand_in: BrandCreate,
    background_tasks: BackgroundTasks,
    request_id: RequestIdDep,
    current_user: Optional[TokenData] = Depends(get_current_user_optional)
) -> BrandRead:
    """
    Create a new brand.
    
    The brand name will be normalized for deduplication.
    """
    log.info(
        f"Creating brand",
        request_id=request_id,
        brand_name=brand_in.name,
        user_id=current_user.sub if current_user else "anonymous"
    )
    
    # Create brand
    brand = await brand_service.create_brand(brand_in)
    
    # Invalidate cache in background
    background_tasks.add_task(
        invalidate_brand_caches,
        brand_id=brand.brand_id
    )
    
    # Add webhook notification in background (if enabled)
    if settings.ENABLE_WEBHOOKS:
        background_tasks.add_task(
            send_webhook_notification,
            event="brand.created",
            data=brand.model_dump()
        )
    
    return brand


@router.get(
    "/{brand_id}",
    response_model=BrandRead,
    summary="Get brand",
    description="Get brand by ID"
)
@cache(expire=300, key_builder=lambda f, brand_id: f"brand:{brand_id}")
async def get_brand(
    brand_id: UUID,
    brand_service: BrandServiceDep,
    include_products: bool = Query(False, description="Include products in response")
) -> BrandRead:
    """Get brand details by ID"""
    if include_products:
        return await brand_service.get_brand_with_products(brand_id)
    
    return await brand_service.get_brand(brand_id)


@router.patch(
    "/{brand_id}",
    response_model=BrandRead,
    summary="Update brand",
    description="Update brand details"
)
async def update_brand(
    brand_id: UUID,
    brand_service: BrandServiceDep,
    brand_update: BrandUpdate,
    background_tasks: BackgroundTasks,
    request_id: RequestIdDep,
    current_user: TokenData = Depends(get_current_user)
) -> BrandRead:
    """
    Update brand details.
    
    Only provided fields will be updated.
    """
    log.info(
        f"Updating brand",
        request_id=request_id,
        brand_id=str(brand_id),
        user_id=current_user.sub
    )
    
    # Update brand
    brand = await brand_service.update_brand(brand_id, brand_update)
    
    # Invalidate cache
    background_tasks.add_task(
        invalidate_brand_caches,
        brand_id=brand_id
    )
    
    return brand


@router.delete(
    "/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete brand",
    description="Delete a brand (only if no products exist)"
)
async def delete_brand(
    brand_id: UUID,
    brand_service: BrandServiceDep,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user)
) -> Response:
    """
    Delete a brand.
    
    Will fail if brand has associated products.
    """
    log.info(
        f"Deleting brand",
        brand_id=str(brand_id),
        user_id=current_user.sub
    )
    
    # Delete brand
    await brand_service.delete_brand(brand_id)
    
    # Invalidate cache
    background_tasks.add_task(
        invalidate_brand_caches,
        brand_id=brand_id
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{brand_id}/merge",
    response_model=BrandRead,
    summary="Merge brands",
    description="Merge source brand into target brand"
)
async def merge_brands(
    brand_id: UUID,
    source_brand_id: UUID = Query(..., description="Source brand to merge from"),
    brand_service: BrandServiceDep,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user)
) -> BrandRead:
    """
    Merge brands.
    
    All products from source brand will be moved to target brand.
    Source brand will be deleted.
    """
    log.info(
        f"Merging brands",
        source_id=str(source_brand_id),
        target_id=str(brand_id),
        user_id=current_user.sub
    )
    
    # Merge brands
    brand = await brand_service.merge_brands(
        source_brand_id=source_brand_id,
        target_brand_id=brand_id
    )
    
    # Invalidate caches for both brands
    background_tasks.add_task(
        invalidate_brand_caches,
        brand_id=brand_id,
        source_brand_id=source_brand_id
    )
    
    return brand


# Background tasks
async def invalidate_brand_caches(brand_id: UUID, source_brand_id: Optional[UUID] = None):
    """Invalidate all caches related to a brand"""
    cache_keys = [
        f"brand:{brand_id}",
        "brands:list:*",
        "brands:top:*"
    ]
    
    if source_brand_id:
        cache_keys.append(f"brand:{source_brand_id}")
    
    # Would implement actual cache invalidation here
    log.info(f"Invalidating caches", keys=cache_keys)


async def send_webhook_notification(event: str, data: dict):
    """Send webhook notification for brand events"""
    # Would implement actual webhook sending here
    log.info(f"Sending webhook", event=event)


# Import these at the end to avoid circular imports
from fastapi import Request
from app.core.config import settings
