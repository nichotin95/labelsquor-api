"""
AI Analysis Service for storing comprehensive product analysis data
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log
from app.models.ai_analysis import (
    ProductAnalysis,
    ProductClaim, 
    ProductIngredient,
    ProductNutrition,
    ProductWarning
)


class AIAnalysisService:
    """Service for storing comprehensive AI analysis results"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save_comprehensive_analysis(
        self,
        product_version_id: UUID,
        ai_result: Dict[str, Any]
    ) -> ProductAnalysis:
        """
        Save comprehensive AI analysis results to database
        
        Args:
            product_version_id: ID of the product version
            ai_result: Complete AI analysis result from pipeline
            
        Returns:
            Created ProductAnalysis instance
        """
        raw_data = ai_result.get("raw_data", {})
        metadata = raw_data.get("_metadata", {})
        usage = ai_result.get("usage", {})
        
        # Create main analysis record
        analysis = ProductAnalysis(
            product_version_id=product_version_id,
            
            # AI Metadata
            model_used=metadata.get("model", "unknown"),
            analysis_mode=metadata.get("mode", "standard"),
            confidence=raw_data.get("confidence", 0.0),
            analyzed_at=datetime.fromisoformat(metadata.get("analyzed_at")) if metadata.get("analyzed_at") else datetime.utcnow(),
            
            # Token usage and cost
            input_tokens=metadata.get("input_tokens", usage.get("input_tokens", 0)),
            output_tokens=metadata.get("output_tokens", usage.get("output_tokens", 0)),
            image_tokens=metadata.get("image_tokens", usage.get("image_tokens", 0)),
            total_tokens=metadata.get("total_tokens", usage.get("total_tokens", 0)),
            analysis_cost=usage.get("cost", 0.0),
            
            # Product identification
            ai_product_name=raw_data.get("product", {}).get("name"),
            ai_brand_name=raw_data.get("product", {}).get("brand"),
            ai_category=raw_data.get("product", {}).get("category"),
            
            # Best image selection
            best_image_index=raw_data.get("best_image", {}).get("index"),
            best_image_url=raw_data.get("best_image", {}).get("selected_url"),
            best_image_reason=raw_data.get("best_image", {}).get("reason"),
            hosted_image_url=raw_data.get("best_image", {}).get("hosted_url"),
            
            # Overall verdict
            overall_rating=raw_data.get("verdict", {}).get("overall_0_5"),
            recommendation=raw_data.get("verdict", {}).get("recommendation"),
            
            # Raw response for debugging
            raw_response=raw_data
        )
        
        self.session.add(analysis)
        await self.session.commit()
        await self.session.refresh(analysis)
        
        log.info(f"Created comprehensive analysis {analysis.analysis_id} for product version {product_version_id}")
        
        # Save related data
        await self._save_ingredients(analysis.analysis_id, raw_data.get("ingredients", []))
        await self._save_nutrition(analysis.analysis_id, raw_data.get("nutrition", {}))
        await self._save_claims(analysis.analysis_id, raw_data.get("claims", []))
        await self._save_warnings(analysis.analysis_id, raw_data.get("warnings", []))
        
        return analysis
    
    async def _save_ingredients(self, analysis_id: UUID, ingredients: List[str]):
        """Save ingredients list"""
        if not ingredients:
            return
            
        for index, ingredient_text in enumerate(ingredients):
            # Parse percentage if present (e.g., "Peanuts 27%")
            percentage = None
            name = ingredient_text.strip()
            
            if '%' in name:
                parts = name.split()
                for i, part in enumerate(parts):
                    if '%' in part:
                        try:
                            percentage = float(part.replace('%', ''))
                            name = ' '.join(parts[:i] + parts[i+1:]).strip()
                            break
                        except ValueError:
                            pass
            
            ingredient = ProductIngredient(
                analysis_id=analysis_id,
                name=name,
                order_index=index,
                percentage=percentage
            )
            self.session.add(ingredient)
        
        await self.session.commit()
        log.info(f"Saved {len(ingredients)} ingredients for analysis {analysis_id}")
    
    async def _save_nutrition(self, analysis_id: UUID, nutrition: Dict[str, Any]):
        """Save nutrition facts"""
        if not nutrition:
            return
        
        # Extract additional nutrition data not in standard fields
        standard_fields = {
            'energy_kcal', 'protein_g', 'carbs_g', 'sugar_g', 'fat_g', 
            'saturated_fat_g', 'sodium_mg', 'fiber_g', 'calcium_mg', 'iron_mg'
        }
        additional_nutrition = {k: v for k, v in nutrition.items() if k not in standard_fields}
        
        nutrition_record = ProductNutrition(
            analysis_id=analysis_id,
            energy_kcal=nutrition.get("energy_kcal"),
            protein_g=nutrition.get("protein_g"),
            carbs_g=nutrition.get("carbs_g"),
            sugar_g=nutrition.get("sugar_g"),
            fat_g=nutrition.get("fat_g"),
            saturated_fat_g=nutrition.get("saturated_fat_g"),
            sodium_mg=nutrition.get("sodium_mg"),
            fiber_g=nutrition.get("fiber_g"),
            calcium_mg=nutrition.get("calcium_mg"),
            iron_mg=nutrition.get("iron_mg"),
            serving_size="per 100g",  # Default assumption
            additional_nutrition=additional_nutrition if additional_nutrition else None
        )
        
        self.session.add(nutrition_record)
        await self.session.commit()
        log.info(f"Saved nutrition facts for analysis {analysis_id}")
    
    async def _save_claims(self, analysis_id: UUID, claims: List[str]):
        """Save marketing claims"""
        if not claims:
            return
            
        for claim_text in claims:
            # Categorize claim type based on keywords
            claim_type = self._categorize_claim(claim_text)
            
            claim = ProductClaim(
                analysis_id=analysis_id,
                claim_text=claim_text,
                claim_type=claim_type
            )
            self.session.add(claim)
        
        await self.session.commit()
        log.info(f"Saved {len(claims)} claims for analysis {analysis_id}")
    
    async def _save_warnings(self, analysis_id: UUID, warnings: List[str]):
        """Save warnings and allergen information"""
        if not warnings:
            return
            
        for warning_text in warnings:
            # Categorize warning type
            warning_type = self._categorize_warning(warning_text)
            
            warning = ProductWarning(
                analysis_id=analysis_id,
                warning_text=warning_text,
                warning_type=warning_type,
                severity="medium"  # Default severity
            )
            self.session.add(warning)
        
        await self.session.commit()
        log.info(f"Saved {len(warnings)} warnings for analysis {analysis_id}")
    
    def _categorize_claim(self, claim_text: str) -> str:
        """Categorize a marketing claim"""
        claim_lower = claim_text.lower()
        
        if any(word in claim_lower for word in ['organic', 'natural', 'pure', 'wholesome']):
            return 'quality'
        elif any(word in claim_lower for word in ['healthy', 'nutritious', 'vitamin', 'protein', 'fiber']):
            return 'health'
        elif any(word in claim_lower for word in ['local', 'farm', 'origin', 'made in']):
            return 'origin'
        elif any(word in claim_lower for word in ['no', 'free', 'zero', 'without']):
            return 'negative_claim'
        elif any(word in claim_lower for word in ['eco', 'sustainable', 'green', 'recyclable']):
            return 'environmental'
        else:
            return 'general'
    
    def _categorize_warning(self, warning_text: str) -> str:
        """Categorize a warning"""
        warning_lower = warning_text.lower()
        
        if any(word in warning_lower for word in ['contains', 'allergen', 'nuts', 'dairy', 'gluten', 'soy']):
            return 'allergen'
        elif any(word in warning_lower for word in ['store', 'storage', 'keep', 'refrigerate']):
            return 'storage'
        elif any(word in warning_lower for word in ['consume', 'expiry', 'best before']):
            return 'consumption'
        else:
            return 'general'
    
    async def get_comprehensive_analysis(self, product_version_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive analysis data for a product version
        
        Returns:
            Complete analysis data including all related information
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        # Load analysis with all relationships
        stmt = (
            select(ProductAnalysis)
            .options(
                selectinload(ProductAnalysis.ingredients),
                selectinload(ProductAnalysis.nutrition_facts),
                selectinload(ProductAnalysis.claims),
                selectinload(ProductAnalysis.warnings)
            )
            .where(ProductAnalysis.product_version_id == product_version_id)
            .order_by(ProductAnalysis.created_at.desc())
        )
        
        result = await self.session.execute(stmt)
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            return None
        
        return {
            "analysis_id": analysis.analysis_id,
            "confidence": analysis.confidence,
            "analyzed_at": analysis.analyzed_at.isoformat(),
            "model_used": analysis.model_used,
            "analysis_cost": analysis.analysis_cost,
            
            # Product identification
            "ai_product_name": analysis.ai_product_name,
            "ai_brand_name": analysis.ai_brand_name,
            "ai_category": analysis.ai_category,
            
            # Best image
            "best_image": {
                "index": analysis.best_image_index,
                "url": analysis.best_image_url,
                "reason": analysis.best_image_reason,
                "hosted_url": analysis.hosted_image_url
            } if analysis.best_image_url else None,
            
            # Overall verdict
            "verdict": {
                "overall_rating": analysis.overall_rating,
                "recommendation": analysis.recommendation
            },
            
            # Ingredients
            "ingredients": [
                {
                    "name": ing.name,
                    "order": ing.order_index,
                    "percentage": ing.percentage
                }
                for ing in sorted(analysis.ingredients, key=lambda x: x.order_index)
            ],
            
            # Nutrition
            "nutrition": {
                "energy_kcal": analysis.nutrition_facts[0].energy_kcal if analysis.nutrition_facts else None,
                "protein_g": analysis.nutrition_facts[0].protein_g if analysis.nutrition_facts else None,
                "carbs_g": analysis.nutrition_facts[0].carbs_g if analysis.nutrition_facts else None,
                "sugar_g": analysis.nutrition_facts[0].sugar_g if analysis.nutrition_facts else None,
                "fat_g": analysis.nutrition_facts[0].fat_g if analysis.nutrition_facts else None,
                "saturated_fat_g": analysis.nutrition_facts[0].saturated_fat_g if analysis.nutrition_facts else None,
                "sodium_mg": analysis.nutrition_facts[0].sodium_mg if analysis.nutrition_facts else None,
                "serving_size": analysis.nutrition_facts[0].serving_size if analysis.nutrition_facts else None,
                "additional": analysis.nutrition_facts[0].additional_nutrition if analysis.nutrition_facts else None
            } if analysis.nutrition_facts else None,
            
            # Claims
            "claims": [
                {
                    "text": claim.claim_text,
                    "type": claim.claim_type,
                    "verified": claim.verified
                }
                for claim in analysis.claims
            ],
            
            # Warnings
            "warnings": [
                {
                    "text": warning.warning_text,
                    "type": warning.warning_type,
                    "severity": warning.severity
                }
                for warning in analysis.warnings
            ]
        }
