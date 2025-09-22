"""
Quota management schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QuotaInfo(BaseModel):
    """Individual quota information"""
    used: int
    limit: int
    remaining: int
    percentage: float
    window_start: str


class CostTracking(BaseModel):
    """Cost tracking information"""
    total_tokens: int
    total_requests: int
    total_cost_usd: float
    breakdown: Dict[str, int]


class QuotaResetTime(BaseModel):
    """Quota reset time information"""
    reset_at: str
    seconds_until_reset: int


class QuotaStatusResponse(BaseModel):
    """Quota status response"""
    service: str
    quotas: Dict[str, QuotaInfo]
    cost_tracking: CostTracking
    reset_times: Dict[str, QuotaResetTime]
    is_available: bool


class QuotaUsageHistory(BaseModel):
    """Quota usage history entry"""
    hour: str
    requests: int
    total_tokens: int
    total_cost: float
    avg_tokens_per_request: float
    quota_exceeded_count: int


class QuotaUsageSummary(BaseModel):
    """Quota usage summary"""
    total_requests: int
    total_tokens: int
    total_cost: float
    avg_cost_per_request: float


class QuotaUsageHistoryResponse(BaseModel):
    """Quota usage history response"""
    service: str
    time_range: str
    usage_history: List[QuotaUsageHistory]
    summary: QuotaUsageSummary


class QuotaLimitResponse(BaseModel):
    """Quota limit configuration"""
    service_name: str
    quota_type: str
    limit_value: int
    window_seconds: int
    window_description: str
    is_active: bool
    updated_at: Optional[str] = None


class QuotaExceededWorkflow(BaseModel):
    """Workflow blocked by quota"""
    workflow_id: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    brand_name: Optional[str] = None
    state: str
    stage: Optional[str] = None
    quota_exceeded_count: int
    next_retry_at: Optional[str] = None
    quota_exceeded_at: Optional[str] = None
    wait_seconds: Optional[int] = None
    progress_percentage: float


class WorkflowResumeResponse(BaseModel):
    """Response for workflow resume operation"""
    success: bool
    resumed_count: int
    message: str


class QuotaResetTimeInfo(BaseModel):
    """Detailed reset time information"""
    quota_type: str
    reset_at: str
    seconds_until_reset: int
    human_readable: str
