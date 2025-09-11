"""
Brand API schemas
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


class BrandBase(BaseModel):
    """Base brand schema with common fields"""
    name: str = Field(..., min_length=1, max_length=255)
    normalized_name: str = Field(..., min_length=1, max_length=255)
    owner_company: Optional[str] = Field(None, max_length=255)
    country: Optional[str] = Field(None, max_length=2, description="ISO 2-letter country code")
    www: Optional[str] = Field(None, max_length=255)


class BrandCreate(BrandBase):
    """Schema for creating a brand"""
    pass


class BrandUpdate(BaseModel):
    """Schema for updating a brand - all fields optional"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    normalized_name: Optional[str] = Field(None, min_length=1, max_length=255)
    owner_company: Optional[str] = Field(None, max_length=255)
    country: Optional[str] = Field(None, max_length=2)
    www: Optional[str] = Field(None, max_length=255)


class BrandRead(BrandBase):
    """Schema for reading a brand"""
    brand_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BrandReadWithProducts(BrandRead):
    """Schema for reading a brand with its products"""
    products: List["ProductRead"] = []
    product_count: int = 0


# Avoid circular imports
from .product import ProductRead
BrandReadWithProducts.model_rebuild()
