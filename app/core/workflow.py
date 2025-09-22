"""
Advanced workflow engine with state machine and distributed locking
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, TypeVar
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import asyncio

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import AsyncSessionLocal, db_retry
from app.core.logging import log
from app.core.exceptions import BusinessLogicError


class WorkflowState(str, Enum):
    """Workflow states with clear progression"""
    # Initial states
    CREATED = "created"
    QUEUED = "queued"
    
    # Processing states
    PROCESSING = "processing"
    WAITING = "waiting"  # Waiting for external dependency
    
    # Terminal states
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
    # Recovery states
    RETRYING = "retrying"
    SUSPENDED = "suspended"  # Manual intervention needed
    
    # Partial states
    QUOTA_EXCEEDED = "quota_exceeded"  # Waiting for quota reset
    PARTIALLY_PROCESSED = "partially_processed"  # Some stages completed


class ProcessingStage(str, Enum):
    """Processing stages within the workflow"""
    DISCOVERY = "discovery"
    IMAGE_FETCH = "image_fetch"
    ENRICHMENT = "enrichment"
    DATA_MAPPING = "data_mapping"
    SCORING = "scoring"
    INDEXING = "indexing"
    NOTIFICATION = "notification"


class StateTransition(BaseModel):
    """Represents a state transition"""
    from_state: WorkflowState
    to_state: WorkflowState
    stage: Optional[ProcessingStage] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: Optional[str] = None  # Worker ID or user


class WorkflowConfig(BaseModel):
    """Configuration for workflow behavior"""
    max_retries: int = 3
    retry_backoff_base: int = 60  # seconds
    retry_backoff_multiplier: float = 2.0
    processing_timeout: int = 300  # 5 minutes
    lock_timeout: int = 30  # seconds
    enable_notifications: bool = True
    enable_metrics: bool = True


class WorkflowStateMachine:
    """State machine for workflow transitions"""
    
    # Valid state transitions
    TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
        WorkflowState.CREATED: {WorkflowState.QUEUED, WorkflowState.CANCELLED},
        WorkflowState.QUEUED: {WorkflowState.PROCESSING, WorkflowState.CANCELLED, WorkflowState.SUSPENDED},
        WorkflowState.PROCESSING: {
            WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.WAITING, 
            WorkflowState.SUSPENDED, WorkflowState.QUOTA_EXCEEDED, WorkflowState.PARTIALLY_PROCESSED
        },
        WorkflowState.WAITING: {WorkflowState.PROCESSING, WorkflowState.FAILED, WorkflowState.CANCELLED},
        WorkflowState.FAILED: {WorkflowState.RETRYING, WorkflowState.CANCELLED, WorkflowState.SUSPENDED},
        WorkflowState.RETRYING: {WorkflowState.QUEUED, WorkflowState.FAILED, WorkflowState.CANCELLED},
        WorkflowState.SUSPENDED: {WorkflowState.QUEUED, WorkflowState.CANCELLED},
        WorkflowState.QUOTA_EXCEEDED: {WorkflowState.QUEUED, WorkflowState.CANCELLED, WorkflowState.SUSPENDED},
        WorkflowState.PARTIALLY_PROCESSED: {WorkflowState.QUEUED, WorkflowState.PROCESSING, WorkflowState.CANCELLED},
        WorkflowState.COMPLETED: set(),  # Terminal state
        WorkflowState.CANCELLED: set(),  # Terminal state
    }
    
    # Stages allowed in each state
    STAGE_STATES: Dict[WorkflowState, Set[ProcessingStage]] = {
        WorkflowState.PROCESSING: set(ProcessingStage),
        WorkflowState.WAITING: set(ProcessingStage),
    }
    
    @classmethod
    def can_transition(cls, from_state: WorkflowState, to_state: WorkflowState) -> bool:
        """Check if a state transition is valid"""
        return to_state in cls.TRANSITIONS.get(from_state, set())
    
    @classmethod
    def is_terminal(cls, state: WorkflowState) -> bool:
        """Check if a state is terminal"""
        return state in {WorkflowState.COMPLETED, WorkflowState.CANCELLED}
    
    @classmethod
    def is_active(cls, state: WorkflowState) -> bool:
        """Check if a state represents active processing"""
        return state in {WorkflowState.PROCESSING, WorkflowState.WAITING}
    
    @classmethod
    def can_retry(cls, state: WorkflowState) -> bool:
        """Check if retry is possible from this state"""
        return state == WorkflowState.FAILED


class WorkflowLock:
    """Distributed lock for workflow items using PostgreSQL advisory locks"""
    
    def __init__(self, workflow_id: str, lock_timeout: int = 30):
        self.workflow_id = workflow_id
        self.lock_timeout = lock_timeout
        self.lock_id = hash(workflow_id) % 2147483647  # PostgreSQL int4 range
        self.session = None
        
    async def __aenter__(self):
        """Acquire lock"""
        self.session = AsyncSessionLocal()
        
        # Try to acquire advisory lock with timeout
        result = await self.session.execute(
            f"SELECT pg_try_advisory_lock({self.lock_id})"
        )
        locked = result.scalar()
        
        if not locked:
            await self.session.close()
            raise BusinessLogicError(f"Could not acquire lock for workflow {self.workflow_id}")
            
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release lock"""
        if self.session:
            await self.session.execute(
                f"SELECT pg_advisory_unlock({self.lock_id})"
            )
            await self.session.close()


