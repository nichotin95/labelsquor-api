"""
AI Analysis models for storing rich product analysis data
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, Relationship, SQLModel

from app.models.product import ProductVersion


class ProductAnalysis(SQLModel, table=True):
    """Comprehensive AI analysis results for a product version"""
    
    __tablename__ = "product_analysis"
    
    analysis_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_version_id: UUID = Field(foreign_key="product_version.product_version_id")
    
    # AI Analysis Metadata
    model_used: str = Field(description="AI model used (e.g., gemini-2.5-flash)")
    analysis_mode: str = Field(description="Analysis mode (e.g., standard)")
    confidence: float = Field(description="AI confidence score (0.0-1.0)")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Token usage and cost tracking
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    image_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    analysis_cost: float = Field(default=0.0)
    
    # Product identification (AI extracted)
    ai_product_name: Optional[str] = Field(default=None)
    ai_brand_name: Optional[str] = Field(default=None)
    ai_category: Optional[str] = Field(default=None)
    
    # Best image selection
    best_image_index: Optional[int] = Field(default=None)
    best_image_url: Optional[str] = Field(default=None)
    best_image_reason: Optional[str] = Field(default=None)
    hosted_image_url: Optional[str] = Field(default=None)
    
    # Overall verdict
    overall_rating: Optional[float] = Field(default=None, description="Overall rating 0-5")
    recommendation: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Raw AI response for debugging
    raw_response: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    product_version: ProductVersion = Relationship()
    ingredients: list["ProductIngredient"] = Relationship(back_populates="analysis")
    nutrition_facts: list["ProductNutrition"] = Relationship(back_populates="analysis") 
    claims: list["ProductClaim"] = Relationship(back_populates="analysis")
    warnings: list["ProductWarning"] = Relationship(back_populates="analysis")


class ProductIngredient(SQLModel, table=True):
    """Individual ingredient extracted by AI"""
    
    __tablename__ = "product_ingredient"
    
    ingredient_id: UUID = Field(default_factory=uuid4, primary_key=True)
    analysis_id: UUID = Field(foreign_key="product_analysis.analysis_id")
    
    name: str = Field(description="Ingredient name as extracted by AI")
    order_index: int = Field(description="Order in ingredients list (0-based)")
    percentage: Optional[float] = Field(default=None, description="Percentage if specified")
    notes: Optional[str] = Field(default=None, description="Additional notes about ingredient")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    analysis: ProductAnalysis = Relationship(back_populates="ingredients")


class ProductNutrition(SQLModel, table=True):
    """Nutrition facts extracted by AI"""
    
    __tablename__ = "product_nutrition"
    
    nutrition_id: UUID = Field(default_factory=uuid4, primary_key=True)
    analysis_id: UUID = Field(foreign_key="product_analysis.analysis_id")
    
    # Standard nutrition fields
    energy_kcal: Optional[float] = Field(default=None)
    protein_g: Optional[float] = Field(default=None)
    carbs_g: Optional[float] = Field(default=None)
    sugar_g: Optional[float] = Field(default=None)
    fat_g: Optional[float] = Field(default=None)
    saturated_fat_g: Optional[float] = Field(default=None)
    sodium_mg: Optional[float] = Field(default=None)
    fiber_g: Optional[float] = Field(default=None)
    calcium_mg: Optional[float] = Field(default=None)
    iron_mg: Optional[float] = Field(default=None)
    
    # Serving size context
    serving_size: Optional[str] = Field(default=None, description="Per 100g, per serving, etc.")
    
    # Additional nutrition data as JSON for flexibility
    additional_nutrition: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    analysis: ProductAnalysis = Relationship(back_populates="nutrition_facts")


class ProductClaim(SQLModel, table=True):
    """Marketing claims extracted by AI"""
    
    __tablename__ = "product_claim"
    
    claim_id: UUID = Field(default_factory=uuid4, primary_key=True)
    analysis_id: UUID = Field(foreign_key="product_analysis.analysis_id")
    
    claim_text: str = Field(description="The marketing claim as it appears")
    claim_type: Optional[str] = Field(default=None, description="health, quality, origin, etc.")
    verified: Optional[bool] = Field(default=None, description="Whether AI could verify the claim")
    verification_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    analysis: ProductAnalysis = Relationship(back_populates="claims")


class ProductWarning(SQLModel, table=True):
    """Warnings and allergen information extracted by AI"""
    
    __tablename__ = "product_warning"
    
    warning_id: UUID = Field(default_factory=uuid4, primary_key=True)
    analysis_id: UUID = Field(foreign_key="product_analysis.analysis_id")
    
    warning_text: str = Field(description="The warning text")
    warning_type: str = Field(description="allergen, storage, health, etc.")
    severity: Optional[str] = Field(default=None, description="low, medium, high")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    analysis: ProductAnalysis = Relationship(back_populates="warnings")


# Add relationship back to ProductVersion
ProductVersion.ai_analyses = Relationship(back_populates="product_version")
