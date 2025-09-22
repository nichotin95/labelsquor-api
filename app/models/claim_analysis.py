"""
Claims analysis model for storing categorized claims
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .product import ProductVersion


class ClaimAnalysis(SQLModel, table=True):
    """Enhanced claims analysis with categorization"""

    __tablename__ = "claim_analysis"

    claim_analysis_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_version_id: UUID = Field(
        foreign_key="product_version.product_version_id", unique=True  # One analysis per product version
    )

    # Claims categorization
    good_claims: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Array of {claim: text, evidence: text, confidence: 0-1}",
    )
    bad_claims: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Array of {claim: text, issue: text, severity: low/medium/high}",
    )
    misleading_claims: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Array of {claim: text, truth: text, explanation: text}",
    )

    # Overall assessment
    claims_summary: Optional[str] = None
    red_flags: List[str] = Field(default_factory=list, sa_column=Column(JSON), description="Major concerns")
    green_flags: List[str] = Field(default_factory=list, sa_column=Column(JSON), description="Positive highlights")

    # Metadata
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    analyzer_version: str = Field(default="v1")
    confidence_score: Optional[Decimal] = Field(default=None, ge=0.0, le=1.0, description="0.00-1.00")

    # Relationships
    product_version: "ProductVersion" = Relationship()
