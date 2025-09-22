"""
Quota and token management for AI services
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from enum import Enum
import json

from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.logging import log
from app.core.exceptions import QuotaExceededException


class QuotaType(str, Enum):
    """Types of quotas to track"""
    TOKENS_PER_MINUTE = "tokens_per_minute"
    TOKENS_PER_DAY = "tokens_per_day"
    REQUESTS_PER_MINUTE = "requests_per_minute"
    REQUESTS_PER_DAY = "requests_per_day"


class QuotaLimit(BaseModel):
    """Quota limit configuration"""
    quota_type: QuotaType
    limit: int
    window_seconds: int  # Time window for the limit
    
    @property
    def window_timedelta(self) -> timedelta:
        return timedelta(seconds=self.window_seconds)


class QuotaUsage(BaseModel):
    """Current quota usage"""
    quota_type: QuotaType
    used: int = 0
    limit: int
    window_start: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)
    
    @property
    def percentage_used(self) -> float:
        return (self.used / self.limit * 100) if self.limit > 0 else 0
    
    def is_exceeded(self) -> bool:
        return self.used >= self.limit
    
    def reset_if_window_expired(self, window_seconds: int) -> bool:
        """Reset usage if the time window has expired"""
        now = datetime.utcnow()
        if now > self.window_start + timedelta(seconds=window_seconds):
            self.used = 0
            self.window_start = now
            return True
        return False


class TokenTracker(BaseModel):
    """Track token usage for cost monitoring"""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    image_tokens: int = 0
    requests: int = 0
    
    # Pricing (Gemini 2.5 Flash)
    input_token_cost: float = 0.00001875  # per 1K tokens
    output_token_cost: float = 0.0000375   # per 1K tokens
    image_token_cost: float = 0.0001315    # per image
    
    @property
    def total_cost(self) -> float:
        """Calculate total cost in USD"""
        input_cost = (self.input_tokens / 1000) * self.input_token_cost
        output_cost = (self.output_tokens / 1000) * self.output_token_cost
        image_cost = self.image_tokens * self.image_token_cost
        return input_cost + output_cost + image_cost
    
    def add_usage(self, input_tokens: int, output_tokens: int, images: int = 0):
        """Add token usage"""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.image_tokens += images
        self.total_tokens += input_tokens + output_tokens
        self.requests += 1


class QuotaManager:
    """Manages API quotas and token usage"""
    
    # Default Gemini Free Tier Limits
    DEFAULT_LIMITS = [
        QuotaLimit(quota_type=QuotaType.TOKENS_PER_MINUTE, limit=4_000_000, window_seconds=60),
        QuotaLimit(quota_type=QuotaType.TOKENS_PER_DAY, limit=1_000_000_000, window_seconds=86400),
        QuotaLimit(quota_type=QuotaType.REQUESTS_PER_MINUTE, limit=15, window_seconds=60),
        QuotaLimit(quota_type=QuotaType.REQUESTS_PER_DAY, limit=1500, window_seconds=86400),
    ]
    
    def __init__(self, service_name: str = "gemini", custom_limits: Optional[list[QuotaLimit]] = None):
        self.service_name = service_name
        self.limits = custom_limits or self.DEFAULT_LIMITS
        self.usage: Dict[QuotaType, QuotaUsage] = {}
        self.token_tracker = TokenTracker()
        self._lock = asyncio.Lock()
        
        # Initialize usage trackers
        for limit in self.limits:
            self.usage[limit.quota_type] = QuotaUsage(
                quota_type=limit.quota_type,
                limit=limit.limit
            )
    
    async def check_quota(self, estimated_tokens: int = 0) -> Tuple[bool, Optional[str], Dict[str, any]]:
        """
        Check if quota is available
        Returns: (can_proceed, error_message, quota_status)
        """
        async with self._lock:
            status = {}
            
            for limit in self.limits:
                usage = self.usage[limit.quota_type]
                
                # Reset if window expired
                usage.reset_if_window_expired(limit.window_seconds)
                
                # Check specific quotas
                if limit.quota_type == QuotaType.TOKENS_PER_MINUTE:
                    if usage.used + estimated_tokens >= limit.limit:
                        return False, f"Token per minute quota exceeded", self.get_status()
                elif limit.quota_type == QuotaType.TOKENS_PER_DAY:
                    if usage.used + estimated_tokens >= limit.limit:
                        return False, f"Daily token quota exceeded", self.get_status()
                elif limit.quota_type == QuotaType.REQUESTS_PER_MINUTE:
                    if usage.used + 1 >= limit.limit:
                        wait_time = 60 - (datetime.utcnow() - usage.window_start).total_seconds()
                        return False, f"Request rate limit exceeded. Wait {wait_time:.0f}s", self.get_status()
                elif limit.quota_type == QuotaType.REQUESTS_PER_DAY:
                    if usage.used + 1 >= limit.limit:
                        return False, f"Daily request quota exceeded", self.get_status()
                
                status[limit.quota_type.value] = {
                    "used": usage.used,
                    "limit": usage.limit,
                    "remaining": usage.remaining,
                    "percentage": usage.percentage_used
                }
            
            return True, None, status
    
    async def record_usage(
        self, 
        tokens_used: int, 
        input_tokens: int = 0,
        output_tokens: int = 0,
        images: int = 0
    ):
        """Record actual usage after API call"""
        async with self._lock:
            # Update token quotas
            for quota_type in [QuotaType.TOKENS_PER_MINUTE, QuotaType.TOKENS_PER_DAY]:
                usage = self.usage[quota_type]
                limit = next(l for l in self.limits if l.quota_type == quota_type)
                usage.reset_if_window_expired(limit.window_seconds)
                usage.used += tokens_used
            
            # Update request quotas
            for quota_type in [QuotaType.REQUESTS_PER_MINUTE, QuotaType.REQUESTS_PER_DAY]:
                usage = self.usage[quota_type]
                limit = next(l for l in self.limits if l.quota_type == quota_type)
                usage.reset_if_window_expired(limit.window_seconds)
                usage.used += 1
            
            # Track for cost calculation
            self.token_tracker.add_usage(input_tokens, output_tokens, images)
            
            # Log usage
            log.info(
                f"Quota usage recorded",
                service=self.service_name,
                tokens=tokens_used,
                total_cost=f"${self.token_tracker.total_cost:.4f}",
                daily_tokens_remaining=self.usage[QuotaType.TOKENS_PER_DAY].remaining
            )
    
    def get_status(self) -> Dict[str, any]:
        """Get current quota status"""
        return {
            "service": self.service_name,
            "quotas": {
                quota_type.value: {
                    "used": usage.used,
                    "limit": usage.limit,
                    "remaining": usage.remaining,
                    "percentage": round(usage.percentage_used, 2),
                    "window_start": usage.window_start.isoformat()
                }
                for quota_type, usage in self.usage.items()
            },
            "cost_tracking": {
                "total_tokens": self.token_tracker.total_tokens,
                "total_requests": self.token_tracker.requests,
                "total_cost_usd": round(self.token_tracker.total_cost, 4),
                "breakdown": {
                    "input_tokens": self.token_tracker.input_tokens,
                    "output_tokens": self.token_tracker.output_tokens,
                    "image_count": self.token_tracker.image_tokens
                }
            }
        }
    
    async def get_wait_time(self) -> Optional[int]:
        """Get seconds to wait before quota resets"""
        min_wait = None
        
        for limit in self.limits:
            usage = self.usage[limit.quota_type]
            if usage.is_exceeded():
                wait_seconds = limit.window_seconds - (datetime.utcnow() - usage.window_start).total_seconds()
                if min_wait is None or wait_seconds < min_wait:
                    min_wait = max(0, int(wait_seconds))
        
        return min_wait
    
    async def save_to_database(self, workflow_id: str):
        """Save quota usage to database for tracking"""
        async with AsyncSessionLocal() as session:
            await session.execute(
                """
                INSERT INTO quota_usage_log 
                (workflow_id, service_name, usage_data, created_at)
                VALUES (:workflow_id, :service_name, :usage_data, :created_at)
                """,
                {
                    "workflow_id": workflow_id,
                    "service_name": self.service_name,
                    "usage_data": json.dumps(self.get_status()),
                    "created_at": datetime.utcnow()
                }
            )
            await session.commit()


class QuotaAwareWorkflowMixin:
    """Mixin for workflows that need quota management"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.quota_manager = QuotaManager()
    
    async def check_quota_before_ai_call(self, estimated_tokens: int = 1000) -> bool:
        """Check quota before making AI call"""
        can_proceed, error_msg, status = await self.quota_manager.check_quota(estimated_tokens)
        
        if not can_proceed:
            # Log quota exceeded
            log.warning(
                f"Quota exceeded",
                error=error_msg,
                status=status
            )
            
            # Get wait time
            wait_time = await self.quota_manager.get_wait_time()
            
            # Raise quota exception with wait time
            raise QuotaExceededException(
                message=error_msg,
                wait_seconds=wait_time,
                quota_status=status
            )
        
        return True
    
    async def record_ai_usage(
        self,
        workflow_id: str,
        tokens_used: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        images: int = 0
    ):
        """Record AI usage after successful call"""
        await self.quota_manager.record_usage(
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            images=images
        )
        
        # Save to database for tracking
        await self.quota_manager.save_to_database(workflow_id)
    
    def get_quota_status(self) -> Dict[str, any]:
        """Get current quota status"""
        return self.quota_manager.get_status()


class GlobalQuotaTracker:
    """Singleton for tracking quota across all workers"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.managers = {}
        return cls._instance
    
    async def get_manager(self, service_name: str = "gemini") -> QuotaManager:
        """Get or create quota manager for service"""
        async with self._lock:
            if service_name not in self.managers:
                self.managers[service_name] = QuotaManager(service_name)
            return self.managers[service_name]
    
    async def get_all_status(self) -> Dict[str, any]:
        """Get status of all quota managers"""
        return {
            service: manager.get_status()
            for service, manager in self.managers.items()
        }
