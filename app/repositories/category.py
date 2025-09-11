"""
Category repository implementation
"""
from typing import Optional, List
from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.category import Category, ProductCategoryMap
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category, CategoryCreate, CategoryUpdate]):
    """Repository for category operations"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Category, session)
    
    async def get_by_slug(self, slug: str, locale: str = "en") -> Optional[Category]:
        """Get category by slug and locale"""
        statement = select(Category).where(
            Category.slug == slug,
            Category.locale == locale
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def get_children(self, parent_id: Optional[UUID] = None) -> List[Category]:
        """Get child categories"""
        statement = select(Category).where(Category.parent_id == parent_id)
        result = await self.session.exec(statement)
        return result.all()
