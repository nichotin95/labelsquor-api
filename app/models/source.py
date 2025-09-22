"""
Source and artifact models
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .product import Product
    from .retailer import Retailer


class SourcePage(SQLModel, table=True):
    """Source page (e.g., retailer product page)"""

    __tablename__ = "source_page"

    source_page_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: Optional[UUID] = Field(foreign_key="product.product_id", default=None)
    retailer_id: Optional[UUID] = Field(foreign_key="retailer.retailer_id", default=None)

    # URL and content
    url: str = Field(unique=True, index=True)
    title: Optional[str] = None
    meta_description: Optional[str] = None

    # Crawl tracking
    crawl_session_id: Optional[UUID] = Field(foreign_key="crawl_session.session_id", default=None)
    status_code: Optional[int] = None
    html_object_key: Optional[str] = None

    # Content fingerprinting
    content_hash: Optional[str] = None  # Hash of extracted data
    html_hash: Optional[str] = None  # Hash of raw HTML

    # Extracted data
    extracted_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    # {
    #   "price": 150,
    #   "mrp": 200,
    #   "in_stock": true,
    #   "seller": "Cloudtail India",
    #   "ratings": {"average": 4.2, "count": 1523},
    #   "images": ["url1", "url2"],
    #   "breadcrumbs": ["Grocery", "Snacks", "Chips"]
    # }

    # Timing
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_crawled_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    next_crawl_at: Optional[datetime] = None

    # Status
    is_active: bool = Field(default=True)
    is_discontinued: bool = Field(default=False)

    # Relationships
    product: Optional["Product"] = Relationship(back_populates="source_pages")
    retailer: Optional["Retailer"] = Relationship(back_populates="source_pages")


class ProductImage(SQLModel, table=True):
    """Product images"""

    __tablename__ = "product_image"

    product_image_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.product_id")
    source_page_id: Optional[UUID] = Field(foreign_key="source_page.source_page_id", default=None)
    role: Optional[str] = None  # front, back, ingredients, nutrition
    object_key: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    hash_sha256: Optional[str] = None
    ocr_status: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    product: "Product" = Relationship(back_populates="images")
    source_page: Optional[SourcePage] = Relationship()


class Artifact(SQLModel, table=True):
    """Storage artifacts (OCR results, LLM outputs, etc.)"""

    __tablename__ = "artifact"

    artifact_id: UUID = Field(default_factory=uuid4, primary_key=True)
    kind: str  # ocr_result, llm_extraction, etc.
    object_key: str
    content_hash: str
    mime: Optional[str] = None
    bytes: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
