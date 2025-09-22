"""
Quota management API endpoints
"""

from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import AsyncSessionDep, get_current_user, TokenData
from app.core.logging import log
from app.services.enhanced_product_workflow import EnhancedProductWorkflowEngine
from app.schemas.quota import (
    QuotaStatusResponse,
    QuotaUsageHistoryResponse,
    QuotaLimitResponse,
    WorkflowResumeResponse,
)

router = APIRouter(prefix="/quota")

# Global workflow engine instance
workflow_engine = EnhancedProductWorkflowEngine()


@router.get("/status", response_model=QuotaStatusResponse)
async def get_quota_status(
    service: str = Query("gemini", description="Service name to check quota for"),
    current_user: Optional[TokenData] = Depends(get_current_user),
) -> QuotaStatusResponse:
    """Get current quota status for a service"""
    try:
        all_status = await workflow_engine.get_quota_status()
        
        if service not in all_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service}' not found"
            )
        
        service_status = all_status[service]
        
        # Calculate reset times
        reset_times = {}
        for quota_type, info in service_status["quotas"].items():
            if info["remaining"] == 0:
                if "per_minute" in quota_type:
                    reset_at = datetime.utcnow() + timedelta(seconds=60)
                    reset_times[quota_type] = {
                        "reset_at": reset_at.isoformat(),
                        "seconds_until_reset": 60
                    }
                elif "per_day" in quota_type:
                    # Calculate seconds until midnight UTC
                    now = datetime.utcnow()
                    midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
                    seconds_until_reset = int((midnight - now).total_seconds())
                    reset_times[quota_type] = {
                        "reset_at": midnight.isoformat(),
                        "seconds_until_reset": seconds_until_reset
                    }
        
        return QuotaStatusResponse(
            service=service,
            quotas=service_status["quotas"],
            cost_tracking=service_status["cost_tracking"],
            reset_times=reset_times,
            is_available=all(info["remaining"] > 0 for info in service_status["quotas"].values())
        )
        
    except Exception as e:
        log.error(f"Error getting quota status", service=service, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quota status"
        )


@router.get("/usage/history", response_model=QuotaUsageHistoryResponse)
async def get_quota_usage_history(
    session: AsyncSessionDep,
    service: str = Query("gemini", description="Service name"),
    time_range: str = Query("24h", description="Time range (1h, 24h, 7d)"),
) -> QuotaUsageHistoryResponse:
    """Get quota usage history"""
    # Map time range to interval
    intervals = {
        "1h": "1 hour",
        "24h": "24 hours",
        "7d": "7 days",
    }
    interval = intervals.get(time_range, "24 hours")
    
    query = """
        SELECT * FROM get_quota_usage_summary(:service, :interval::interval)
    """
    
    result = await session.execute(query, {"service": service, "interval": interval})
    
    usage_history = []
    total_requests = 0
    total_tokens = 0
    total_cost = 0.0
    
    for row in result:
        usage_history.append({
            "hour": row.hour.isoformat(),
            "requests": row.requests,
            "total_tokens": row.total_tokens,
            "total_cost": float(row.total_cost) if row.total_cost else 0.0,
            "avg_tokens_per_request": float(row.avg_tokens_per_request) if row.avg_tokens_per_request else 0.0,
            "quota_exceeded_count": row.quota_exceeded_count,
        })
        total_requests += row.requests
        total_tokens += row.total_tokens or 0
        total_cost += float(row.total_cost) if row.total_cost else 0.0
    
    return QuotaUsageHistoryResponse(
        service=service,
        time_range=time_range,
        usage_history=usage_history,
        summary={
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "avg_cost_per_request": total_cost / total_requests if total_requests > 0 else 0.0,
        }
    )


@router.get("/limits", response_model=list[QuotaLimitResponse])
async def get_quota_limits(
    session: AsyncSessionDep,
    service: Optional[str] = Query(None, description="Filter by service"),
) -> list[QuotaLimitResponse]:
    """Get configured quota limits"""
    query = """
        SELECT 
            service_name,
            quota_type,
            limit_value,
            window_seconds,
            is_active,
            updated_at
        FROM quota_limits
        WHERE is_active = true
    """
    
    params = {}
    if service:
        query += " AND service_name = :service"
        params["service"] = service
    
    query += " ORDER BY service_name, quota_type"
    
    result = await session.execute(query, params)
    
    limits = []
    for row in result:
        limits.append(QuotaLimitResponse(
            service_name=row.service_name,
            quota_type=row.quota_type,
            limit_value=row.limit_value,
            window_seconds=row.window_seconds,
            window_description=f"{row.window_seconds // 60} minutes" if row.window_seconds < 3600 else f"{row.window_seconds // 3600} hours",
            is_active=row.is_active,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        ))
    
    return limits


