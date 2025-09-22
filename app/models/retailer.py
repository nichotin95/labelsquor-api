"""
Retailer and crawling models
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .source import SourcePage


class Retailer(SQLModel, table=True):
    """Retailer configuration for crawling"""

    __tablename__ = "retailer"

    retailer_id: UUID = Field(default_factory=uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)  # amazon_in, bigbasket, blinkit, zepto
    name: str
    domain: str
    country: str = Field(default="IN")
    is_active: bool = Field(default=True)

    # Crawling configuration
    crawl_config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    rate_limit_rps: int = Field(default=1)  # Requests per second
    priority: int = Field(default=5)  # 1-10, higher = more priority

    # Scheduling
    crawl_frequency_hours: int = Field(default=24)
    last_crawl_at: Optional[datetime] = None
    next_crawl_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    crawl_sessions: List["CrawlSession"] = Relationship(back_populates="retailer")
    source_pages: List["SourcePage"] = Relationship(back_populates="retailer")


class CrawlSession(SQLModel, table=True):
    """Track crawling sessions per retailer"""

    __tablename__ = "crawl_session"

    session_id: UUID = Field(default_factory=uuid4, primary_key=True)
    retailer_id: UUID = Field(foreign_key="retailer.retailer_id")

    # Session details
    status: str = Field(default="pending")  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # Metrics
    pages_discovered: int = Field(default=0)
    pages_processed: int = Field(default=0)
    products_found: int = Field(default=0)
    products_new: int = Field(default=0)
    products_updated: int = Field(default=0)
    errors_count: int = Field(default=0)

    # Error tracking
    error_details: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Session metadata
    session_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    retailer: Retailer = Relationship(back_populates="crawl_sessions")


class ProcessingQueue(SQLModel, table=True):
    """Queue for products awaiting processing"""

    __tablename__ = "processing_queue"

    queue_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: Optional[UUID] = Field(default=None, foreign_key="product.product_id")
    source_page_id: UUID = Field(foreign_key="source_page.source_page_id")

    # Queue management
    status: str = Field(default="pending")  # pending, processing, completed, failed, skipped
    priority: int = Field(default=5)  # 1-10, higher = more priority
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)

    # Processing stages
    stage: str = Field(default="discovery")  # discovery, image_fetch, ocr, enrichment, scoring, indexing
    stage_details: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Timing
    queued_at: datetime = Field(default_factory=datetime.utcnow)
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None

    # Error tracking
    last_error: Optional[str] = None
    error_details: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    product: Optional["Product"] = Relationship()
    source_page: Optional["SourcePage"] = Relationship()


class CrawlRule(SQLModel, table=True):
    """Rules for crawling specific retailers"""

    __tablename__ = "crawl_rule"

    rule_id: UUID = Field(default_factory=uuid4, primary_key=True)
    retailer_id: UUID = Field(foreign_key="retailer.retailer_id")

    # Rule configuration
    rule_type: str  # category_page, search_page, product_page
    url_pattern: str  # Regex pattern for URLs
    selector_config: dict = Field(sa_column=Column(JSON))  # CSS/XPath selectors

    # Pagination
    pagination_type: Optional[str] = None  # page_number, infinite_scroll, load_more
    max_pages: Optional[int] = Field(default=100)

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
