"""
Source and artifact models
"""
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from .product import Product


class SourcePage(SQLModel, table=True):
    """Source page (e.g., retailer product page)"""
    __tablename__ = "source_page"
    
    source_page_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: Optional[UUID] = Field(foreign_key="product.product_id", default=None)
    retailer: str
    url: str
    crawl_batch_id: Optional[str] = None
    html_object_key: Optional[str] = None
    status_code: Optional[int] = None
    fingerprint_sha256: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    
    # Relationships
    product: Optional["Product"] = Relationship(back_populates="source_pages")


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
