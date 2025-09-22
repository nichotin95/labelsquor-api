"""
Product Matching and Deduplication Service
Uses both deterministic rules and ML models for accurate matching
"""

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.logging import logger
from app.utils.normalization import normalize_text
from app.models.product import Product


class ProductMatcher:
    """
    Intelligent product matching using multiple strategies:
    1. Exact barcode/GTIN matching
    2. Fuzzy string matching on normalized names
    3. Semantic similarity using sentence embeddings
    4. Brand + category constraints
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize with a lightweight sentence transformer model

        Args:
            model_name: HuggingFace model for embeddings
                       all-MiniLM-L6-v2 is fast and good for short texts
        """
        self.encoder = SentenceTransformer(model_name)
        self.similarity_threshold = 0.85
        self.fuzzy_threshold = 0.80

        # Cache for embeddings
        self._embedding_cache = {}

    def find_duplicate(self, new_product: Dict[str, Any], existing_products: List[Product]) -> Optional[Product]:
        """
        Find if new product already exists in database

        Returns:
            Matched product or None
        """
        # Step 1: Try exact matching
        if match := self._exact_match(new_product, existing_products):
            logger.info(f"Exact match found for {new_product['name']}")
            return match

        # Step 2: Try fuzzy + rule-based matching
        if match := self._fuzzy_match(new_product, existing_products):
            logger.info(f"Fuzzy match found for {new_product['name']}")
            return match

        # Step 3: Try ML-based semantic matching
        if match := self._semantic_match(new_product, existing_products):
            logger.info(f"Semantic match found for {new_product['name']}")
            return match

        return None

    def _exact_match(self, new_product: Dict[str, Any], existing_products: List[Product]) -> Optional[Product]:
        """Exact matching using unique identifiers"""

        # 1. Barcode/GTIN matching
        new_barcode = new_product.get("barcode") or new_product.get("gtin")
        if new_barcode:
            for product in existing_products:
                if product.barcode == new_barcode:
                    return product

        # 2. SKU matching (retailer + SKU should be unique)
        new_sku = new_product.get("sku")
        new_retailer = new_product.get("retailer")
        if new_sku and new_retailer:
            for product in existing_products:
                # Check if same SKU from same retailer
                identifiers = product.identifiers or []
                for identifier in identifiers:
                    if identifier.retailer == new_retailer and identifier.retailer_sku == new_sku:
                        return product

        return None

    def _fuzzy_match(self, new_product: Dict[str, Any], existing_products: List[Product]) -> Optional[Product]:
        """Fuzzy matching using normalized strings"""

        # Normalize new product details
        new_name = self._normalize_product_name(new_product["name"])
        new_brand = (new_product.get("brand") or "").lower().strip()
        new_size = self._extract_size(new_product.get("pack_size", ""))

        # Must have same brand
        brand_matches = [p for p in existing_products if p.brand and p.brand.lower().strip() == new_brand]

        if not brand_matches:
            return None

        # Check name similarity
        best_match = None
        best_score = 0

        for product in brand_matches:
            existing_name = self._normalize_product_name(product.name)

            # Calculate similarity
            name_similarity = SequenceMatcher(None, new_name, existing_name).ratio()

            # Boost score if size matches
            existing_size = self._extract_size(product.pack_size or "")
            size_match = (new_size == existing_size) if new_size else True

            score = name_similarity
            if size_match:
                score += 0.1

            if score > best_score and score >= self.fuzzy_threshold:
                best_score = score
                best_match = product

        return best_match

    def _semantic_match(self, new_product: Dict[str, Any], existing_products: List[Product]) -> Optional[Product]:
        """ML-based semantic matching using embeddings"""

        # Create text representation of new product
        new_text = self._create_product_text(new_product)
        new_embedding = self._get_embedding(new_text)

        # Filter by brand first
        new_brand = (new_product.get("brand") or "").lower().strip()
        candidates = [p for p in existing_products if p.brand and p.brand.lower().strip() == new_brand]

        if not candidates:
            return None

        # Compare embeddings
        best_match = None
        best_similarity = 0

        for product in candidates:
            # Create text representation
            existing_text = self._create_product_text(
                {
                    "name": product.name,
                    "brand": product.brand,
                    "pack_size": product.pack_size,
                    "description": product.description,
                }
            )

            existing_embedding = self._get_embedding(existing_text)

            # Calculate cosine similarity
            similarity = cosine_similarity(new_embedding.reshape(1, -1), existing_embedding.reshape(1, -1))[0][0]

            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_match = product

        return best_match

    def _normalize_product_name(self, name: str) -> str:
        """Normalize product name for comparison"""
        # Remove common words
        stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from"}

        # Normalize
        name = name.lower()
        name = re.sub(r"[^\w\s]", " ", name)  # Remove punctuation
        name = re.sub(r"\s+", " ", name)  # Multiple spaces to single

        # Remove stopwords
        words = name.split()
        words = [w for w in words if w not in stopwords]

        return " ".join(words).strip()

    def _extract_size(self, size_text: str) -> Optional[str]:
        """Extract normalized size from text"""
        if not size_text:
            return None

        # Common patterns
        patterns = [
            r"(\d+\.?\d*)\s*(g|gm|gram|grams)",
            r"(\d+\.?\d*)\s*(kg|kilogram|kilograms)",
            r"(\d+\.?\d*)\s*(ml|milliliter|milliliters)",
            r"(\d+\.?\d*)\s*(l|ltr|liter|liters)",
        ]

        text = size_text.lower()
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1)
                unit = match.group(2)[0]  # First letter
                return f"{value}{unit}"

        return None

    def _create_product_text(self, product: Dict[str, Any]) -> str:
        """Create text representation for embedding"""
        parts = []

        if brand := product.get("brand"):
            parts.append(brand)

        if name := product.get("name"):
            parts.append(name)

        if size := product.get("pack_size"):
            parts.append(size)

        if desc := product.get("description"):
            # Limit description length
            parts.append(desc[:200])

        return " ".join(parts)

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get sentence embedding with caching"""
        # Create cache key
        cache_key = hashlib.md5(text.encode()).hexdigest()

        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        # Generate embedding
        embedding = self.encoder.encode(text, convert_to_numpy=True)

        # Cache it
        self._embedding_cache[cache_key] = embedding

        # Limit cache size
        if len(self._embedding_cache) > 10000:
            # Remove oldest entries
            self._embedding_cache = dict(list(self._embedding_cache.items())[-5000:])

        return embedding

    def calculate_match_confidence(self, product1: Dict[str, Any], product2: Dict[str, Any]) -> float:
        """Calculate confidence score for a match"""
        score = 0.0

        # Exact identifiers
        if product1.get("barcode") == product2.get("barcode"):
            return 1.0

        # Brand match
        if product1.get("brand", "").lower() == product2.get("brand", "").lower():
            score += 0.3
        else:
            return 0.0  # Different brands = no match

        # Name similarity
        name1 = self._normalize_product_name(product1["name"])
        name2 = self._normalize_product_name(product2["name"])
        name_sim = SequenceMatcher(None, name1, name2).ratio()
        score += name_sim * 0.4

        # Size match
        size1 = self._extract_size(product1.get("pack_size", ""))
        size2 = self._extract_size(product2.get("pack_size", ""))
        if size1 and size2 and size1 == size2:
            score += 0.2

        # Semantic similarity
        text1 = self._create_product_text(product1)
        text2 = self._create_product_text(product2)
        emb1 = self._get_embedding(text1)
        emb2 = self._get_embedding(text2)

        semantic_sim = cosine_similarity(emb1.reshape(1, -1), emb2.reshape(1, -1))[0][0]

        score += semantic_sim * 0.1

        return min(score, 1.0)


class RelevanceFilter:
    """Filter out irrelevant or low-quality product data"""

    def __init__(self):
        self.min_name_length = 3
        self.min_fields_required = 4
        self.spam_keywords = ["test", "demo", "sample", "dummy", "placeholder"]

    def is_relevant(self, product: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if product data is relevant and complete enough

        Returns:
            (is_relevant, reason)
        """
        # Must have name
        name = product.get("name", "").strip()
        if not name or len(name) < self.min_name_length:
            return False, "Missing or invalid product name"

        # Check for spam
        name_lower = name.lower()
        for spam in self.spam_keywords:
            if spam in name_lower:
                return False, f"Spam keyword detected: {spam}"

        # Must have brand or clear product identity
        if not product.get("brand") and len(name.split()) < 2:
            return False, "No brand and name too short"

        # Count non-empty fields
        important_fields = ["name", "brand", "price", "images", "description", "pack_size", "category"]

        field_count = sum(1 for field in important_fields if product.get(field))

        if field_count < self.min_fields_required:
            return False, f"Too few fields: {field_count}/{self.min_fields_required}"

        # Must be food/beverage product (basic check)
        if category := product.get("category"):
            non_food_categories = ["electronics", "mobile", "laptop", "fashion", "home", "furniture", "books", "sports"]
            if any(cat in category.lower() for cat in non_food_categories):
                return False, f"Non-food category: {category}"

        return True, "Relevant product"
