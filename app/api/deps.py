"""
API Dependencies for dependency injection
"""
from typing import AsyncGenerator, Optional, Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel.ext.asyncio.session import AsyncSession
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.database import get_async_session
from app.core.config import settings
from app.core.logging import log
from app.repositories import BrandRepository, ProductRepository, CategoryRepository
from app.services import BrandService, ProductService
from app.schemas.common import PaginationParams


# Security
security = HTTPBearer()


class TokenData(BaseModel):
    """JWT Token data"""
    sub: str
    exp: int
    type: str = "access"
    scopes: list[str] = []


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """Extract and validate JWT token"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        token_data = TokenData(**payload)
        
        if token_data.type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        return token_data
        
    except JWTError as e:
        log.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    authorization: Optional[str] = Header(None)
) -> Optional[TokenData]:
    """Optional authentication - returns None if no token"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return TokenData(**payload)
    except:
        return None


# Database session
AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]


# Repositories
async def get_brand_repository(
    session: AsyncSessionDep
) -> BrandRepository:
    """Get brand repository instance"""
    return BrandRepository(session)


async def get_product_repository(
    session: AsyncSessionDep
) -> ProductRepository:
    """Get product repository instance"""
    return ProductRepository(session)


async def get_category_repository(
    session: AsyncSessionDep
) -> CategoryRepository:
    """Get category repository instance"""
    return CategoryRepository(session)


BrandRepoDep = Annotated[BrandRepository, Depends(get_brand_repository)]
ProductRepoDep = Annotated[ProductRepository, Depends(get_product_repository)]
CategoryRepoDep = Annotated[CategoryRepository, Depends(get_category_repository)]


# Services
async def get_brand_service(
    brand_repo: BrandRepoDep
) -> BrandService:
    """Get brand service instance"""
    return BrandService(brand_repo)


async def get_product_service(
    product_repo: ProductRepoDep,
    brand_repo: BrandRepoDep,
    category_repo: CategoryRepoDep
) -> ProductService:
    """Get product service instance"""
    return ProductService(product_repo, brand_repo, category_repo)


BrandServiceDep = Annotated[BrandService, Depends(get_brand_service)]
ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]


# Common parameters
async def get_pagination(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return")
) -> PaginationParams:
    """Get pagination parameters"""
    return PaginationParams(skip=skip, limit=limit)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination)]


# Request ID and correlation
async def get_request_id(
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID")
) -> str:
    """Get or generate request ID"""
    if x_request_id:
        return x_request_id
    
    import uuid
    return str(uuid.uuid4())


RequestIdDep = Annotated[str, Depends(get_request_id)]


# Feature flags
class FeatureFlags(BaseModel):
    """Feature flags from config"""
    enable_ocr: bool
    enable_barcode_scan: bool
    enable_graphql: bool
    enable_webhooks: bool


async def get_feature_flags() -> FeatureFlags:
    """Get current feature flags"""
    return FeatureFlags(
        enable_ocr=settings.ENABLE_OCR,
        enable_barcode_scan=settings.ENABLE_BARCODE_SCAN,
        enable_graphql=settings.ENABLE_GRAPHQL,
        enable_webhooks=settings.ENABLE_WEBHOOKS
    )


FeatureFlagsDep = Annotated[FeatureFlags, Depends(get_feature_flags)]


# Rate limiting check (if using API key rate limiting)
async def check_rate_limit(
    request_id: RequestIdDep,
    user: Optional[TokenData] = Depends(get_current_user_optional)
) -> None:
    """Check rate limits for the current user/IP"""
    # This would integrate with your rate limiting backend
    # For now, it's a placeholder
    pass


RateLimitDep = Annotated[None, Depends(check_rate_limit)]
