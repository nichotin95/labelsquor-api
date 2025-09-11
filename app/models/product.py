"""
Product models
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from sqlmodel import Field, SQLModel, Relationship, Column, String
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from .brand import Brand
    from .category import ProductCategoryMap
    from .source import SourcePage, ProductImage
    from .facts import IngredientsV, NutritionV, AllergensV, ClaimsV, CertificationsV
    from .score import SquorScore


class ProductBase(SQLModel):
    """Base product attributes"""
    name: str
    normalized_name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    pack_size: Optional[Decimal] = None
    unit: Optional[str] = None
    gtin_primary: Optional[str] = None
    status: str = Field(default="active")


class Product(ProductBase, table=True):
    """Product database model"""
    __tablename__ = "product"
    
    product_id: UUID = Field(default_factory=uuid4, primary_key=True)
    brand_id: UUID = Field(foreign_key="brand.brand_id")
    canonical_key: str = Field(sa_column=Column(String, unique=True, index=True))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    brand: "Brand" = Relationship(back_populates="products")
    identifiers: List["ProductIdentifier"] = Relationship(back_populates="product")
    versions: List["ProductVersion"] = Relationship(back_populates="product")
    source_pages: List["SourcePage"] = Relationship(back_populates="product")
    images: List["ProductImage"] = Relationship(back_populates="product")
    category_mappings: List["ProductCategoryMap"] = Relationship(back_populates="product")


class ProductIdentifier(SQLModel, table=True):
    """Product identifiers (GTIN, ASIN, SKU, etc.)"""
    __tablename__ = "product_identifier"
    
    product_identifier_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.product_id")
    type: str  # GTIN, ASIN, SKU, MPN
    value: str
    confidence: Optional[Decimal] = None
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    product: Product = Relationship(back_populates="identifiers")


class ProductVersion(SQLModel, table=True):
    """Immutable product version snapshot"""
    __tablename__ = "product_version"
    
    product_version_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.product_id")
    derived_from_job_run_id: Optional[UUID] = Field(foreign_key="job_run.job_run_id")
    version_seq: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    product: Product = Relationship(back_populates="versions")
    ingredients: List["IngredientsV"] = Relationship(back_populates="product_version")
    nutrition: List["NutritionV"] = Relationship(back_populates="product_version")
    allergens: List["AllergensV"] = Relationship(back_populates="product_version")
    claims: List["ClaimsV"] = Relationship(back_populates="product_version")
    certifications: List["CertificationsV"] = Relationship(back_populates="product_version")
    squor_scores: List["SquorScore"] = Relationship(back_populates="product_version")
