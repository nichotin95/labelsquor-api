"""
Product processing workflow implementation using the workflow engine
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.workflow import (
    WorkflowEngine, WorkflowState, ProcessingStage, StateTransition,
    WorkflowConfig, WorkflowEvent, WorkflowEventHandler
)
from app.core.database import AsyncSessionLocal, db_retry
from app.core.logging import log
from app.models import ProcessingQueue, Product, ProductVersion
from app.services.ai_pipeline_service import AIPipelineService
from app.repositories import ProductRepository, FactsRepository


class ProductWorkflowEngine(WorkflowEngine):
    """Workflow engine for product processing"""
    
    def __init__(self, config: Optional[WorkflowConfig] = None):
        super().__init__(config)
        from app.core.config import settings
        self.ai_pipeline = AIPipelineService(settings.google_api_key or "")
        
        # Add monitoring handler
        self.add_event_handler(WorkflowMonitoringHandler())
        
        # Add notification handler
        if self.config.enable_notifications:
            self.add_event_handler(WorkflowNotificationHandler())
            
    async def get_workflow_state(self, workflow_id: str) -> WorkflowState:
        """Get current state from ProcessingQueue"""
        async with AsyncSessionLocal() as session:
            queue_item = await session.get(ProcessingQueue, UUID(workflow_id))
            if not queue_item:
                raise ValueError(f"Workflow {workflow_id} not found")
                
            # Map old status to new WorkflowState
            status_mapping = {
                "pending": WorkflowState.QUEUED,
                "processing": WorkflowState.PROCESSING,
                "completed": WorkflowState.COMPLETED,
                "failed": WorkflowState.FAILED,
                "skipped": WorkflowState.CANCELLED,
            }
            return status_mapping.get(queue_item.status, WorkflowState.CREATED)
            
    async def save_workflow_state(self, workflow_id: str, state: WorkflowState, metadata: Dict[str, Any]):
        """Save workflow state to ProcessingQueue"""
        async with AsyncSessionLocal() as session:
            # Map WorkflowState to old status
            state_mapping = {
                WorkflowState.CREATED: "pending",
                WorkflowState.QUEUED: "pending",
                WorkflowState.PROCESSING: "processing",
                WorkflowState.WAITING: "processing",
                WorkflowState.COMPLETED: "completed",
                WorkflowState.FAILED: "failed",
                WorkflowState.CANCELLED: "skipped",
                WorkflowState.RETRYING: "pending",
                WorkflowState.SUSPENDED: "failed",
            }
            
            await session.execute(
                update(ProcessingQueue)
                .where(ProcessingQueue.queue_id == UUID(workflow_id))
                .values(
                    status=state_mapping.get(state, "pending"),
                    stage_details={
                        **metadata,
                        "workflow_state": state.value,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                )
            )
            await session.commit()
            
    async def record_transition(self, workflow_id: str, transition: StateTransition):
        """Record state transition in audit table"""
        async with AsyncSessionLocal() as session:
            # Store in a new workflow_transitions table
            await session.execute(
                """
                INSERT INTO workflow_transitions 
                (workflow_id, from_state, to_state, stage, reason, metadata, created_at, actor)
                VALUES (:workflow_id, :from_state, :to_state, :stage, :reason, :metadata, :created_at, :actor)
                """,
                {
                    "workflow_id": UUID(workflow_id),
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "stage": transition.stage.value if transition.stage else None,
                    "reason": transition.reason,
                    "metadata": transition.metadata,
                    "created_at": transition.timestamp,
                    "actor": transition.actor,
                }
            )
            await session.commit()
            
    async def get_next_items(self, limit: int = 10) -> List[str]:
        """Get next items to process"""
        async with AsyncSessionLocal() as session:
            # Select items that are ready to process
            # Using FOR UPDATE SKIP LOCKED for distributed processing
            result = await session.execute(
                select(ProcessingQueue.queue_id)
                .where(ProcessingQueue.status == "pending")
                .where(
                    (ProcessingQueue.next_retry_at.is_(None)) |
                    (ProcessingQueue.next_retry_at <= datetime.utcnow())
                )
                .order_by(ProcessingQueue.priority.desc(), ProcessingQueue.queued_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            return [str(row[0]) for row in result]
            
    async def get_workflow_metadata(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow metadata from ProcessingQueue"""
        async with AsyncSessionLocal() as session:
            queue_item = await session.get(ProcessingQueue, UUID(workflow_id))
            if not queue_item:
                return {}
            return queue_item.stage_details or {}
            
    async def schedule_retry(self, workflow_id: str, retry_at: datetime):
        """Schedule a retry by updating next_retry_at"""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(ProcessingQueue)
                .where(ProcessingQueue.queue_id == UUID(workflow_id))
                .values(
                    next_retry_at=retry_at,
                    retry_count=ProcessingQueue.retry_count + 1
                )
            )
            await session.commit()
            
    async def process_stage(self, workflow_id: str, stage: ProcessingStage):
        """Process a specific stage of the workflow"""
        async with AsyncSessionLocal() as session:
            queue_item = await session.get(ProcessingQueue, UUID(workflow_id))
            if not queue_item:
                raise ValueError(f"Queue item {workflow_id} not found")
                
            # Update current stage
            queue_item.stage = stage.value
            await session.commit()
            
            # Process based on stage
            if stage == ProcessingStage.DISCOVERY:
                await self._process_discovery(queue_item)
            elif stage == ProcessingStage.IMAGE_FETCH:
                await self._process_image_fetch(queue_item)
            elif stage == ProcessingStage.ENRICHMENT:
                await self._process_enrichment(queue_item)
            elif stage == ProcessingStage.DATA_MAPPING:
                await self._process_data_mapping(queue_item)
            elif stage == ProcessingStage.SCORING:
                await self._process_scoring(queue_item)
            elif stage == ProcessingStage.INDEXING:
                await self._process_indexing(queue_item)
            elif stage == ProcessingStage.NOTIFICATION:
                await self._process_notification(queue_item)
                
    async def _process_discovery(self, queue_item: ProcessingQueue):
        """Delegate to AI pipeline service"""
        await self.ai_pipeline._process_discovery(queue_item)
        
    async def _process_image_fetch(self, queue_item: ProcessingQueue):
        """Image fetching is handled by AI service directly"""
        pass  # Skip as Gemini fetches images directly
        
    async def _process_enrichment(self, queue_item: ProcessingQueue):
        """Delegate to AI pipeline service"""
        result = await self.ai_pipeline._process_enrichment(queue_item)
        
        # Update queue item with results
        async with AsyncSessionLocal() as session:
            queue_item = await session.get(ProcessingQueue, queue_item.queue_id)
            queue_item.stage_details["ai_result"] = result
            await session.commit()
            
    async def _process_data_mapping(self, queue_item: ProcessingQueue):
        """Delegate to AI pipeline service"""
        await self.ai_pipeline._process_data_mapping(queue_item)
        
    async def _process_scoring(self, queue_item: ProcessingQueue):
        """Delegate to AI pipeline service"""
        await self.ai_pipeline._process_scoring(queue_item)
        
    async def _process_indexing(self, queue_item: ProcessingQueue):
        """Index product for search"""
        # Implement search indexing (Elasticsearch, etc.)
        log.info(f"Indexing product {queue_item.product_id}")
        
    async def _process_notification(self, queue_item: ProcessingQueue):
        """Send notifications about completed processing"""
        # Implement notification logic
        log.info(f"Sending notifications for {queue_item.product_id}")


