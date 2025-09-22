"""
Source page repository implementation
"""

from typing import List, Optional
from uuid import UUID

from sqlmodel import select

from app.models import SourcePage
from app.repositories.base import BaseRepository


class SourcePageRepository(BaseRepository[SourcePage, dict, dict]):
    """Repository for source page operations"""

    def __init__(self):
        super().__init__(SourcePage)

    async def get_by_url(self, url: str) -> Optional[SourcePage]:
        """Get source page by URL"""
        async with self.get_session() as session:
            statement = select(SourcePage).where(SourcePage.url == url)
            result = await session.exec(statement)
            return result.first()

    async def get_by_retailer(self, retailer_id: UUID) -> List[SourcePage]:
        """Get all source pages for a retailer"""
        async with self.get_session() as session:
            statement = select(SourcePage).where(SourcePage.retailer_id == retailer_id)
            result = await session.exec(statement)
            return result.all()

    async def get_pending_crawl(self, limit: int = 100) -> List[SourcePage]:
        """Get source pages pending crawl"""
        async with self.get_session() as session:
            statement = (
                select(SourcePage)
                .where(SourcePage.crawl_status.in_(["pending", "failed"]))
                .limit(limit)
            )
            result = await session.exec(statement)
            return result.all()
