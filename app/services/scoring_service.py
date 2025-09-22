"""
Scoring service for Squor calculation
"""

from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from app.core.logging import log
from app.models import ProductVersion, SquorComponent, SquorScore
from app.repositories import FactsRepository, ProductRepository


class ScoringService:
    """Service for calculating Squor scores based on Indian regulations and standards"""

    def __init__(self, product_repo: ProductRepository, facts_repo: FactsRepository):
        self.product_repo = product_repo
        self.facts_repo = facts_repo

    async def calculate_squor(self, product_version_id: UUID) -> Dict[str, Any]:
        """Calculate all Squor scores for a product version"""
        # Get product version and all related facts
        version = await self.product_repo.get_version(product_version_id)
        if not version:
            raise ValueError(f"Product version {product_version_id} not found")

        # Get all facts for this version
        ingredients = await self.facts_repo.get_current_ingredients(product_version_id)
        nutrition = await self.facts_repo.get_current_nutrition(product_version_id)
        allergens = await self.facts_repo.get_current_allergens(product_version_id)
        claims = await self.facts_repo.get_current_claims(product_version_id)
        certifications = await self.facts_repo.get_current_certifications(product_version_id)

        # Calculate individual scores
        health_score = await self._calculate_health_score(nutrition, ingredients)
        safety_score = await self._calculate_safety_score(certifications, allergens)
        sustainability_score = await self._calculate_sustainability_score(ingredients, certifications, claims)
        verification_score = await self._calculate_verification_score(ingredients, nutrition, certifications)

        return {
            "health": health_score,
            "safety": safety_score,
            "sustainability": sustainability_score,
            "verification": verification_score,
            "scheme": "LabelSquor_v1",
        }

    async def _calculate_health_score(self, nutrition: Optional[Dict], ingredients: Optional[Dict]) -> int:
        """
        Calculate health score based on:
        - Nutritional composition (60%)
        - Ingredient quality (40%)
        """
        score = 100  # Start with perfect score

        if nutrition and nutrition.get("per_100g"):
            per_100g = nutrition["per_100g"]

            # Deduct for high sugar (FSSAI HFSS criteria)
            if "sugar" in per_100g:
                sugar_g = per_100g["sugar"]["value"]
                if sugar_g > 22.5:  # High sugar
                    score -= 30
                elif sugar_g > 5:  # Medium sugar
                    score -= 15

            # Deduct for high fat
            if "fat" in per_100g:
                fat_g = per_100g["fat"]["value"]
                if fat_g > 17.5:  # High fat
                    score -= 20
                elif fat_g > 3:  # Medium fat
                    score -= 10

            # Deduct for high saturated fat
            if "saturated_fat" in per_100g:
                sat_fat_g = per_100g["saturated_fat"]["value"]
                if sat_fat_g > 5:  # High saturated fat
                    score -= 15
                elif sat_fat_g > 1.5:  # Medium saturated fat
                    score -= 7

            # Deduct for high sodium
            if "sodium" in per_100g:
                sodium_mg = per_100g["sodium"]["value"]
                if sodium_mg > 600:  # High sodium (0.6g)
                    score -= 20
                elif sodium_mg > 300:  # Medium sodium (0.3g)
                    score -= 10

            # Bonus for protein
            if "protein" in per_100g:
                protein_g = per_100g["protein"]["value"]
                if protein_g > 10:  # High protein
                    score += 10
                elif protein_g > 5:  # Medium protein
                    score += 5

            # Bonus for fiber
            if "fiber" in per_100g:
                fiber_g = per_100g["fiber"]["value"]
                if fiber_g > 6:  # High fiber
                    score += 10
                elif fiber_g > 3:  # Medium fiber
                    score += 5
        else:
            # No nutrition info = major penalty
            score -= 30

        # Ingredient quality assessment
        if ingredients and ingredients.get("normalized_list"):
            ingredient_list = ingredients["normalized_list"]

            # Penalize for certain ingredients
            bad_ingredients = [
                "palm oil",
                "hydrogenated",
                "trans fat",
                "high fructose",
                "artificial color",
                "artificial flavour",
                "msg",
            ]

            for bad in bad_ingredients:
                if any(bad in ing.lower() for ing in ingredient_list):
                    score -= 5

            # Bonus for whole ingredients
            good_ingredients = ["whole wheat", "whole grain", "oats", "nuts", "seeds"]
            for good in good_ingredients:
                if any(good in ing.lower() for ing in ingredient_list):
                    score += 3

        return max(0, min(100, score))  # Ensure score is between 0-100

    async def _calculate_safety_score(self, certifications: Optional[list], allergens: Optional[Dict]) -> int:
        """
        Calculate safety score based on:
        - Regulatory compliance (70%)
        - Allergen declaration (30%)
        """
        score = 50  # Start with base score

        # Certification compliance
        if certifications:
            for cert in certifications:
                if cert["scheme"] == "FSSAI":
                    score += 30  # FSSAI is mandatory in India
                elif cert["scheme"] in ["AGMARK", "ISI", "BIS"]:
                    score += 10
                elif cert["scheme"] in ["India Organic", "Jaivik Bharat"]:
                    score += 5

        # Allergen declaration
        if allergens:
            if allergens.get("declared_list"):
                score += 20  # Proper allergen declaration
            if allergens.get("may_contain_list"):
                score += 10  # Cross-contamination warning

        return min(100, score)

    async def _calculate_sustainability_score(
        self, ingredients: Optional[Dict], certifications: Optional[list], claims: Optional[list]
    ) -> int:
        """
        Calculate sustainability score based on:
        - Packaging info (40%)
        - Sustainable ingredients (30%)
        - Certifications (30%)
        """
        score = 40  # Base score

        # Check for sustainable certifications
        if certifications:
            for cert in certifications:
                if cert["scheme"] in ["India Organic", "Jaivik Bharat", "Rainforest Alliance"]:
                    score += 20

        # Check claims
        if claims:
            sustainable_claims = ["organic", "natural", "eco_friendly", "biodegradable"]
            for claim in claims:
                if claim["claim_type"] in sustainable_claims:
                    score += 5

        # Check ingredients
        if ingredients and ingredients.get("normalized_list"):
            # Penalize for unsustainable ingredients
            if any("palm oil" in ing.lower() for ing in ingredients["normalized_list"]):
                score -= 15  # Unless RSPO certified

        # TODO: Add packaging assessment when we have that data

        return max(0, min(100, score))

    async def _calculate_verification_score(
        self, ingredients: Optional[Dict], nutrition: Optional[Dict], certifications: Optional[list]
    ) -> int:
        """
        Calculate verification score based on:
        - Data completeness (50%)
        - Data confidence (50%)
        """
        score = 0

        # Check data completeness
        if ingredients and ingredients.get("normalized_list"):
            score += 20
            # Bonus for high confidence
            if ingredients.get("confidence", 0) > 0.8:
                score += 10

        if nutrition and nutrition.get("per_100g"):
            score += 20
            # Bonus for complete nutrition data
            if len(nutrition["per_100g"]) > 5:
                score += 10

        if certifications:
            score += 20
            # Bonus for verifiable license numbers
            if any(cert.get("id_code") for cert in certifications):
                score += 20

        return min(100, score)
