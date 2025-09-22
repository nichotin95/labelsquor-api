"""
Facts API schemas (ingredients, nutrition, allergens, claims, certifications)
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FactBase(BaseModel):
    """Base schema for facts with confidence"""

    confidence: Optional[Decimal] = Field(None, ge=0, le=1, description="Confidence score 0-1")


# Ingredients Schemas
class IngredientsCreate(FactBase):
    """Schema for creating ingredients"""

    raw_text: Optional[str] = None
    normalized_list: Optional[List[str]] = None
    tree_structure: Optional[Dict[str, Any]] = None


class IngredientsRead(IngredientsCreate):
    """Schema for reading ingredients"""

    ingredients_id: UUID
    product_version_id: UUID
    valid_from: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


# Nutrition Schemas
class NutritionFactValue(BaseModel):
    """Individual nutrition fact value"""

    value: Decimal
    unit: str
    per_100g: Optional[Decimal] = None
    daily_value_percent: Optional[Decimal] = None


class NutritionCreate(FactBase):
    """Schema for creating nutrition data"""

    panel_raw_text: Optional[str] = None
    serving_size: Optional[str] = None
    servings_per_container: Optional[Decimal] = None

    # Key nutrition facts
    calories: Optional[NutritionFactValue] = None
    total_fat: Optional[NutritionFactValue] = None
    saturated_fat: Optional[NutritionFactValue] = None
    trans_fat: Optional[NutritionFactValue] = None
    cholesterol: Optional[NutritionFactValue] = None
    sodium: Optional[NutritionFactValue] = None
    total_carbohydrate: Optional[NutritionFactValue] = None
    dietary_fiber: Optional[NutritionFactValue] = None
    total_sugars: Optional[NutritionFactValue] = None
    added_sugars: Optional[NutritionFactValue] = None
    protein: Optional[NutritionFactValue] = None

    # Additional nutrients
    other_nutrients: Optional[Dict[str, NutritionFactValue]] = None


class NutritionRead(BaseModel):
    """Schema for reading nutrition data"""

    nutrition_id: UUID
    product_version_id: UUID
    panel_raw_text: Optional[str]
    per_100g_json: Optional[Dict[str, Any]]
    per_serving_json: Optional[Dict[str, Any]]
    serving_size: Optional[str]
    confidence: Optional[Decimal]
    valid_from: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


# Allergens Schemas
class AllergensCreate(FactBase):
    """Schema for creating allergen data"""

    declared_list: Optional[List[str]] = Field(None, description="Explicitly declared allergens")
    may_contain_list: Optional[List[str]] = Field(None, description="May contain allergens")
    contains_list: Optional[List[str]] = Field(None, description="Contains allergens from ingredients")


class AllergensRead(AllergensCreate):
    """Schema for reading allergen data"""

    allergens_id: UUID
    product_version_id: UUID
    valid_from: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


# Claims Schemas
class ClaimItem(BaseModel):
    """Individual claim"""

    claim_type: str  # organic, non-gmo, gluten-free, etc.
    claim_text: str
    verified: Optional[bool] = None
    evidence: Optional[str] = None


class ClaimsCreate(FactBase):
    """Schema for creating claims"""

    claims: List[ClaimItem] = []
    source: Optional[str] = None


class ClaimsRead(BaseModel):
    """Schema for reading claims"""

    claims_id: UUID
    product_version_id: UUID
    claims_json: Optional[Dict[str, Any]]
    source: Optional[str]
    confidence: Optional[Decimal]
    valid_from: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


# Certifications Schemas
class CertificationCreate(FactBase):
    """Schema for creating certification"""

    scheme: str = Field(..., description="FSSAI, USDA Organic, India Organic, etc.")
    id_code: Optional[str] = Field(None, description="License/certification number")
    issuer: Optional[str] = None
    valid_from_label: Optional[str] = None
    valid_to_label: Optional[str] = None


class CertificationRead(CertificationCreate):
    """Schema for reading certification"""

    cert_id: UUID
    product_version_id: UUID
    evidence_artifact_id: Optional[UUID]
    valid_from: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)