@router.get("/exceeded/workflows")
async def get_quota_exceeded_workflows(
    session: AsyncSessionDep,
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Get workflows that are blocked due to quota limits"""
    query = """
        SELECT 
            queue_id,
            product_id,
            workflow_state,
            stage,
            quota_exceeded_count,
            next_retry_at,
            quota_exceeded_at,
            wait_seconds,
            progress_percentage,
            product_name,
            brand_name
        FROM vw_quota_exceeded_workflows
        LIMIT :limit
    """
    
    result = await session.execute(query, {"limit": limit})
    
    workflows = []
    for row in result:
        workflows.append({
            "workflow_id": str(row.queue_id),
            "product_id": str(row.product_id) if row.product_id else None,
            "product_name": row.product_name,
            "brand_name": row.brand_name,
            "state": row.workflow_state,
            "stage": row.stage,
            "quota_exceeded_count": row.quota_exceeded_count,
            "next_retry_at": row.next_retry_at.isoformat() if row.next_retry_at else None,
            "quota_exceeded_at": row.quota_exceeded_at,
            "wait_seconds": int(row.wait_seconds) if row.wait_seconds else None,
            "progress_percentage": float(row.progress_percentage) if row.progress_percentage else 0.0,
        })
    
    return {
        "total": len(workflows),
        "workflows": workflows,
    }


@router.post("/exceeded/resume", response_model=WorkflowResumeResponse)
async def resume_quota_exceeded_workflows(
    current_user: TokenData = Depends(get_current_user),
) -> WorkflowResumeResponse:
    """Resume workflows that were stopped due to quota limits"""
    try:
        # Check current quota status first
        status = await workflow_engine.get_quota_status()
        gemini_status = status.get("gemini", {})
        
        # Check if quota is available
        is_available = all(
            info["remaining"] > 0 
            for info in gemini_status.get("quotas", {}).values()
        )
        
        if not is_available:
            # Get reset time
            reset_info = await _get_next_reset_time(gemini_status)
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Quota still exceeded",
                    "message": "Cannot resume workflows - quota is still exceeded",
                    "next_reset": reset_info,
                },
                headers={"Retry-After": str(reset_info.get("seconds", 60))}
            )
        
        # Resume workflows
        resumed_count = await workflow_engine.resume_quota_exceeded_workflows()
        
        return WorkflowResumeResponse(
            success=True,
            resumed_count=resumed_count,
            message=f"Successfully resumed {resumed_count} workflows",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error resuming workflows", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume workflows"
        )


@router.get("/reset-times")
async def get_quota_reset_times(
    session: AsyncSessionDep,
    service: str = Query("gemini", description="Service name"),
) -> dict:
    """Get estimated quota reset times"""
    query = """
        SELECT * FROM estimate_quota_reset_time(:service)
    """
    
    result = await session.execute(query, {"service": service})
    
    reset_times = []
    for row in result:
        reset_times.append({
            "quota_type": row.quota_type,
            "reset_at": row.reset_at.isoformat() if row.reset_at else None,
            "seconds_until_reset": row.seconds_until_reset,
            "human_readable": _format_duration(row.seconds_until_reset),
        })
    
    return {
        "service": service,
        "reset_times": reset_times,
        "checked_at": datetime.utcnow().isoformat(),
    }


def _format_duration(seconds: int) -> str:
    """Format seconds into human readable duration"""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"


async def _get_next_reset_time(quota_status: dict) -> dict:
    """Get the next reset time from quota status"""
    min_reset_seconds = None
    reset_quota_type = None
    
    for quota_type, info in quota_status.get("quotas", {}).items():
        if info["remaining"] == 0:
            if "per_minute" in quota_type:
                seconds = 60
            elif "per_day" in quota_type:
                now = datetime.utcnow()
                midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
                seconds = int((midnight - now).total_seconds())
            else:
                continue
            
            if min_reset_seconds is None or seconds < min_reset_seconds:
                min_reset_seconds = seconds
                reset_quota_type = quota_type
    
    if min_reset_seconds:
        return {
            "quota_type": reset_quota_type,
            "reset_at": (datetime.utcnow() + timedelta(seconds=min_reset_seconds)).isoformat(),
            "seconds": min_reset_seconds,
            "human_readable": _format_duration(min_reset_seconds),
        }
    
    return {"seconds": 0}
