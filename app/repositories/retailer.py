"""
Retailer repository implementation
"""

from typing import List, Optional
from uuid import UUID

from sqlmodel import select

from app.models import Retailer
from app.repositories.base import BaseRepository


class RetailerRepository(BaseRepository[Retailer, dict, dict]):
    """Repository for retailer operations"""

    def __init__(self):
        super().__init__(Retailer)

    async def get_active_retailers(self) -> List[Retailer]:
        """Get all active retailers"""
        async with self.get_session() as session:
            statement = select(Retailer).where(Retailer.is_active == True)
            result = await session.exec(statement)
            return result.all()

    async def get_by_slug(self, slug: str) -> Optional[Retailer]:
        """Get retailer by slug"""
        async with self.get_session() as session:
            statement = select(Retailer).where(Retailer.slug == slug)
            result = await session.exec(statement)
            return result.first()

    async def get_supported_retailers(self) -> List[Retailer]:
        """Get retailers that have crawler support"""
        async with self.get_session() as session:
            statement = select(Retailer).where(
                Retailer.is_active == True, Retailer.has_crawler_support == True
            )
            result = await session.exec(statement)
            return result.all()
