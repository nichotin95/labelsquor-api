"""
Product Consolidation Service
Merges product data from multiple retailers into a single refined record
"""

import asyncio
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sentence_transformers import CrossEncoder
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.product import Product, ProductIdentifier
from app.models.source import SourcePage
from app.services.parsing_service import ParsingService
from app.services.product_matcher import ProductMatcher, RelevanceFilter


class ProductConsolidator:
    """
    Consolidates product information from multiple sources
    Uses AI to merge and refine data for accuracy
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        # TODO: Temporarily simplified - will re-enable advanced matching later
        try:
            self.matcher = ProductMatcher()
            self.filter = RelevanceFilter()
            self.parser = ParsingService()
            # Cross-encoder for ranking information quality
            self.quality_ranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except ImportError as e:
            logger.warning(f"Advanced matching disabled due to missing dependencies: {e}")
            self.matcher = None
            self.filter = None
            self.parser = None
            self.quality_ranker = None

    async def should_crawl_product(self, brand: str, product_name: str, retailer: str) -> Tuple[bool, Optional[str]]:
        """
        Check if we should crawl this product

        Returns:
            (should_crawl, reason)
        """
        # Normalize inputs
        brand_normalized = brand.lower().strip()

        # Check if product already exists
        existing = await self.db.execute(
            select(Product)
            .where(and_(Product.brand.ilike(f"%{brand_normalized}%"), Product.is_active == True))
            .limit(10)
        )
        existing_products = existing.scalars().all()

        # Check for matches
        test_product = {"name": product_name, "brand": brand, "retailer": retailer}

        if self.matcher:
            match = self.matcher.find_duplicate(test_product, existing_products)
        else:
            match = None

        if match:
            # Check if we already have this retailer's data
            identifiers = await self.db.execute(
                select(ProductIdentifier).where(
                    and_(ProductIdentifier.product_id == match.id, ProductIdentifier.retailer == retailer)
                )
            )

            if identifiers.scalar_one_or_none():
                return False, f"Product already exists: {match.id}"
            else:
                return True, f"Need data from {retailer} for existing product {match.id}"

        return True, "New product"

    async def consolidate_product_data(self, product_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Consolidate product data from multiple retailers

        Args:
            product_sources: List of product data from different retailers

        Returns:
            Consolidated product data
        """
        if not product_sources:
            raise ValueError("No product sources provided")

        if len(product_sources) == 1:
            # Single source, just validate and return
            return self._validate_single_source(product_sources[0])

        # Group data by field
        field_values = defaultdict(list)
        for source in product_sources:
            for field, value in source.items():
                if value:  # Skip None/empty values
                    field_values[field].append(
                        {
                            "value": value,
                            "retailer": source.get("retailer", "unknown"),
                            "confidence": source.get("confidence", 0.5),
                        }
                    )

        # Consolidate each field
        consolidated = {}

        # Simple fields - take most common or highest confidence
        for field in ["brand", "category", "subcategory", "manufacturer"]:
            consolidated[field] = self._pick_best_value(field_values.get(field, []))

        # Name - use AI to pick best
        consolidated["name"] = self._consolidate_product_name(field_values.get("name", []))

        # Description - merge multiple sources
        consolidated["description"] = self._merge_descriptions(field_values.get("description", []))

        # Pack size - normalize and pick most specific
        consolidated["pack_size"] = self._consolidate_pack_size(field_values.get("pack_size", []))

        # Price - calculate range
        price_data = self._consolidate_prices(product_sources)
        consolidated.update(price_data)

        # Images - collect all unique
        consolidated["images"] = self._consolidate_images(field_values.get("images", []))

        # Ingredients and nutrition - merge and parse
        consolidated["ingredients_text"] = self._merge_text_fields(field_values.get("ingredients_text", []))
        consolidated["nutrition_text"] = self._merge_text_fields(field_values.get("nutrition_text", []))

        # Parse the merged text
        if consolidated["ingredients_text"]:
            ingredients_data = self.parser.parse_ingredients(consolidated["ingredients_text"])
            consolidated["ingredients"] = ingredients_data.get("ingredients", [])
            consolidated["allergens"] = ingredients_data.get("allergens", [])

        if consolidated["nutrition_text"]:
            consolidated["nutrition"] = self.parser.parse_nutrition(consolidated["nutrition_text"])

        # Metadata
        consolidated["source_count"] = len(product_sources)
        consolidated["retailers"] = [s.get("retailer") for s in product_sources]
        consolidated["last_updated"] = datetime.utcnow()

        # Calculate confidence score
        consolidated["confidence_score"] = self._calculate_confidence(consolidated, product_sources)

        return consolidated

    def _pick_best_value(self, values: List[Dict[str, Any]]) -> Optional[str]:
        """Pick best value based on frequency and confidence"""
        if not values:
            return None

        # Count occurrences
        value_counts = defaultdict(float)
        for item in values:
            value_counts[item["value"]] += item.get("confidence", 0.5)

        # Return most confident/frequent
        return max(value_counts.items(), key=lambda x: x[1])[0]

    def _consolidate_product_name(self, name_values: List[Dict[str, Any]]) -> str:
        """Use AI to pick the best product name"""
        if not name_values:
            return ""

        if len(name_values) == 1:
            return name_values[0]["value"]

        # Rank names by quality
        names = [v["value"] for v in name_values]
        query = "Complete product name with brand and variant"

        try:
            # Score each name
            scores = self.quality_ranker.predict([(query, name) for name in names])

            # Return highest scoring name
            best_idx = scores.argmax()
            return names[best_idx]
        except Exception as e:
            logger.error(f"Error ranking names: {e}")
            # Fallback to longest name
            return max(names, key=len)

    def _merge_descriptions(self, desc_values: List[Dict[str, Any]]) -> str:
        """Merge multiple descriptions intelligently"""
        if not desc_values:
            return ""

        descriptions = [v["value"] for v in desc_values]

        # Remove duplicates while preserving order
        seen = set()
        unique_descs = []
        for desc in descriptions:
            desc_clean = desc.strip().lower()
            if desc_clean not in seen:
                seen.add(desc_clean)
                unique_descs.append(desc)

        # Combine with proper formatting
        if len(unique_descs) == 1:
            return unique_descs[0]

        # Use AI to merge or just concatenate
        return " ".join(unique_descs)

    def _consolidate_pack_size(self, size_values: List[Dict[str, Any]]) -> Optional[str]:
        """Consolidate pack sizes"""
        if not size_values:
            return None

        sizes = [v["value"] for v in size_values]

        # Try to normalize and find most specific
        normalized_sizes = []
        for size in sizes:
            # Extract numeric value and unit
            import re

            match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z]+)", size)
            if match:
                value = float(match.group(1))
                unit = match.group(2).lower()
                normalized_sizes.append((value, unit, size))

        if not normalized_sizes:
            return sizes[0]  # Return first as-is

        # Prefer more specific units (g over kg, ml over l)
        specific_units = ["g", "ml", "pcs", "sachets"]
        for value, unit, original in normalized_sizes:
            if unit in specific_units:
                return original

        return normalized_sizes[0][2]

    def _consolidate_prices(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate price information"""
        prices = []
        mrps = []

        for source in sources:
            if price := source.get("price"):
                prices.append(
                    {
                        "value": float(price),
                        "retailer": source.get("retailer"),
                        "date": source.get("crawled_at", datetime.utcnow()),
                    }
                )

            if mrp := source.get("mrp"):
                mrps.append(float(mrp))

        result = {}

        if prices:
            # Current price range
            price_values = [p["value"] for p in prices]
            result["min_price"] = min(price_values)
            result["max_price"] = max(price_values)
            result["avg_price"] = statistics.mean(price_values)
            result["price_sources"] = prices

        if mrps:
            # MRP should be consistent
            result["mrp"] = statistics.mode(mrps) if len(mrps) > 1 else mrps[0]

        return result

    def _consolidate_images(self, image_values: List[Dict[str, Any]]) -> List[str]:
        """Consolidate images from multiple sources"""
        all_images = []
        seen_hashes = set()

        for item in image_values:
            images = item["value"]
            if isinstance(images, list):
                all_images.extend(images)
            else:
                all_images.append(images)

        # Remove duplicates based on URL similarity
        unique_images = []
        for img in all_images:
            # Simple hash of filename
            import os

            filename = os.path.basename(img).lower()
            if filename not in seen_hashes:
                seen_hashes.add(filename)
                unique_images.append(img)

        return unique_images[:10]  # Limit to 10 images

    def _merge_text_fields(self, text_values: List[Dict[str, Any]]) -> str:
        """Merge text fields like ingredients, nutrition"""
        if not text_values:
            return ""

        texts = [v["value"] for v in text_values]

        # Find longest most complete text
        longest = max(texts, key=len)

        # Check if others have additional info
        all_words = set()
        for text in texts:
            words = set(text.lower().split())
            all_words.update(words)

        longest_words = set(longest.lower().split())
        missing_words = all_words - longest_words

        # If significant missing info, combine
        if len(missing_words) > 5:
            return " | ".join(texts)

        return longest

    def _calculate_confidence(self, consolidated: Dict[str, Any], sources: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for consolidated data"""
        score = 0.0

        # More sources = higher confidence
        source_score = min(len(sources) / 3, 1.0) * 0.3
        score += source_score

        # Check data completeness
        important_fields = ["name", "brand", "ingredients", "nutrition", "images", "pack_size", "category"]

        present_fields = sum(1 for f in important_fields if consolidated.get(f))
        completeness_score = (present_fields / len(important_fields)) * 0.4
        score += completeness_score

        # Check data consistency
        if "price_sources" in consolidated:
            prices = [p["value"] for p in consolidated["price_sources"]]
            if prices:
                # Low variance = high consistency
                if len(prices) > 1:
                    cv = statistics.stdev(prices) / statistics.mean(prices)
                    consistency_score = max(0, 1 - cv) * 0.3
                else:
                    consistency_score = 0.3
                score += consistency_score

        return min(score, 1.0)

    def _validate_single_source(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean single source data"""
        # Remove empty fields
        cleaned = {k: v for k, v in source.items() if v}

        # Ensure required fields
        if not cleaned.get("name"):
            raise ValueError("Product name is required")

        if not cleaned.get("brand"):
            # Try to extract from name
            name_parts = cleaned["name"].split()
            if name_parts:
                cleaned["brand"] = name_parts[0]

        cleaned["source_count"] = 1
        cleaned["confidence_score"] = 0.6  # Lower confidence for single source

        return cleaned

    async def consolidate_products(
        self, products: List[Dict[str, Any]], group_variants: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Consolidate products using proper product identification
        """
        if not products:
            return []

        from app.utils.product_identification import create_unique_product_key, get_product_debug_info
        
        # Group products by unique product key
        product_groups = {}
        
        for product in products:
            product_key = create_unique_product_key(product)
            debug_info = get_product_debug_info(product)
            
            logger.info(f"Product: {debug_info['name']} | Brand: {debug_info['brand']} | Key: {product_key} | Retailer ID: {debug_info['retailer_id']}")
            
            if product_key not in product_groups:
                product_groups[product_key] = []
            product_groups[product_key].append(product)
        
        # Create consolidated entries (merge data from same product across retailers)
        consolidated = []
        for product_key, group in product_groups.items():
            if len(group) > 1:
                # Multiple sources for same product - merge them
                merged = self._merge_product_data(group)
                logger.info(f"Merged {len(group)} sources for product key {product_key}")
                consolidated.append(merged)
            else:
                # Single source - use as is
                consolidated.append(group[0])
        
        logger.info(f"Consolidated {len(products)} products into {len(consolidated)} unique products")
        return consolidated

    def _merge_product_data(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge data from multiple sources into single product"""
        # Start with first product as base
        merged = products[0].copy()

        # Track all sources
        merged["sources"] = [p["retailer"] for p in products]
        merged["source_urls"] = {p["retailer"]: p["url"] for p in products}

        # Collect all images
        all_images = []
        for p in products:
            all_images.extend(p.get("images", []))
        merged["images"] = list(set(all_images))  # Remove duplicates

        # Use most detailed description
        for p in products:
            if p.get("extracted_data", {}).get("description"):
                if len(p["extracted_data"]["description"]) > len(
                    merged.get("extracted_data", {}).get("description", "")
                ):
                    merged["extracted_data"]["description"] = p["extracted_data"]["description"]

        # Average price across sources
        prices = [p["price"] for p in products if p.get("price")]
        if prices:
            merged["average_price"] = sum(prices) / len(prices)
            merged["price_range"] = {"min": min(prices), "max": max(prices)}

        return merged


class ConsolidationPipeline:
    """
    Main pipeline for product consolidation workflow
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.consolidator = ProductConsolidator(db)
        self.matcher = ProductMatcher()

    async def process_discovered_product(
        self, product_url: str, retailer: str, product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a newly discovered product

        Returns:
            {
                'action': 'created' | 'updated' | 'skipped',
                'product_id': uuid,
                'reason': str
            }
        """
        # Check relevance
        is_relevant, reason = self.consolidator.filter.is_relevant(product_data)
        if not is_relevant:
            return {"action": "skipped", "reason": f"Irrelevant: {reason}"}

        # Extract brand
        brand = product_data.get("brand", "")
        if not brand:
            return {"action": "skipped", "reason": "No brand information"}

        # Check if we should crawl
        should_crawl, reason = await self.consolidator.should_crawl_product(brand, product_data["name"], retailer)

        if not should_crawl:
            return {"action": "skipped", "reason": reason}

        # Find existing product or similar products
        existing_products = await self._find_existing_products(brand)
        match = self.matcher.find_duplicate(product_data, existing_products)

        if match:
            # Add this source to existing product
            return await self._update_existing_product(match, product_data, retailer)
        else:
            # Check if we have similar products from other retailers
            similar_sources = await self._find_similar_pending_products(product_data)

            if similar_sources:
                # We have data from other retailers, consolidate now
                all_sources = similar_sources + [product_data]
                consolidated = await self.consolidator.consolidate_product_data(all_sources)
                return await self._create_consolidated_product(consolidated)
            else:
                # First time seeing this product, store as pending
                return await self._store_pending_product(product_data, retailer)

    async def _find_existing_products(self, brand: str) -> List[Product]:
        """Find existing products from the same brand"""
        result = await self.db.execute(
            select(Product).where(and_(Product.brand.ilike(f"%{brand}%"), Product.is_active == True)).limit(100)
        )
        return result.scalars().all()

    async def _find_similar_pending_products(self, product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar products in pending queue"""
        # This would query a pending_products table
        # For now, return empty
        return []

    async def _update_existing_product(
        self, existing: Product, new_data: Dict[str, Any], retailer: str
    ) -> Dict[str, Any]:
        """Update existing product with new source"""
        # Add identifier
        identifier = ProductIdentifier(
            product_id=existing.id,
            retailer=retailer,
            retailer_sku=new_data.get("sku"),
            retailer_url=new_data.get("url"),
        )
        self.db.add(identifier)

        # Update price history
        if new_price := new_data.get("price"):
            # Add to price history
            pass

        # Check if we should re-consolidate
        # (e.g., if we now have data from 3+ retailers)

        await self.db.commit()

        return {"action": "updated", "product_id": existing.id, "reason": f"Added {retailer} data to existing product"}

    async def _create_consolidated_product(self, consolidated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new product from consolidated data"""
        product = Product(**consolidated_data)
        self.db.add(product)
        await self.db.commit()

        return {
            "action": "created",
            "product_id": product.id,
            "reason": f'Created from {consolidated_data["source_count"]} sources',
        }

    async def _store_pending_product(self, product_data: Dict[str, Any], retailer: str) -> Dict[str, Any]:
        """Store product data as pending for future consolidation"""
        # This would store in a pending_products table
        # For now, create directly
        product = Product(**product_data)
        self.db.add(product)
        await self.db.commit()

        return {
            "action": "created",
            "product_id": product.id,
            "reason": "Created from single source (pending consolidation)",
        }

    async def search_product(self, product_name: str, brand: Optional[str], retailer: str) -> List[Dict[str, Any]]:
        """Search for a product on a specific retailer"""
        # Import the appropriate parser
        import os
        import sys

        sys.path.append(os.path.join(os.path.dirname(__file__), "../../crawlers"))

        results = []

        if retailer == "bigbasket":
            from simple_bigbasket_parser import SimpleBigBasketParser

            parser = SimpleBigBasketParser()

            # Search by product name
            search_term = f"{brand} {product_name}" if brand else product_name
            search_results = parser.search_products(search_term)

            # Get detailed data for matching products
            for result in search_results[:5]:  # Limit to 5 results per retailer
                if self._is_likely_match(result, product_name, brand):
                    try:
                        detailed = parser.get_product_details(result["url"])
                        if detailed:
                            results.append(
                                {
                                    "url": result["url"],
                                    "name": detailed.get("name", result["name"]),
                                    "brand": detailed.get("brand", result["brand"]),
                                    "retailer": retailer,
                                    "images": detailed.get("all_image_urls", []),
                                    "price": detailed.get("price"),
                                    "extracted_data": detailed,
                                }
                            )
                    except Exception as e:
                        logger.error(f"Error fetching product details: {str(e)}")

        else:
            # Mock data for other retailers
            results.append(
                {
                    "url": f"https://{retailer}.com/product/mock",
                    "name": product_name,
                    "brand": brand or "Unknown",
                    "retailer": retailer,
                    "images": [],
                    "price": 100.0,
                    "extracted_data": {},
                }
            )

        return results

    def _is_likely_match(self, result: Dict, target_name: str, target_brand: Optional[str]) -> bool:
        """Check if search result likely matches target product"""
        result_name = result.get("name", "").lower()
        result_brand = result.get("brand", "").lower()
        target_name_lower = target_name.lower()

        # Check brand match if specified
        if target_brand:
            target_brand_lower = target_brand.lower()
            if target_brand_lower not in result_brand and target_brand_lower not in result_name:
                return False

        # Check name similarity
        # Simple check - can be enhanced with fuzzy matching
        name_words = set(target_name_lower.split())
        result_words = set(result_name.split())

        # At least 50% of target words should be in result
        common_words = name_words.intersection(result_words)
        if len(common_words) >= len(name_words) * 0.5:
            return True

        return False


    def _merge_product_data(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge data from multiple sources into single product"""
        # Start with first product as base
        merged = products[0].copy()

        # Track all sources
        merged["sources"] = [p["retailer"] for p in products]
        merged["source_urls"] = {p["retailer"]: p["url"] for p in products}

        # Collect all images
        all_images = []
        for p in products:
            all_images.extend(p.get("images", []))
        merged["images"] = list(set(all_images))  # Remove duplicates

        # Use most detailed description
        for p in products:
            if p.get("extracted_data", {}).get("description"):
                if len(p["extracted_data"]["description"]) > len(
                    merged.get("extracted_data", {}).get("description", "")
                ):
                    merged["extracted_data"]["description"] = p["extracted_data"]["description"]

        # Average price across sources
        prices = [p["price"] for p in products if p.get("price")]
        if prices:
            merged["average_price"] = sum(prices) / len(prices)
            merged["price_range"] = {"min": min(prices), "max": max(prices)}

        return merged
