"""
Extended category models for versioning and schema
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .category import Category


class CategoryVersion(SQLModel, table=True):
    """Category version tracking"""

    __tablename__ = "category_version"

    category_version_id: UUID = Field(default_factory=uuid4, primary_key=True)
    category_id: UUID = Field(foreign_key="category.category_id")
    version: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    category: "Category" = Relationship()


class CategoryAttributeSchema(SQLModel, table=True):
    """Schema for category-specific attributes"""

    __tablename__ = "category_attribute_schema"

    schema_id: UUID = Field(default_factory=uuid4, primary_key=True)
    category_id: UUID = Field(foreign_key="category.category_id")
    attribute_name: str
    data_type: str  # string, number, boolean, array, object
    is_required: bool = Field(default=False)
    validation_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    category: "Category" = Relationship()


class CategoryPolicyOverride(SQLModel, table=True):
    """Category-specific policy overrides"""

    __tablename__ = "category_policy_override"

    override_id: UUID = Field(default_factory=uuid4, primary_key=True)
    category_id: UUID = Field(foreign_key="category.category_id")
    policy_id: UUID = Field(foreign_key="policy_catalog.policy_id")
    weight_override: Optional[float] = None
    params_override_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    effective_from: datetime = Field(default_factory=datetime.utcnow)
    effective_to: Optional[datetime] = None

    # Relationships
    category: "Category" = Relationship()
