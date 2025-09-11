"""
Product repository implementation
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlmodel import select, func, or_, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.product import Product, ProductIdentifier, ProductVersion
from app.schemas.product import ProductCreate, ProductUpdate
from app.repositories.base import BaseRepository
from app.core.logging import log


class ProductRepository(BaseRepository[Product, ProductCreate, ProductUpdate]):
    """Repository for product operations"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Product, session)
    
    async def get_by_canonical_key(self, canonical_key: str) -> Optional[Product]:
        """Get product by canonical key"""
        statement = select(Product).where(
            Product.canonical_key == canonical_key,
            Product.status == "active"
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def get_by_gtin(self, gtin: str) -> Optional[Product]:
        """Get product by GTIN"""
        statement = select(Product).where(Product.gtin_primary == gtin)
        result = await self.session.exec(statement)
        return result.first()
    
    async def search(
        self,
        query: str,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Product]:
        """Search products by name or brand"""
        search_term = f"%{query}%"
        
        statement = select(Product).where(
            or_(
                Product.name.ilike(search_term),
                Product.normalized_name.ilike(search_term)
            )
        )
        
        # Apply additional filters
        if filters:
            if filters.get("brand_id"):
                statement = statement.where(Product.brand_id == filters["brand_id"])
            if filters.get("category"):
                statement = statement.where(Product.category == filters["category"])
            if filters.get("status"):
                statement = statement.where(Product.status == filters["status"])
        
        statement = statement.offset(skip).limit(limit)
        result = await self.session.exec(statement)
        return result.all()
    
    async def get_latest_version(self, product_id: UUID) -> Optional[ProductVersion]:
        """Get latest product version"""
        statement = select(ProductVersion).where(
            ProductVersion.product_id == product_id
        ).order_by(ProductVersion.version_seq.desc()).limit(1)
        
        result = await self.session.exec(statement)
        return result.first()
    
    async def create_version(self, product_id: UUID, job_run_id: Optional[UUID] = None) -> ProductVersion:
        """Create new product version"""
        # Get next version number
        count_stmt = select(func.count()).select_from(ProductVersion).where(
            ProductVersion.product_id == product_id
        )
        result = await self.session.exec(count_stmt)
        next_version = result.one() + 1
        
        # Create version
        version = ProductVersion(
            product_id=product_id,
            version_seq=next_version,
            derived_from_job_run_id=job_run_id
        )
        
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)
        
        return version
