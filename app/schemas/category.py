"""
Category API schemas
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    """Base category schema"""

    slug: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    locale: str = Field(default="en", max_length=5)
    rank: int = Field(default=0)
    is_active: bool = Field(default=True)


class CategoryCreate(CategoryBase):
    """Schema for creating a category"""

    parent_id: Optional[UUID] = None


class CategoryUpdate(BaseModel):
    """Schema for updating a category"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    rank: Optional[int] = None
    is_active: Optional[bool] = None
    parent_id: Optional[UUID] = None


class CategoryRead(CategoryBase):
    """Schema for reading a category"""

    category_id: UUID
    parent_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    # Computed fields
    level: int = 0
    product_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CategoryTree(CategoryRead):
    """Schema for category tree structure"""

    children: List["CategoryTree"] = []

    model_config = ConfigDict(from_attributes=True)


class ProductCategoryMapCreate(BaseModel):
    """Schema for mapping product to category"""

    category_id: UUID
    is_primary: bool = Field(default=False)
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)


class ProductCategoryMapRead(BaseModel):
    """Schema for reading product category mapping"""

    product_id: UUID
    category_id: UUID
    category_name: str
    category_slug: str
    is_primary: bool
    confidence: Optional[Decimal]
    assigned_by: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
