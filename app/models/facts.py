"""
Fact models with SCD Type-2 versioning
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .product import ProductVersion
    from .source import Artifact


class BaseFact(SQLModel):
    """Base class for versioned facts"""

    confidence: Optional[Decimal] = None
    valid_from: datetime = Field(default_factory=datetime.utcnow)
    valid_to: Optional[datetime] = None
    is_current: bool = Field(default=True)


class IngredientsV(BaseFact, table=True):
    """Versioned ingredients data"""

    __tablename__ = "ingredients_v"

    ingredients_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_version_id: UUID = Field(foreign_key="product_version.product_version_id")
    raw_text: Optional[str] = None
    normalized_list_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    tree_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    product_version: "ProductVersion" = Relationship(back_populates="ingredients")


class NutritionV(BaseFact, table=True):
    """Versioned nutrition data"""

    __tablename__ = "nutrition_v"

    nutrition_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_version_id: UUID = Field(foreign_key="product_version.product_version_id")
    panel_raw_text: Optional[str] = None
    per_100g_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    per_serving_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    serving_size: Optional[str] = None

    # Relationships
    product_version: "ProductVersion" = Relationship(back_populates="nutrition")


class AllergensV(BaseFact, table=True):
    """Versioned allergen data"""

    __tablename__ = "allergens_v"

    allergens_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_version_id: UUID = Field(foreign_key="product_version.product_version_id")
    declared_list: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    may_contain_list: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    contains_list: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    product_version: "ProductVersion" = Relationship(back_populates="allergens")


class ClaimsV(BaseFact, table=True):
    """Versioned product claims"""

    __tablename__ = "claims_v"

    claims_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_version_id: UUID = Field(foreign_key="product_version.product_version_id")
    claims_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    source: Optional[str] = None

    # Relationships
    product_version: "ProductVersion" = Relationship(back_populates="claims")


class CertificationsV(BaseFact, table=True):
    """Versioned certifications"""

    __tablename__ = "certifications_v"

    cert_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_version_id: UUID = Field(foreign_key="product_version.product_version_id")
    scheme: Optional[str] = None  # FSSAI, USDA Organic, etc.
    id_code: Optional[str] = None
    issuer: Optional[str] = None
    valid_from_label: Optional[str] = None
    valid_to_label: Optional[str] = None
    evidence_artifact_id: Optional[UUID] = Field(foreign_key="artifact.artifact_id", default=None)

    # Relationships
    product_version: "ProductVersion" = Relationship(back_populates="certifications")
    evidence_artifact: Optional["Artifact"] = Relationship()
