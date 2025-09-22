"""
Discovery and task models
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column, JSON


class DiscoveryTask(SQLModel, table=True):
    """Task for discovery operations"""
    __tablename__ = "discovery_task"

    task_id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_type: str = Field(..., description="Type of discovery task")
    retailer_slug: str = Field(..., description="Retailer identifier")
    search_query: Optional[str] = Field(None, description="Search query")
    category: Optional[str] = Field(None, description="Category to search")
    priority: int = Field(default=5, description="Task priority (1-10)")
    status: str = Field(default="pending", description="Task status")
    
    # Task configuration
    max_products: int = Field(default=50, description="Maximum products to fetch")
    config: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON), description="Task configuration")
    
    # Results
    results: Optional[Dict[str, Any]] = Field(None, sa_column=Column(JSON), description="Task results")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    created_by: Optional[str] = Field(None, description="User who created the task")
    session_id: Optional[UUID] = Field(None, description="Associated session ID")


class TaskResult(SQLModel):
    """Result of a discovery task (not a table, just a data structure)"""
    
    task_id: UUID
    status: str
    products_found: int = 0
    products_processed: int = 0
    errors: list[str] = []
    task_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    duration_seconds: Optional[float] = None
