"""
Workflow management API endpoints
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.deps import AsyncSessionDep, get_current_user, TokenData
from app.core.logging import log
from app.schemas.workflow import (
    WorkflowStatusResponse,
    WorkflowListResponse,
    WorkflowActionRequest,
    WorkflowActionResponse,
    WorkflowMetricsResponse,
    WorkflowHistoryResponse,
)
from app.services.product_workflow import WorkflowOrchestrator

router = APIRouter(prefix="/workflow")

# Global orchestrator instance (in production, this would be managed differently)
orchestrator = WorkflowOrchestrator()


@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: UUID,
    include_history: bool = Query(False, description="Include state transition history"),
    current_user: Optional[TokenData] = Depends(get_current_user),
) -> WorkflowStatusResponse:
    """Get detailed workflow status"""
    try:
        status = await orchestrator.get_workflow_status(str(workflow_id))
        
        if "error" in status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=status["error"]
            )
            
        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            current_state=status["current_state"],
            current_stage=status.get("current_stage"),
            created_at=status["created_at"],
            updated_at=status.get("updated_at"),
            retry_count=status["retry_count"],
            metadata=status["metadata"],
            history=status["history"] if include_history else None,
        )
        
    except Exception as e:
        log.error(f"Error getting workflow status", workflow_id=workflow_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workflow status"
        )


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    session: AsyncSessionDep,
    state: Optional[str] = Query(None, description="Filter by workflow state"),
    stage: Optional[str] = Query(None, description="Filter by current stage"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
) -> WorkflowListResponse:
    """List workflows with filtering"""
    query = """
        SELECT 
            queue_id, 
            workflow_state, 
            stage, 
            priority,
            retry_count,
            queued_at,
            processing_started_at,
            completed_at,
            last_error
        FROM processing_queue
        WHERE 1=1
    """
    
    params = {}
    
    if state:
        query += " AND workflow_state = :state"
        params["state"] = state
        
    if stage:
        query += " AND stage = :stage"
        params["stage"] = stage
        
    query += " ORDER BY queued_at DESC LIMIT :limit OFFSET :skip"
    params["limit"] = limit
    params["skip"] = skip
    
    result = await session.execute(query, params)
    items = []
    
    for row in result:
        items.append({
            "workflow_id": str(row.queue_id),
            "state": row.workflow_state,
            "stage": row.stage,
            "priority": row.priority,
            "retry_count": row.retry_count,
            "queued_at": row.queued_at.isoformat() if row.queued_at else None,
            "started_at": row.processing_started_at.isoformat() if row.processing_started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "last_error": row.last_error,
        })
        
    # Get total count
    count_query = "SELECT COUNT(*) FROM processing_queue WHERE 1=1"
    if state:
        count_query += " AND workflow_state = :state"
    if stage:
        count_query += " AND stage = :stage"
        
    total_result = await session.execute(count_query, params)
    total = total_result.scalar()
    
    return WorkflowListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/{workflow_id}/retry", response_model=WorkflowActionResponse)
async def retry_workflow(
    workflow_id: UUID,
    current_user: TokenData = Depends(get_current_user),
) -> WorkflowActionResponse:
    """Retry a failed workflow"""
    try:
        success = await orchestrator.retry_workflow(str(workflow_id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot retry workflow in its current state"
            )
            
        return WorkflowActionResponse(
            success=True,
            message=f"Workflow {workflow_id} queued for retry",
        )
        
    except Exception as e:
        log.error(f"Error retrying workflow", workflow_id=workflow_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry workflow"
        )


@router.post("/{workflow_id}/cancel", response_model=WorkflowActionResponse)
async def cancel_workflow(
    workflow_id: UUID,
    current_user: TokenData = Depends(get_current_user),
) -> WorkflowActionResponse:
    """Cancel a workflow"""
    try:
        success = await orchestrator.cancel_workflow(str(workflow_id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel workflow in its current state"
            )
            
        return WorkflowActionResponse(
            success=True,
            message=f"Workflow {workflow_id} cancelled",
        )
        
    except Exception as e:
        log.error(f"Error cancelling workflow", workflow_id=workflow_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel workflow"
        )


@router.post("/{workflow_id}/suspend", response_model=WorkflowActionResponse)
async def suspend_workflow(
    workflow_id: UUID,
    request: WorkflowActionRequest,
    current_user: TokenData = Depends(get_current_user),
) -> WorkflowActionResponse:
    """Suspend a workflow for manual intervention"""
    try:
        success = await orchestrator.suspend_workflow(
            str(workflow_id),
            reason=request.reason
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot suspend workflow in its current state"
            )
            
        return WorkflowActionResponse(
            success=True,
            message=f"Workflow {workflow_id} suspended",
        )
        
    except Exception as e:
        log.error(f"Error suspending workflow", workflow_id=workflow_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to suspend workflow"
        )


@router.get("/{workflow_id}/history", response_model=WorkflowHistoryResponse)
async def get_workflow_history(
    workflow_id: UUID,
    session: AsyncSessionDep,
    limit: int = Query(50, ge=1, le=100, description="Number of transitions to return"),
) -> WorkflowHistoryResponse:
    """Get workflow state transition history"""
    query = """
        SELECT 
            transition_id,
            from_state,
            to_state,
            stage,
            reason,
            metadata,
            created_at,
            actor
        FROM workflow_transitions
        WHERE workflow_id = :workflow_id
        ORDER BY created_at DESC
        LIMIT :limit
    """
    
    result = await session.execute(query, {"workflow_id": workflow_id, "limit": limit})
    transitions = []
    
    for row in result:
        transitions.append({
            "transition_id": str(row.transition_id),
            "from_state": row.from_state,
            "to_state": row.to_state,
            "stage": row.stage,
            "reason": row.reason,
            "metadata": row.metadata,
            "created_at": row.created_at.isoformat(),
            "actor": row.actor,
        })
        
    return WorkflowHistoryResponse(
        workflow_id=workflow_id,
        transitions=transitions,
    )


@router.get("/metrics", response_model=WorkflowMetricsResponse)
async def get_workflow_metrics(
    session: AsyncSessionDep,
    time_range: str = Query("24h", description="Time range for metrics (1h, 24h, 7d, 30d)"),
) -> WorkflowMetricsResponse:
    """Get workflow performance metrics"""
    # Calculate time filter
    time_filters = {
        "1h": "1 hour",
        "24h": "24 hours",
        "7d": "7 days",
        "30d": "30 days",
    }
    time_filter = time_filters.get(time_range, "24 hours")
    
    # Get state distribution
    state_query = """
        SELECT workflow_state, COUNT(*) as count
        FROM processing_queue
        WHERE queued_at >= NOW() - INTERVAL :time_filter
        GROUP BY workflow_state
    """
    
    state_result = await session.execute(state_query, {"time_filter": time_filter})
    state_distribution = {row.workflow_state: row.count for row in state_result}
    
    # Get average processing times
    duration_query = """
        SELECT 
            AVG(EXTRACT(EPOCH FROM (completed_at - queued_at))) as avg_duration,
            MIN(EXTRACT(EPOCH FROM (completed_at - queued_at))) as min_duration,
            MAX(EXTRACT(EPOCH FROM (completed_at - queued_at))) as max_duration,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - queued_at))) as median_duration,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - queued_at))) as p95_duration
        FROM processing_queue
        WHERE completed_at IS NOT NULL
        AND queued_at >= NOW() - INTERVAL :time_filter
    """
    
    duration_result = await session.execute(duration_query, {"time_filter": time_filter})
    duration_row = duration_result.first()
    
    # Get error rates
    error_query = """
        SELECT 
            COUNT(*) FILTER (WHERE workflow_state = 'failed') as failed_count,
            COUNT(*) as total_count
        FROM processing_queue
        WHERE queued_at >= NOW() - INTERVAL :time_filter
    """
    
    error_result = await session.execute(error_query, {"time_filter": time_filter})
    error_row = error_result.first()
    
    error_rate = (error_row.failed_count / error_row.total_count * 100) if error_row.total_count > 0 else 0
    
    # Get throughput
    throughput_query = """
        SELECT 
            DATE_TRUNC('hour', completed_at) as hour,
            COUNT(*) as count
        FROM processing_queue
        WHERE completed_at >= NOW() - INTERVAL :time_filter
        GROUP BY hour
        ORDER BY hour DESC
    """
    
    throughput_result = await session.execute(throughput_query, {"time_filter": time_filter})
    throughput = [
        {"hour": row.hour.isoformat(), "count": row.count}
        for row in throughput_result
    ]
    
    return WorkflowMetricsResponse(
        time_range=time_range,
        state_distribution=state_distribution,
        avg_duration_seconds=duration_row.avg_duration if duration_row else 0,
        min_duration_seconds=duration_row.min_duration if duration_row else 0,
        max_duration_seconds=duration_row.max_duration if duration_row else 0,
        median_duration_seconds=duration_row.median_duration if duration_row else 0,
        p95_duration_seconds=duration_row.p95_duration if duration_row else 0,
        error_rate=error_rate,
        total_processed=error_row.total_count if error_row else 0,
        throughput_per_hour=throughput,
    )


@router.post("/workers/start")
async def start_workers(
    background_tasks: BackgroundTasks,
    num_workers: int = Query(4, ge=1, le=20, description="Number of workers to start"),
    current_user: TokenData = Depends(get_current_user),
) -> WorkflowActionResponse:
    """Start workflow workers"""
    background_tasks.add_task(orchestrator.start)
    
    return WorkflowActionResponse(
        success=True,
        message=f"Starting {num_workers} workflow workers",
    )


@router.post("/workers/stop")
async def stop_workers(
    current_user: TokenData = Depends(get_current_user),
) -> WorkflowActionResponse:
    """Stop workflow workers"""
    await orchestrator.stop()
    
    return WorkflowActionResponse(
        success=True,
        message="Workflow workers stopped",
    )
