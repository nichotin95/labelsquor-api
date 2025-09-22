"""
Processing Queue repository implementation
"""

from typing import List, Optional
from uuid import UUID

from sqlmodel import select

from app.models import ProcessingQueue
from app.core.database import get_session


class ProcessingQueueRepository:
    """Repository for processing queue operations"""

    def __init__(self):
        pass

    async def get_pending_items(self, limit: int = 100) -> List[ProcessingQueue]:
        """Get pending items in the processing queue"""
        async with get_session() as session:
            statement = (
                select(ProcessingQueue)
                .where(ProcessingQueue.status == "pending")
                .order_by(ProcessingQueue.priority.desc(), ProcessingQueue.created_at)
                .limit(limit)
            )
            result = await session.exec(statement)
            return result.all()

    async def get_by_source_page(self, source_page_id: UUID) -> Optional[ProcessingQueue]:
        """Get processing queue item by source page ID"""
        async with get_session() as session:
            statement = select(ProcessingQueue).where(ProcessingQueue.source_page_id == source_page_id)
            result = await session.exec(statement)
            return result.first()

    async def mark_as_processing(self, queue_id: UUID) -> bool:
        """Mark a queue item as being processed"""
        async with get_session() as session:
            item = await session.get(ProcessingQueue, queue_id)
            if item and item.status == "pending":
                item.status = "processing"
                session.add(item)
                await session.commit()
                return True
            return False

    async def mark_as_completed(self, queue_id: UUID) -> bool:
        """Mark a queue item as completed"""
        async with get_session() as session:
            item = await session.get(ProcessingQueue, queue_id)
            if item:
                item.status = "completed"
                session.add(item)
                await session.commit()
                return True
            return False

    async def mark_as_failed(self, queue_id: UUID, error_message: str = None) -> bool:
        """Mark a queue item as failed"""
        async with get_session() as session:
            item = await session.get(ProcessingQueue, queue_id)
            if item:
                item.status = "failed"
                if error_message:
                    item.error_details = {"error": error_message}
                session.add(item)
                await session.commit()
                return True
            return False
