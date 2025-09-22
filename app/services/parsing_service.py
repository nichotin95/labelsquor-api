"""
Parsing service for label extraction and data parsing
"""

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.logging import log
from app.utils.normalization import extract_allergens, normalize_text


class ParsingService:
    """Service for parsing product labels and extracted text"""

    # Common ingredient patterns
    INGREDIENT_PATTERNS = [
        r"ingredients?\s*:?\s*([^.]+)",
        r"composition\s*:?\s*([^.]+)",
        r"contains?\s*:?\s*([^.]+)",
    ]

    # Nutrition patterns
    NUTRITION_PATTERNS = {
        "energy": [r"energy\s*:?\s*([\d.]+)\s*(kcal|cal|kj)", r"calories?\s*:?\s*([\d.]+)"],
        "protein": [r"protein\s*:?\s*([\d.]+)\s*(g|gm|gram)"],
        "carbohydrate": [r"carbohydrate\s*:?\s*([\d.]+)\s*(g|gm|gram)"],
        "fat": [r"(?:total\s+)?fat\s*:?\s*([\d.]+)\s*(g|gm|gram)"],
        "saturated_fat": [r"saturated\s+fat\s*:?\s*([\d.]+)\s*(g|gm|gram)"],
        "trans_fat": [r"trans\s+fat\s*:?\s*([\d.]+)\s*(g|gm|gram)"],
        "sugar": [r"(?:total\s+)?sugar\s*:?\s*([\d.]+)\s*(g|gm|gram)"],
        "sodium": [r"sodium\s*:?\s*([\d.]+)\s*(mg|g)"],
        "fiber": [r"(?:dietary\s+)?fib(?:er|re)\s*:?\s*([\d.]+)\s*(g|gm|gram)"],
    }

    async def parse_ingredients(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse ingredients from text"""
        if not text:
            return None

        text_lower = text.lower()
        ingredients_text = None

        # Try to find ingredients section
        for pattern in self.INGREDIENT_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
            if match:
                ingredients_text = match.group(1)
                break

        if not ingredients_text:
            return None

        # Clean and split ingredients
        # Remove common endings
        ingredients_text = re.sub(r"\.$", "", ingredients_text)
        ingredients_text = re.sub(
            r"(for more info|storage|store|keep|refrigerate).*$", "", ingredients_text, flags=re.IGNORECASE
        )

        # Split by common delimiters
        ingredients = []
        raw_ingredients = re.split(r"[,;]", ingredients_text)

        for ingredient in raw_ingredients:
            # Clean each ingredient
            ingredient = ingredient.strip()
            # Remove percentages for now
            ingredient = re.sub(r"\([\d.]+%?\)", "", ingredient)
            ingredient = ingredient.strip()

            if ingredient and len(ingredient) > 2:
                ingredients.append(ingredient)

        # Build tree structure (simplified for now)
        ingredient_tree = self._build_ingredient_tree(ingredients)

        return {
            "raw_text": ingredients_text,
            "normalized_list": ingredients,
            "tree": ingredient_tree,
            "confidence": 0.8 if len(ingredients) > 2 else 0.5,
        }

    def _build_ingredient_tree(self, ingredients: List[str]) -> Dict[str, Any]:
        """Build hierarchical ingredient tree"""
        # Simplified version - in reality this would parse sub-ingredients
        tree = {"ingredients": []}

        for ingredient in ingredients:
            # Check if ingredient has sub-ingredients in parentheses
            match = re.match(r"([^(]+)\(([^)]+)\)", ingredient)
            if match:
                main_ingredient = match.group(1).strip()
                sub_ingredients = [s.strip() for s in match.group(2).split(",")]
                tree["ingredients"].append({"name": main_ingredient, "sub_ingredients": sub_ingredients})
            else:
                tree["ingredients"].append({"name": ingredient, "sub_ingredients": []})

        return tree

    async def parse_nutrition(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse nutrition information from text"""
        if not text:
            return None

        text_lower = text.lower()
        nutrition_data = {"per_100g": {}, "per_serving": {}, "confidence": 0.0}

        # Detect if it's per 100g or per serving
        per_100g = "per 100" in text_lower or "per100" in text_lower
        per_serving = "per serving" in text_lower or "serving size" in text_lower

        nutrients_found = 0

        # Extract each nutrient
        for nutrient, patterns in self.NUTRITION_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    value = float(match.group(1))
                    unit = match.group(2) if len(match.groups()) > 1 else "g"

                    # Convert to standard units
                    if nutrient == "sodium" and unit == "g":
                        value = value * 1000  # Convert g to mg
                        unit = "mg"

                    nutrient_data = {"value": value, "unit": unit}

                    if per_100g:
                        nutrition_data["per_100g"][nutrient] = nutrient_data
                    else:
                        nutrition_data["per_serving"][nutrient] = nutrient_data

                    nutrients_found += 1
                    break

        # Extract serving size
        serving_match = re.search(r"serving\s+size\s*:?\s*([\d.]+)\s*(g|ml|gm)", text_lower)
        if serving_match:
            nutrition_data["serving_size"] = f"{serving_match.group(1)}{serving_match.group(2)}"

        # Calculate confidence based on nutrients found
        nutrition_data["confidence"] = min(nutrients_found / 5, 1.0)  # At least 5 nutrients for full confidence

        return nutrition_data if nutrients_found > 0 else None

    async def extract_allergens(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract allergen information"""
        if not text:
            return None

        text_lower = text.lower()

        # Common allergen declarations
        declared_allergens = []
        may_contain = []

        # Look for "contains" statements
        contains_match = re.search(r"contains?\s*:?\s*([^.]+)", text_lower)
        if contains_match:
            allergen_text = contains_match.group(1)
            declared_allergens = extract_allergens(allergen_text)

        # Look for "may contain" statements
        may_contain_match = re.search(r"may\s+contain\s*:?\s*([^.]+)", text_lower)
        if may_contain_match:
            allergen_text = may_contain_match.group(1)
            may_contain = extract_allergens(allergen_text)

        # Also extract from ingredients
        contains_from_ingredients = extract_allergens(text)

        if not declared_allergens and not may_contain and not contains_from_ingredients:
            return None

        return {
            "declared_list": declared_allergens,
            "may_contain_list": may_contain,
            "contains_list": contains_from_ingredients,
            "confidence": 0.9 if declared_allergens else 0.7,
        }

    async def extract_claims(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Extract product claims"""
        if not text:
            return None

        text_lower = text.lower()
        claims = []

        # Common claim patterns
        claim_patterns = {
            "organic": [r"organic", r"certified\s+organic", r"usda\s+organic"],
            "natural": [r"100%?\s+natural", r"all\s+natural"],
            "no_preservatives": [r"no\s+preservatives?", r"preservative\s+free"],
            "no_artificial_colors": [r"no\s+artificial\s+colou?rs?", r"no\s+added\s+colou?rs?"],
            "no_artificial_flavors": [r"no\s+artificial\s+flavou?rs?"],
            "gluten_free": [r"gluten\s+free", r"no\s+gluten"],
            "sugar_free": [r"sugar\s+free", r"no\s+added\s+sugar"],
            "vegan": [r"vegan", r"100%?\s+vegan"],
            "vegetarian": [r"vegetarian", r"pure\s+veg"],
            "non_gmo": [r"non[\s-]?gmo", r"gmo\s+free"],
            "whole_grain": [r"whole\s+grain", r"100%?\s+whole\s+wheat"],
            "high_protein": [r"high\s+(?:in\s+)?protein", r"protein\s+rich"],
            "low_fat": [r"low\s+fat", r"reduced\s+fat"],
            "fortified": [r"fortified\s+with", r"enriched\s+with"],
        }

        for claim_type, patterns in claim_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    claims.append(
                        {
                            "claim_type": claim_type,
                            "claim_text": pattern.replace(r"\s+", " "),
                            "verified": False,  # Would need additional verification
                            "confidence": 0.8,
                        }
                    )
                    break

        return claims if claims else None

    async def extract_certifications(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Extract certification information"""
        if not text:
            return None

        text_lower = text.lower()
        certifications = []

        # FSSAI License
        fssai_match = re.search(r"fssai\s*(?:lic(?:ense)?)?\.?\s*(?:no\.?)?\s*:?\s*([\d\s]+)", text_lower)
        if fssai_match:
            certifications.append(
                {"scheme": "FSSAI", "id_code": re.sub(r"\s+", "", fssai_match.group(1)), "confidence": 0.9}
            )

        # Agmark
        if re.search(r"agmark", text_lower):
            certifications.append({"scheme": "AGMARK", "confidence": 0.8})

        # ISI Mark
        if re.search(r"isi\s*mark", text_lower):
            certifications.append({"scheme": "ISI", "confidence": 0.8})

        # India Organic
        if re.search(r"india\s+organic", text_lower):
            certifications.append({"scheme": "India Organic", "confidence": 0.8})

        # Jaivik Bharat
        if re.search(r"jaivik\s+bharat", text_lower):
            certifications.append({"scheme": "Jaivik Bharat", "confidence": 0.8})

        return certifications if certifications else None
