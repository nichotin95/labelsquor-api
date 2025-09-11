"""
Operations models (jobs, refresh requests, issues)
"""
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship, Column, JSON
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from .product import Product


class Job(SQLModel, table=True):
    """Job definitions"""
    __tablename__ = "job"
    
    job_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    is_active: bool = Field(default=True)
    
    # Relationships
    runs: list["JobRun"] = Relationship(back_populates="job")


class JobRun(SQLModel, table=True):
    """Job execution records"""
    __tablename__ = "job_run"
    
    job_run_id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID = Field(foreign_key="job.job_id")
    product_id: Optional[UUID] = Field(foreign_key="product.product_id", default=None)
    source_page_id: Optional[UUID] = Field(foreign_key="source_page.source_page_id", default=None)
    status: Optional[str] = None  # pending, running, completed, failed
    attempt: int = Field(default=1)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    logs_object_key: Optional[str] = None
    metrics_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Relationships
    job: Job = Relationship(back_populates="runs")


class RefreshRequest(SQLModel, table=True):
    """Product refresh requests"""
    __tablename__ = "refresh_request"
    
    refresh_request_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.product_id")
    reason: Optional[str] = None
    requested_by: Optional[str] = None
    priority: Optional[str] = None  # low, medium, high
    status: Optional[str] = None  # pending, processing, completed, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    job_run_id: Optional[UUID] = Field(foreign_key="job_run.job_run_id", default=None)
    
    # Relationships
    product: "Product" = Relationship()
    job_run: Optional[JobRun] = Relationship()


class Issue(SQLModel, table=True):
    """Data quality issues"""
    __tablename__ = "issue"
    
    issue_id: UUID = Field(default_factory=uuid4, primary_key=True)
    entity_type: str  # product, brand, etc.
    entity_id: UUID
    severity: Optional[str] = None  # info, warning, error, critical
    code: Optional[str] = None
    details_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
