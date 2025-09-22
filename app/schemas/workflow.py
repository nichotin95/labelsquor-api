"""
Workflow management schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowTransition(BaseModel):
    """Workflow state transition"""
    transition_id: str
    from_state: str
    to_state: str
    stage: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    actor: Optional[str] = None


class WorkflowStatusResponse(BaseModel):
    """Workflow status response"""
    workflow_id: UUID
    current_state: str
    current_stage: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    history: Optional[List[Dict[str, Any]]] = None


class WorkflowListItem(BaseModel):
    """Workflow list item"""
    workflow_id: str
    state: str
    stage: Optional[str] = None
    priority: int
    retry_count: int
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_error: Optional[str] = None


class WorkflowListResponse(BaseModel):
    """Workflow list response"""
    items: List[WorkflowListItem]
    total: int
    skip: int
    limit: int


class WorkflowActionRequest(BaseModel):
    """Request for workflow actions"""
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowActionResponse(BaseModel):
    """Response for workflow actions"""
    success: bool
    message: str
    workflow_id: Optional[str] = None


class WorkflowHistoryResponse(BaseModel):
    """Workflow history response"""
    workflow_id: UUID
    transitions: List[Dict[str, Any]]


class WorkflowMetricsResponse(BaseModel):
    """Workflow metrics response"""
    time_range: str
    state_distribution: Dict[str, int]
    avg_duration_seconds: float
    min_duration_seconds: float
    max_duration_seconds: float
    median_duration_seconds: float
    p95_duration_seconds: float
    error_rate: float
    total_processed: int
    throughput_per_hour: List[Dict[str, Any]]


class WorkflowEventSchema(BaseModel):
    """Workflow event schema for webhooks/notifications"""
    event_id: str
    workflow_id: str
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]


class WorkflowStageMetrics(BaseModel):
    """Metrics for a specific workflow stage"""
    stage: str
    count: int
    avg_duration: float
    success_rate: float
    errors: Dict[str, int]
