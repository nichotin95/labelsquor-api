"""
Product API schemas
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    """Base product schema"""

    name: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = Field(None, max_length=255)
    subcategory: Optional[str] = Field(None, max_length=255)
    pack_size: Optional[Decimal] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=50)
    gtin_primary: Optional[str] = Field(None, pattern="^[0-9]{8,14}$")


class ProductCreate(ProductBase):
    """Schema for creating a product"""

    brand_id: UUID
    identifiers: Optional[List["ProductIdentifierCreate"]] = []


class ProductUpdate(BaseModel):
    """Schema for updating a product"""

    name: Optional[str] = Field(None, min_length=1, max_length=500)
    category: Optional[str] = Field(None, max_length=255)
    subcategory: Optional[str] = Field(None, max_length=255)
    pack_size: Optional[Decimal] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=50)
    gtin_primary: Optional[str] = Field(None, pattern="^[0-9]{8,14}$")
    status: Optional[str] = Field(None, pattern="^(active|inactive|discontinued)$")


class ProductRead(ProductBase):
    """Basic product read schema"""

    product_id: UUID
    brand_id: UUID
    brand_name: str
    status: str
    canonical_key: str
    created_at: datetime
    updated_at: datetime

    # Computed fields
    latest_squor_score: Optional[int] = None
    latest_squor_grade: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProductReadDetailed(ProductRead):
    """Detailed product read schema with related data"""

    identifiers: List["ProductIdentifierRead"] = []
    latest_version: Optional["ProductVersionRead"] = None
    categories: List["CategoryRead"] = []
    images: List["ProductImageRead"] = []


class ProductIdentifierBase(BaseModel):
    """Base identifier schema"""

    type: str = Field(..., pattern="^(GTIN|ASIN|SKU|MPN|EAN|UPC)$")
    value: str = Field(..., min_length=1, max_length=255)
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    source: Optional[str] = Field(None, max_length=255)


class ProductIdentifierCreate(ProductIdentifierBase):
    """Schema for creating an identifier"""

    pass


class ProductIdentifierRead(ProductIdentifierBase):
    """Schema for reading an identifier"""

    product_identifier_id: UUID
    product_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductVersionRead(BaseModel):
    """Schema for reading a product version"""

    product_version_id: UUID
    product_id: UUID
    version_seq: int
    created_at: datetime

    # Summary of facts in this version
    has_ingredients: bool = False
    has_nutrition: bool = False
    has_allergens: bool = False
    has_claims: bool = False
    has_certifications: bool = False

    model_config = ConfigDict(from_attributes=True)


class ProductImageRead(BaseModel):
    """Schema for reading product images"""

    product_image_id: UUID
    role: Optional[str]
    url: str  # Pre-signed URL or public URL
    width: Optional[int]
    height: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Avoid circular imports
from .category import CategoryRead

ProductReadDetailed.model_rebuild()