class WorkflowMonitoringHandler(WorkflowEventHandler):
    """Handler for monitoring workflow events"""
    
    async def handle(self, event: WorkflowEvent):
        """Log and track workflow events"""
        if event.event_type == "state_changed":
            log.info(
                "Workflow state changed",
                workflow_id=event.workflow_id,
                **event.data
            )
            # Could send to monitoring system (Prometheus, DataDog, etc.)
            
        elif event.event_type == "stage_completed":
            log.info(
                "Workflow stage completed",
                workflow_id=event.workflow_id,
                **event.data
            )
            # Track stage performance metrics
            
        elif event.event_type == "error_occurred":
            log.error(
                "Workflow error",
                workflow_id=event.workflow_id,
                **event.data
            )
            # Alert on errors


class WorkflowNotificationHandler(WorkflowEventHandler):
    """Handler for sending notifications"""
    
    async def handle(self, event: WorkflowEvent):
        """Send notifications for important events"""
        if event.event_type == "state_changed" and event.data.get("to_state") == WorkflowState.FAILED.value:
            # Send alert for failed workflows
            await self.send_failure_alert(event.workflow_id, event.data)
            
        elif event.event_type == "state_changed" and event.data.get("to_state") == WorkflowState.COMPLETED.value:
            # Send completion notification
            await self.send_completion_notification(event.workflow_id)
            
    async def send_failure_alert(self, workflow_id: str, data: Dict[str, Any]):
        """Send failure alert"""
        log.warning(f"Workflow {workflow_id} failed", **data)
        # Implement actual notification (email, Slack, etc.)
        
    async def send_completion_notification(self, workflow_id: str):
        """Send completion notification"""
        log.info(f"Workflow {workflow_id} completed successfully")
        # Implement actual notification