class WorkflowEvent(BaseModel):
    """Event emitted by workflow state changes"""
    workflow_id: str
    event_type: str  # state_changed, stage_completed, error_occurred
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEventHandler(ABC):
    """Abstract base for workflow event handlers"""
    
    @abstractmethod
    async def handle(self, event: WorkflowEvent) -> None:
        """Handle a workflow event"""
        pass


class WorkflowMetrics:
    """Metrics collection for workflow performance"""
    
    def __init__(self):
        self.state_durations: Dict[str, List[float]] = {}
        self.stage_durations: Dict[str, List[float]] = {}
        self.retry_counts: Dict[str, int] = {}
        self.error_counts: Dict[str, int] = {}
        
    async def record_state_duration(self, workflow_id: str, state: WorkflowState, duration: float):
        """Record how long a workflow spent in a state"""
        if state not in self.state_durations:
            self.state_durations[state] = []
        self.state_durations[state].append(duration)
        
    async def record_stage_duration(self, workflow_id: str, stage: ProcessingStage, duration: float):
        """Record how long a stage took to process"""
        if stage not in self.stage_durations:
            self.stage_durations[stage] = []
        self.stage_durations[stage].append(duration)
        
    async def increment_retry(self, workflow_id: str):
        """Increment retry counter"""
        self.retry_counts[workflow_id] = self.retry_counts.get(workflow_id, 0) + 1
        
    async def increment_error(self, error_type: str):
        """Increment error counter"""
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        return {
            "state_avg_durations": {
                state: sum(durations) / len(durations) if durations else 0
                for state, durations in self.state_durations.items()
            },
            "stage_avg_durations": {
                stage: sum(durations) / len(durations) if durations else 0
                for stage, durations in self.stage_durations.items()
            },
            "total_retries": sum(self.retry_counts.values()),
            "error_breakdown": self.error_counts,
        }


T = TypeVar('T', bound='WorkflowEngine')


