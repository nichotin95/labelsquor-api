"""
Brand model
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .product import Product


class BrandBase(SQLModel):
    """Base brand attributes for request/response schemas"""

    name: str
    normalized_name: str
    owner_company: Optional[str] = None
    country: Optional[str] = None
    www: Optional[str] = None


class Brand(BrandBase, table=True):
    """Brand database model"""

    __tablename__ = "brand"

    brand_id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    products: List["Product"] = Relationship(back_populates="brand")
