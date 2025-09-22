"""
Scoring models (Squor)
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .product import ProductVersion


class SquorScore(SQLModel, table=True):
    """Product scores"""

    __tablename__ = "squor_score"

    squor_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_version_id: UUID = Field(foreign_key="product_version.product_version_id")
    scheme: str  # LabelSquor_v1, etc.
    score: Decimal
    grade: Optional[str] = None  # A, B, C, D, F
    score_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    product_version: "ProductVersion" = Relationship(back_populates="squor_scores")
    components: list["SquorComponent"] = Relationship(back_populates="squor_score")


class SquorComponent(SQLModel, table=True):
    """Individual score components"""

    __tablename__ = "squor_component"

    squor_component_id: UUID = Field(default_factory=uuid4, primary_key=True)
    squor_id: UUID = Field(foreign_key="squor_score.squor_id")
    component_key: str  # health, safety, sustainability, verification
    weight: Optional[Decimal] = None
    value: Optional[Decimal] = None
    contribution: Optional[Decimal] = None
    explain_md: Optional[str] = None

    # Relationships
    squor_score: SquorScore = Relationship(back_populates="components")


class PolicyCatalog(SQLModel, table=True):
    """Scoring policy configuration"""

    __tablename__ = "policy_catalog"

    policy_id: UUID = Field(default_factory=uuid4, primary_key=True)
    scheme: str
    version: str
    component_key: str
    weight_default: Optional[Decimal] = None
    params_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