class WorkflowEngine(ABC):
    """Abstract workflow engine for processing items through stages"""
    
    def __init__(self, config: Optional[WorkflowConfig] = None):
        self.config = config or WorkflowConfig()
        self.state_machine = WorkflowStateMachine()
        self.metrics = WorkflowMetrics()
        self.event_handlers: List[WorkflowEventHandler] = []
        
    def add_event_handler(self, handler: WorkflowEventHandler):
        """Add an event handler"""
        self.event_handlers.append(handler)
        
    async def emit_event(self, event: WorkflowEvent):
        """Emit an event to all handlers"""
        for handler in self.event_handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                log.error(f"Event handler error: {e}", event=event.dict())
                
    @abstractmethod
    async def get_workflow_state(self, workflow_id: str) -> WorkflowState:
        """Get current state of a workflow"""
        pass
        
    @abstractmethod
    async def save_workflow_state(self, workflow_id: str, state: WorkflowState, metadata: Dict[str, Any]):
        """Save workflow state"""
        pass
        
    @abstractmethod
    async def record_transition(self, workflow_id: str, transition: StateTransition):
        """Record a state transition"""
        pass
        
    @abstractmethod
    async def get_next_items(self, limit: int = 10) -> List[str]:
        """Get next items to process"""
        pass
        
    async def transition_state(
        self,
        workflow_id: str,
        to_state: WorkflowState,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Transition workflow to a new state"""
        async with WorkflowLock(workflow_id, self.config.lock_timeout):
            current_state = await self.get_workflow_state(workflow_id)
            
            # Check if transition is valid
            if not self.state_machine.can_transition(current_state, to_state):
                log.warning(
                    f"Invalid state transition attempted",
                    workflow_id=workflow_id,
                    from_state=current_state,
                    to_state=to_state
                )
                return False
                
            # Record transition
            transition = StateTransition(
                from_state=current_state,
                to_state=to_state,
                reason=reason,
                metadata=metadata or {},
            )
            await self.record_transition(workflow_id, transition)
            
            # Save new state
            await self.save_workflow_state(workflow_id, to_state, metadata or {})
            
            # Emit event
            await self.emit_event(WorkflowEvent(
                workflow_id=workflow_id,
                event_type="state_changed",
                data={
                    "from_state": current_state.value,
                    "to_state": to_state.value,
                    "reason": reason,
                }
            ))
            
            log.info(
                f"State transition successful",
                workflow_id=workflow_id,
                from_state=current_state,
                to_state=to_state,
                reason=reason
            )
            return True
            
    async def process_item(self, workflow_id: str) -> bool:
        """Process a single workflow item"""
        try:
            # Acquire lock and transition to processing
            if not await self.transition_state(workflow_id, WorkflowState.PROCESSING):
                return False
                
            # Process through stages
            for stage in ProcessingStage:
                stage_start = datetime.utcnow()
                
                try:
                    # Process stage
                    await self.process_stage(workflow_id, stage)
                    
                    # Record metrics
                    duration = (datetime.utcnow() - stage_start).total_seconds()
                    await self.metrics.record_stage_duration(workflow_id, stage, duration)
                    
                    # Emit stage completed event
                    await self.emit_event(WorkflowEvent(
                        workflow_id=workflow_id,
                        event_type="stage_completed",
                        data={"stage": stage.value, "duration": duration}
                    ))
                    
                except Exception as e:
                    log.error(f"Stage processing failed", workflow_id=workflow_id, stage=stage, error=str(e))
                    await self.handle_error(workflow_id, stage, e)
                    return False
                    
            # Mark as completed
            await self.transition_state(workflow_id, WorkflowState.COMPLETED)
            return True
            
        except Exception as e:
            log.error(f"Workflow processing failed", workflow_id=workflow_id, error=str(e))
            await self.handle_error(workflow_id, None, e)
            return False
            
    @abstractmethod
    async def process_stage(self, workflow_id: str, stage: ProcessingStage):
        """Process a specific stage"""
        pass
        
    async def handle_error(self, workflow_id: str, stage: Optional[ProcessingStage], error: Exception):
        """Handle processing errors"""
        await self.metrics.increment_error(type(error).__name__)
        
        # Get current retry count
        metadata = await self.get_workflow_metadata(workflow_id)
        retry_count = metadata.get("retry_count", 0)
        
        if retry_count < self.config.max_retries:
            # Calculate backoff
            backoff = self.config.retry_backoff_base * (self.config.retry_backoff_multiplier ** retry_count)
            next_retry = datetime.utcnow() + timedelta(seconds=backoff)
            
            # Transition to retrying
            await self.transition_state(
                workflow_id,
                WorkflowState.RETRYING,
                reason=f"Error: {str(error)}",
                metadata={
                    "retry_count": retry_count + 1,
                    "next_retry_at": next_retry.isoformat(),
                    "last_error": str(error),
                    "failed_stage": stage.value if stage else None,
                }
            )
            
            # Schedule retry
            await self.schedule_retry(workflow_id, next_retry)
            
        else:
            # Max retries exceeded
            await self.transition_state(
                workflow_id,
                WorkflowState.FAILED,
                reason=f"Max retries exceeded. Last error: {str(error)}",
                metadata={
                    "final_error": str(error),
                    "failed_stage": stage.value if stage else None,
                    "retry_count": retry_count,
                }
            )
            
    @abstractmethod
    async def get_workflow_metadata(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow metadata"""
        pass
        
    @abstractmethod
    async def schedule_retry(self, workflow_id: str, retry_at: datetime):
        """Schedule a retry"""
        pass
        
    async def run_worker(self, worker_id: str):
        """Run a worker that processes items"""
        log.info(f"Starting workflow worker", worker_id=worker_id)
        
        while True:
            try:
                # Get next items to process
                items = await self.get_next_items(limit=10)
                
                if not items:
                    # No items, wait
                    await asyncio.sleep(5)
                    continue
                    
                # Process items concurrently
                tasks = [self.process_item(item) for item in items]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Log results
                success_count = sum(1 for r in results if r is True)
                log.info(f"Processed batch", worker_id=worker_id, total=len(items), success=success_count)
                
            except Exception as e:
                log.error(f"Worker error", worker_id=worker_id, error=str(e))
                await asyncio.sleep(10)  # Back off on error
