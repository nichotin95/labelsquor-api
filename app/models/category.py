"""
Category taxonomy models
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from .product import Product


class CategoryBase(SQLModel):
    """Base category attributes"""
    slug: str
    name: str
    locale: str = Field(default="en")
    rank: int = Field(default=0)
    is_active: bool = Field(default=True)


class Category(CategoryBase, table=True):
    """Category database model"""
    __tablename__ = "category"
    
    category_id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_id: Optional[UUID] = Field(foreign_key="category.category_id", default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    parent: Optional["Category"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Category.category_id"}
    )
    children: List["Category"] = Relationship(back_populates="parent")
    synonyms: List["CategorySynonym"] = Relationship(back_populates="category")
    product_mappings: List["ProductCategoryMap"] = Relationship(back_populates="category")


class CategorySynonym(SQLModel, table=True):
    """Category synonyms for search and mapping"""
    __tablename__ = "category_synonym"
    
    category_synonym_id: UUID = Field(default_factory=uuid4, primary_key=True)
    category_id: UUID = Field(foreign_key="category.category_id")
    term: str
    locale: str = Field(default="en")
    source: Optional[str] = None
    confidence: Optional[Decimal] = None
    
    # Relationships
    category: Category = Relationship(back_populates="synonyms")


class ProductCategoryMap(SQLModel, table=True):
    """Many-to-many mapping between products and categories"""
    __tablename__ = "product_category_map"
    
    product_id: UUID = Field(foreign_key="product.product_id", primary_key=True)
    category_id: UUID = Field(foreign_key="category.category_id", primary_key=True)
    is_primary: bool = Field(default=False)
    confidence: Optional[Decimal] = None
    assigned_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    product: "Product" = Relationship(back_populates="category_mappings")
    category: Category = Relationship(back_populates="product_mappings")