class WorkflowOrchestrator:
    """Orchestrates multiple workflow workers"""
    
    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self.engine = ProductWorkflowEngine()
        
    async def start(self):
        """Start workflow workers"""
        workers = []
        
        for i in range(self.num_workers):
            worker_id = f"worker-{i+1}"
            worker = asyncio.create_task(self.engine.run_worker(worker_id))
            workers.append(worker)
            
        log.info(f"Started {self.num_workers} workflow workers")
        
        # Wait for all workers
        await asyncio.gather(*workers)
        
    async def stop(self):
        """Stop workflow workers"""
        # Implement graceful shutdown
        log.info("Stopping workflow workers")
        
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get detailed workflow status"""
        async with AsyncSessionLocal() as session:
            # Get queue item
            queue_item = await session.get(ProcessingQueue, UUID(workflow_id))
            if not queue_item:
                return {"error": "Workflow not found"}
                
            # Get transition history
            transitions = await session.execute(
                """
                SELECT from_state, to_state, stage, reason, created_at
                FROM workflow_transitions
                WHERE workflow_id = :workflow_id
                ORDER BY created_at DESC
                LIMIT 20
                """,
                {"workflow_id": UUID(workflow_id)}
            )
            
            return {
                "workflow_id": workflow_id,
                "current_state": queue_item.status,
                "current_stage": queue_item.stage,
                "created_at": queue_item.queued_at.isoformat(),
                "updated_at": queue_item.stage_details.get("updated_at"),
                "retry_count": queue_item.retry_count,
                "metadata": queue_item.stage_details,
                "history": [
                    {
                        "from": row.from_state,
                        "to": row.to_state,
                        "stage": row.stage,
                        "reason": row.reason,
                        "timestamp": row.created_at.isoformat(),
                    }
                    for row in transitions
                ]
            }
            
    async def retry_workflow(self, workflow_id: str) -> bool:
        """Manually retry a failed workflow"""
        return await self.engine.transition_state(
            workflow_id,
            WorkflowState.QUEUED,
            reason="Manual retry requested"
        )
        
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow"""
        return await self.engine.transition_state(
            workflow_id,
            WorkflowState.CANCELLED,
            reason="Manual cancellation"
        )
        
    async def suspend_workflow(self, workflow_id: str, reason: str) -> bool:
        """Suspend a workflow for manual intervention"""
        return await self.engine.transition_state(
            workflow_id,
            WorkflowState.SUSPENDED,
            reason=reason
        )
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get workflow metrics"""
        return self.engine.metrics.get_summary()
