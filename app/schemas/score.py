"""
Score API schemas for SQUOR scoring system
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SquorScoreBase(BaseModel):
    """Base SQUOR score schema"""

    scheme: str = Field(..., description="Scoring scheme identifier (e.g., SQUOR_V2)")
    score: Decimal = Field(..., ge=0, le=100, description="Overall score (0-100)")
    grade: str = Field(..., pattern="^[A-F][+-]?$", description="Letter grade (A+ to F)")
    score_json: Optional[Dict[str, Any]] = Field(None, description="Detailed scoring breakdown")


class SquorScoreCreate(SquorScoreBase):
    """Schema for creating a SQUOR score"""

    product_version_id: UUID


class SquorScoreUpdate(BaseModel):
    """Schema for updating a SQUOR score"""

    score: Optional[Decimal] = Field(None, ge=0, le=100)
    grade: Optional[str] = Field(None, pattern="^[A-F][+-]?$")
    score_json: Optional[Dict[str, Any]] = None


class SquorScoreRead(SquorScoreBase):
    """Schema for reading a SQUOR score"""

    squor_id: UUID
    product_version_id: UUID
    computed_at: datetime
    components: Optional[List["SquorComponentRead"]] = []

    model_config = ConfigDict(from_attributes=True)


class SquorComponentBase(BaseModel):
    """Base SQUOR component schema"""

    component_key: str = Field(..., description="Component identifier (safety, quality, etc.)")
    value: Decimal = Field(..., ge=0, le=100, description="Component score (0-100)")
    weight: Decimal = Field(..., ge=0, le=1, description="Component weight (0-1)")
    reasoning: Optional[str] = Field(None, description="One-line explanation for the score")
    factors: Optional[Dict[str, Any]] = Field(None, description="Detailed factors")
    evidence: Optional[Dict[str, Any]] = Field(None, description="Supporting evidence")
    explain_md: Optional[str] = Field(None, description="Markdown explanation")


class SquorComponentCreate(SquorComponentBase):
    """Schema for creating a SQUOR component"""

    squor_id: UUID


class SquorComponentUpdate(BaseModel):
    """Schema for updating a SQUOR component"""

    value: Optional[Decimal] = Field(None, ge=0, le=100)
    weight: Optional[Decimal] = Field(None, ge=0, le=1)
    reasoning: Optional[str] = None
    factors: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    explain_md: Optional[str] = None


class SquorComponentRead(SquorComponentBase):
    """Schema for reading a SQUOR component"""

    squor_component_id: UUID
    squor_id: UUID

    model_config = ConfigDict(from_attributes=True)


class SquorAnalysisRead(BaseModel):
    """Comprehensive SQUOR analysis schema"""

    product_version_id: UUID
    overall_score: Decimal
    overall_grade: str
    squor_rating: str = Field(..., description="Visual rating (🟢, 🟡, 🟠, 🔴)")
    squor_label: str = Field(..., description="Rating label (Excellent, Good, Fair, Poor)")

    # Component breakdown
    safety_score: Optional[Decimal] = None
    safety_reasoning: Optional[str] = None
    quality_score: Optional[Decimal] = None
    quality_reasoning: Optional[str] = None
    usability_score: Optional[Decimal] = None
    usability_reasoning: Optional[str] = None
    origin_score: Optional[Decimal] = None
    origin_reasoning: Optional[str] = None
    responsibility_score: Optional[Decimal] = None
    responsibility_reasoning: Optional[str] = None

    # Claims analysis
    good_claims: List[Dict[str, Any]] = []
    bad_claims: List[Dict[str, Any]] = []
    misleading_claims: List[Dict[str, Any]] = []
    red_flags: List[str] = []
    green_flags: List[str] = []

    # Summary
    key_warnings: List[str] = []
    recommendation: Optional[str] = None
    computed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Resolve forward references
SquorScoreRead.model_rebuild()
