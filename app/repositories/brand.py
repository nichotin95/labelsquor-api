"""
Brand repository with advanced features
"""
from typing import Optional, List
from uuid import UUID
from sqlmodel import select, func, or_
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.brand import Brand
from app.schemas.brand import BrandCreate, BrandUpdate
from app.repositories.base import BaseRepository
from app.core.logging import log


class BrandRepository(BaseRepository[Brand, BrandCreate, BrandUpdate]):
    """Repository for brand operations"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Brand, session)
    
    async def get_by_normalized_name(
        self, 
        normalized_name: str, 
        country: Optional[str] = None
    ) -> Optional[Brand]:
        """Get brand by normalized name and optional country"""
        statement = select(Brand).where(
            Brand.normalized_name == normalized_name
        )
        
        if country:
            statement = statement.where(Brand.country == country)
        
        result = await self.session.exec(statement)
        return result.first()
    
    async def search(
        self, 
        query: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[Brand]:
        """Search brands by name (case-insensitive)"""
        search_term = f"%{query}%"
        
        statement = select(Brand).where(
            or_(
                Brand.name.ilike(search_term),
                Brand.normalized_name.ilike(search_term),
                Brand.owner_company.ilike(search_term)
            )
        ).offset(skip).limit(limit)
        
        result = await self.session.exec(statement)
        return result.all()
    
    async def get_with_product_count(self, brand_id: UUID) -> Optional[dict]:
        """Get brand with product count"""
        # Using raw SQL for complex aggregation
        query = """
            SELECT 
                b.*,
                COUNT(DISTINCT p.product_id) as product_count,
                COUNT(DISTINCT p.product_id) FILTER (WHERE p.status = 'active') as active_product_count
            FROM brand b
            LEFT JOIN product p ON b.brand_id = p.brand_id
            WHERE b.brand_id = :brand_id
            GROUP BY b.brand_id
        """
        
        result = await self.session.execute(
            query, 
            {"brand_id": str(brand_id)}
        )
        row = result.first()
        
        if row:
            return {
                **row._asdict(),
                "product_count": row.product_count,
                "active_product_count": row.active_product_count
            }
        return None
    
    async def get_top_brands(
        self, 
        limit: int = 10,
        country: Optional[str] = None
    ) -> List[dict]:
        """Get top brands by product count"""
        query = """
            SELECT 
                b.*,
                COUNT(DISTINCT p.product_id) as product_count
            FROM brand b
            LEFT JOIN product p ON b.brand_id = p.brand_id
            WHERE (:country IS NULL OR b.country = :country)
            GROUP BY b.brand_id
            ORDER BY product_count DESC
            LIMIT :limit
        """
        
        result = await self.session.execute(
            query,
            {"country": country, "limit": limit}
        )
        
        return [row._asdict() for row in result.all()]
    
    async def merge_brands(
        self, 
        source_brand_id: UUID, 
        target_brand_id: UUID
    ) -> bool:
        """Merge source brand into target brand"""
        try:
            # Update all products to point to target brand
            update_query = """
                UPDATE product 
                SET brand_id = :target_id, updated_at = NOW()
                WHERE brand_id = :source_id
            """
            
            await self.session.execute(
                update_query,
                {"target_id": str(target_brand_id), "source_id": str(source_brand_id)}
            )
            
            # Delete source brand
            await self.delete(id=source_brand_id)
            
            await self.session.commit()
            
            log.info(
                "Merged brands", 
                source_id=str(source_brand_id), 
                target_id=str(target_brand_id)
            )
            return True
            
        except Exception as e:
            await self.session.rollback()
            log.error("Error merging brands", error=str(e))
            raise
