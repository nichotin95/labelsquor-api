"""
SQUOR Scoring Service v2
Implements the new 5-component SQUOR scoring system
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.logging import log
from app.models import ProductVersion, SquorComponent, SquorScore
from app.repositories import FactsRepository, ProductRepository


class SQUORScoringService:
    """
    Service for calculating SQUOR scores based on Indian regulations and standards

    SQUOR Components:
    - S (Safety): Ingredient & product safety (0-100)
    - Q (Quality): Product & ingredient quality (0-100)
    - U (Usability): Consumer-friendliness (0-100)
    - O (Origin): Provenance & traceability (0-100)
    - R (Responsibility): Sustainability & ethics (0-100)
    """

    # Evidence sources mapping
    EVIDENCE_SOURCES = {
        "safety": ["FSSAI", "FDA", "BIS", "PubChem", "INCI"],
        "quality": ["Lab reports", "certifications", "Codex"],
        "usability": ["FOPL norms", "WCAG for readability"],
        "origin": ["GS1", "Fairtrade", "Organic India", "Brand docs"],
        "responsibility": ["EPR norms", "sustainability frameworks"],
    }

    # Banned/harmful ingredients list (Indian context)
    BANNED_INGREDIENTS = [
        "potassium bromate",
        "rhodamine b",
        "lead chromate",
        "carbide",
        "formalin",
        "oxytocin",
        "melamine",
    ]

    HIGH_CONCERN_INGREDIENTS = [
        "trans fat",
        "high fructose corn syrup",
        "artificial colors",
        "sodium benzoate",
        "msg",
        "aspartame",
        "saccharin",
    ]

    def __init__(self, product_repo: ProductRepository, facts_repo: FactsRepository):
        self.product_repo = product_repo
        self.facts_repo = facts_repo

    async def calculate_squor(self, product_version_id: UUID) -> Dict[str, Any]:
        """Calculate all SQUOR scores for a product version"""
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

        # Get product details for additional context
        product = await self.product_repo.get(id=version.product_id)

        # Calculate individual SQUOR components
        safety_score = await self._calculate_safety_squor(ingredients, allergens, certifications)
        quality_score = await self._calculate_quality_squor(ingredients, nutrition, certifications, claims)
        usability_score = await self._calculate_usability_squor(allergens, nutrition, product)
        origin_score = await self._calculate_origin_squor(claims, certifications, product)
        responsibility_score = await self._calculate_responsibility_squor(claims, certifications, ingredients)

        # Calculate overall SQUOR score (weighted average)
        overall_score = (
            safety_score * 0.25  # 25% weight for Safety
            + quality_score * 0.25  # 25% weight for Quality
            + usability_score * 0.15  # 15% weight for Usability
            + origin_score * 0.15  # 15% weight for Origin
            + responsibility_score * 0.20  # 20% weight for Responsibility
        )

        return {
            "overall": round(overall_score, 1),
            "components": {
                "safety": round(safety_score, 1),
                "quality": round(quality_score, 1),
                "usability": round(usability_score, 1),
                "origin": round(origin_score, 1),
                "responsibility": round(responsibility_score, 1),
            },
            "calculation_method": "squor_v2",
            "scheme": "squor_v2",
        }

    async def _calculate_safety_squor(
        self, ingredients: Optional[Any], allergens: Optional[Any], certifications: Optional[Any]
    ) -> float:
        """
        Calculate SafetySquor (S) - Ingredient & product safety

        Sub-metrics:
        - Toxicology checks (25%)
        - Banned ingredients (25%)
        - Allergen thresholds (25%)
        - Usage warnings (25%)
        """
        score = 100.0  # Start with perfect score and deduct

        # 1. Check for banned ingredients (25 points)
        if ingredients and ingredients.normalized_list_json:
            ingredients_list = [i.lower() for i in ingredients.normalized_list_json]

            # Check banned ingredients
            banned_found = [ing for ing in self.BANNED_INGREDIENTS if ing in str(ingredients_list)]
            if banned_found:
                score -= 25  # Full deduction for banned ingredients
                log.warning(f"Banned ingredients found: {banned_found}")

            # Check high concern ingredients
            concern_found = [ing for ing in self.HIGH_CONCERN_INGREDIENTS if ing in str(ingredients_list)]
            if concern_found:
                score -= min(15, len(concern_found) * 3)  # -3 per concern ingredient, max -15

        # 2. Allergen declaration (25 points)
        if allergens:
            if allergens.declared_list:
                # Good - allergens are declared
                score -= 0
            else:
                # Check if common allergens are in ingredients but not declared
                if ingredients and ingredients.normalized_list_json:
                    common_allergens = ["milk", "wheat", "soy", "nuts", "egg"]
                    undeclared = [a for a in common_allergens if a in str(ingredients.normalized_list_json).lower()]
                    if undeclared:
                        score -= 15  # Major deduction for undeclared allergens
        else:
            score -= 10  # No allergen information

        # 3. Safety certifications (25 points)
        if certifications:
            # Check for FSSAI license
            fssai_found = (
                any(c.scheme == "FSSAI" for c in certifications) if hasattr(certifications, "__iter__") else False
            )
            if not fssai_found:
                score -= 15  # No FSSAI license is a major issue
        else:
            score -= 20  # No certification information

        # 4. Usage warnings (25 points) - based on product type
        # This would need product category context
        # For now, basic implementation
        if not allergens or not allergens.declared_list:
            score -= 5  # Missing usage warnings

        return max(0, score)

    async def _calculate_quality_squor(
        self, ingredients: Optional[Any], nutrition: Optional[Any], certifications: Optional[Any], claims: Optional[Any]
    ) -> float:
        """
        Calculate QualitySquor (Q) - Product & ingredient quality

        Sub-metrics:
        - Purity (25%)
        - Adulteration risk (25%)
        - Freshness indicators (25%)
        - Processing levels (25%)
        """
        score = 100.0

        # 1. Ingredient quality/purity (25 points)
        if ingredients and ingredients.normalized_list_json:
            ingredients_list = ingredients.normalized_list_json

            # Check for artificial ingredients
            artificial_count = sum(
                1
                for ing in ingredients_list
                if any(marker in ing.lower() for marker in ["artificial", "synthetic", "imitation"])
            )
            score -= min(15, artificial_count * 3)

            # Check for preservatives
            preservative_count = sum(
                1
                for ing in ingredients_list
                if any(marker in ing.lower() for marker in ["benzoate", "sorbate", "nitrite", "sulphite"])
            )
            score -= min(10, preservative_count * 2)

        # 2. Processing level (25 points)
        if ingredients and ingredients.normalized_list_json:
            # Ultra-processed indicators
            ultra_processed_markers = [
                "modified",
                "hydrogenated",
                "hydrolyzed",
                "isolate",
                "concentrate",
                "extract",
                "flavoring",
            ]
            processing_score = sum(
                3 for ing in ingredients.normalized_list_json if any(m in ing.lower() for m in ultra_processed_markers)
            )
            score -= min(25, processing_score)

        # 3. Nutritional quality (25 points)
        if nutrition:
            # Check HFSS (High Fat, Sugar, Salt) criteria
            if nutrition.per_100g_json:
                nut_data = nutrition.per_100g_json

                # High sugar (>22.5g/100g)
                if nut_data.get("sugar_g", 0) > 22.5:
                    score -= 8

                # High fat (>17.5g/100g)
                if nut_data.get("fat_g", 0) > 17.5:
                    score -= 8

                # High sodium (>600mg/100g)
                if nut_data.get("sodium_mg", 0) > 600:
                    score -= 9

        # 4. Quality certifications (25 points)
        quality_certs = ["ISO", "HACCP", "GMP", "Agmark"]
        if certifications:
            quality_cert_count = sum(1 for cert in quality_certs if any(c.scheme == cert for c in certifications))
            score += min(10, quality_cert_count * 5)  # Bonus for quality certs

        return max(0, score)

    async def _calculate_usability_squor(
        self, allergens: Optional[Any], nutrition: Optional[Any], product: Optional[Any]
    ) -> float:
        """
        Calculate UsabilitySquor (U) - Consumer-friendliness

        Sub-metrics:
        - Label readability (25%)
        - Allergen visibility (25%)
        - Instructions clarity (25%)
        - Serving info (25%)
        """
        score = 70.0  # Base score, harder to evaluate from data alone

        # 1. Allergen visibility (25 points)
        if allergens and allergens.declared_list:
            score += 15  # Good allergen declaration
            if allergens.may_contain_list:
                score += 10  # Excellent - even "may contain" warnings

        # 2. Nutrition label completeness (25 points)
        if nutrition:
            if nutrition.per_100g_json and nutrition.per_serving_json:
                score += 10  # Both per 100g and per serving
            if nutrition.serving_size:
                score += 5  # Clear serving size

        # 3. Product naming clarity (25 points)
        if product and product.name:
            # Check if product name is clear and not misleading
            if len(product.name) < 100 and not any(
                word in product.name.lower() for word in ["natural", "healthy", "pure"]
            ):
                score += 5

        # Note: Instructions clarity and label design can't be evaluated from structured data
        # Would need image analysis or manual review

        return min(100, max(0, score))

    async def _calculate_origin_squor(
        self, claims: Optional[Any], certifications: Optional[Any], product: Optional[Any]
    ) -> float:
        """
        Calculate OriginSquor (O) - Provenance & traceability

        Sub-metrics:
        - Country of origin (33%)
        - Organic/fair-trade claims (33%)
        - Supplier transparency (34%)
        """
        score = 50.0  # Base score

        # 1. Organic certifications (33 points)
        if certifications:
            organic_certs = ["India Organic", "USDA Organic", "EU Organic", "Jaivik Bharat"]
            organic_found = any(any(cert in str(c.scheme) for cert in organic_certs) for c in certifications)
            if organic_found:
                score += 20

        # 2. Fair trade certifications (33 points)
        if certifications:
            fair_trade_certs = ["Fairtrade", "Rainforest Alliance", "UTZ"]
            fair_trade_found = any(any(cert in str(c.scheme) for cert in fair_trade_certs) for c in certifications)
            if fair_trade_found:
                score += 20

        # 3. Origin claims (34 points)
        if claims and claims.claims_json:
            origin_claims = [
                c
                for c in claims.claims_json
                if any(keyword in c.lower() for keyword in ["origin", "sourced", "from", "grown in"])
            ]
            if origin_claims:
                score += 15

        # Note: Supplier transparency requires supply chain data not typically on labels

        return min(100, max(0, score))

    async def _calculate_responsibility_squor(
        self, claims: Optional[Any], certifications: Optional[Any], ingredients: Optional[Any]
    ) -> float:
        """
        Calculate ResponsibilitySquor (R) - Sustainability & ethics

        Sub-metrics:
        - Packaging recyclability (25%)
        - Carbon footprint (25%)
        - Ethical sourcing (25%)
        - Compliance (25%)
        """
        score = 40.0  # Base score

        # 1. Sustainable certifications (25 points)
        if certifications:
            sustainable_certs = ["Carbon Neutral", "Carbon Trust", "EPR", "Green Dot"]
            sustainable_found = sum(
                1 for c in certifications if any(cert in str(c.scheme) for cert in sustainable_certs)
            )
            score += min(20, sustainable_found * 10)

        # 2. Ethical sourcing - palm oil check (25 points)
        if ingredients and ingredients.normalized_list_json:
            # Check for palm oil
            has_palm_oil = any("palm" in ing.lower() for ing in ingredients.normalized_list_json)
            if has_palm_oil:
                # Check if sustainable palm oil is claimed
                if claims and claims.claims_json:
                    sustainable_palm = any("sustainable palm" in c.lower() for c in claims.claims_json)
                    if sustainable_palm:
                        score += 10  # Better than regular palm oil
                    else:
                        score -= 10  # Regular palm oil
            else:
                score += 15  # No palm oil

        # 3. Environmental claims (25 points)
        if claims and claims.claims_json:
            eco_claims = [
                c
                for c in claims.claims_json
                if any(
                    keyword in c.lower() for keyword in ["recyclable", "biodegradable", "eco-friendly", "sustainable"]
                )
            ]
            if eco_claims:
                score += min(15, len(eco_claims) * 5)

        # 4. Compliance indicators (25 points)
        if certifications:
            # Multiple certifications indicate better compliance
            cert_count = len(list(certifications)) if hasattr(certifications, "__iter__") else 0
            score += min(20, cert_count * 4)

        return min(100, max(0, score))

    async def save_squor_scores(self, product_version_id: UUID, scores: Dict[str, Any]) -> SquorScore:
        """Save calculated SQUOR scores to database"""
        # Create main score record
        squor_score = SquorScore(
            product_version_id=product_version_id,
            scheme=scores.get("scheme", "squor_v2"),
            score=Decimal(str(scores["overall"])),
            score_json=scores,
            computed_at=datetime.utcnow(),
        )

        # Save to database (implementation depends on your repository)
        await self.product_repo.save_squor_score(squor_score)

        # Save component scores
        for component, value in scores["components"].items():
            component_score = SquorComponent(
                squor_id=squor_score.squor_id,
                component_key=component,
                value=Decimal(str(value)),
                weight=Decimal("20"),  # Equal weight for now
                contribution=Decimal(str(value * 0.2)),
                explain_md=f"{component.upper()}-Squor: {self._get_component_explanation(component, value)}",
            )
            await self.product_repo.save_squor_component(component_score)

        return squor_score

    def _get_component_explanation(self, component: str, score: float) -> str:
        """Get explanation text for a component score"""
        explanations = {
            "safety": {
                80: "Excellent safety profile with no harmful ingredients",
                60: "Generally safe with minor concerns",
                40: "Some safety concerns requiring attention",
                0: "Significant safety issues detected",
            },
            "quality": {
                80: "High quality ingredients and minimal processing",
                60: "Good quality with some processed ingredients",
                40: "Moderate quality with significant processing",
                0: "Low quality, highly processed product",
            },
            "usability": {
                80: "Excellent labeling and consumer information",
                60: "Good usability with clear information",
                40: "Adequate labeling with room for improvement",
                0: "Poor labeling and consumer information",
            },
            "origin": {
                80: "Excellent traceability and origin transparency",
                60: "Good origin information available",
                40: "Limited origin and sourcing information",
                0: "No origin or traceability information",
            },
            "responsibility": {
                80: "Highly sustainable and ethical practices",
                60: "Good sustainability efforts",
                40: "Some sustainability initiatives",
                0: "Limited sustainability or ethical practices",
            },
        }

        component_explanations = explanations.get(component, {})
        for threshold in sorted(component_explanations.keys(), reverse=True):
            if score >= threshold:
                return component_explanations[threshold]

        return "Score calculated based on available data"
