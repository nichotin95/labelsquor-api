"""
Crawler configuration loader
Reads YAML configuration files for search terms and categories
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.core.logging import logger


class CrawlerConfigLoader:
    """Loads and manages crawler configuration from YAML files"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize config loader

        Args:
            config_dir: Directory containing config files
                       Defaults to configs/crawler/
        """
        if config_dir is None:
            # Get project root directory
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "configs" / "crawler"

        self.config_dir = Path(config_dir)
        self._search_terms_cache = None
        self._categories_cache = None

        # Check if config directory exists
        if not self.config_dir.exists():
            logger.warning(f"Config directory not found: {self.config_dir}")
            self.config_dir.mkdir(parents=True, exist_ok=True)

    @lru_cache(maxsize=1)
    def load_search_terms(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load search terms configuration"""
        if force_reload:
            self._search_terms_cache = None
            self.load_search_terms.cache_clear()

        if self._search_terms_cache is not None:
            return self._search_terms_cache

        config_file = self.config_dir / "search_terms.yaml"

        if not config_file.exists():
            logger.warning(f"Search terms config not found: {config_file}")
            return self._get_default_search_terms()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self._search_terms_cache = yaml.safe_load(f)
                logger.info(f"Loaded search terms from {config_file}")
                return self._search_terms_cache
        except Exception as e:
            logger.error(f"Error loading search terms: {e}")
            return self._get_default_search_terms()

    @lru_cache(maxsize=1)
    def load_categories(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load categories configuration"""
        if force_reload:
            self._categories_cache = None
            self.load_categories.cache_clear()

        if self._categories_cache is not None:
            return self._categories_cache

        config_file = self.config_dir / "categories.yaml"

        if not config_file.exists():
            logger.warning(f"Categories config not found: {config_file}")
            return self._get_default_categories()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self._categories_cache = yaml.safe_load(f)
                logger.info(f"Loaded categories from {config_file}")
                return self._categories_cache
        except Exception as e:
            logger.error(f"Error loading categories: {e}")
            return self._get_default_categories()

    def get_priority_brands(self, tier: str = "all") -> List[str]:
        """Get priority brand search terms"""
        config = self.load_search_terms()
        brands = config.get("priority_brands", {})

        if tier == "all":
            # Combine all tiers
            all_brands = []
            for tier_brands in brands.values():
                all_brands.extend(tier_brands)
            return all_brands
        else:
            return brands.get(tier, [])

    def get_search_terms_by_category(self, category: str) -> List[str]:
        """Get search terms for a specific category"""
        config = self.load_search_terms()

        # Check product categories
        product_cats = config.get("product_categories", {})
        if category in product_cats:
            return product_cats[category]

        # Check health keywords
        health = config.get("health_keywords", {})
        if category in health:
            return health[category]

        # Check other sections
        for section in ["trending_searches", "certification_keywords", "regional_products"]:
            section_data = config.get(section, {})
            if category in section_data:
                return section_data[category]

        return []

    def get_all_search_terms_with_priority(self) -> List[Dict[str, Any]]:
        """Get all search terms with their priorities"""
        config = self.load_search_terms()
        terms = []

        # Priority brands
        brands = config.get("priority_brands", {})

        # Tier 1 - Priority 9
        for brand in brands.get("tier1", []):
            terms.append({"term": brand, "category": "brand", "priority": 9, "metadata": {"tier": "tier1"}})

        # Tier 2 - Priority 8
        for brand in brands.get("tier2", []):
            terms.append({"term": brand, "category": "brand", "priority": 8, "metadata": {"tier": "tier2"}})

        # Tier 3 - Priority 7
        for brand in brands.get("tier3", []):
            terms.append({"term": brand, "category": "brand", "priority": 7, "metadata": {"tier": "tier3"}})

        # Product categories - Priority 6
        product_cats = config.get("product_categories", {})
        for cat_name, cat_terms in product_cats.items():
            for term in cat_terms:
                terms.append(
                    {"term": term, "category": "product", "priority": 6, "metadata": {"product_category": cat_name}}
                )

        # Health keywords - Priority 7
        health = config.get("health_keywords", {})
        for health_cat, keywords in health.items():
            for keyword in keywords:
                terms.append(
                    {"term": keyword, "category": "health", "priority": 7, "metadata": {"health_category": health_cat}}
                )

        return terms

    def get_category_mappings(self, retailer: str) -> Dict[str, str]:
        """Get category URL mappings for a specific retailer"""
        config = self.load_categories()
        categories = config.get("categories", {})
        mappings = {}

        for main_cat, sub_cats in categories.items():
            for sub_cat_key, sub_cat_data in sub_cats.items():
                retailers = sub_cat_data.get("retailers", {})
                if retailer in retailers:
                    internal_key = f"{main_cat}/{sub_cat_key}"
                    mappings[internal_key] = retailers[retailer]

        # Add special categories
        special = config.get("special_categories", {})
        for special_key, special_data in special.items():
            retailers = special_data.get("retailers", {})
            if retailer in retailers:
                mappings[f"special/{special_key}"] = retailers[retailer]

        return mappings

    def get_category_info(self, main_cat: str, sub_cat: str) -> Dict[str, Any]:
        """Get detailed information about a category"""
        config = self.load_categories()
        categories = config.get("categories", {})

        if main_cat in categories and sub_cat in categories[main_cat]:
            return categories[main_cat][sub_cat]

        return {}

    def _get_default_search_terms(self) -> Dict[str, Any]:
        """Return minimal default search terms if config not found"""
        return {
            "priority_brands": {
                "tier1": ["maggi", "lays", "amul", "britannia", "parle"],
                "tier2": ["nestle", "cadbury", "haldiram"],
                "tier3": [],
            },
            "product_categories": {
                "snacks": ["chips", "namkeen", "biscuits"],
                "beverages": ["soft drinks", "juice"],
                "dairy": ["milk", "curd", "paneer"],
                "instant_foods": ["noodles", "pasta"],
            },
        }

    def _get_default_categories(self) -> Dict[str, Any]:
        """Return minimal default categories if config not found"""
        return {
            "categories": {
                "snacks": {
                    "chips_crisps": {
                        "display_name": "Chips & Crisps",
                        "retailers": {"bigbasket": "/pc/snacks-branded-foods/chips-crisps/"},
                    }
                }
            }
        }

    def reload_configs(self):
        """Force reload all configurations"""
        self.load_search_terms.cache_clear()
        self.load_categories.cache_clear()
        self._search_terms_cache = None
        self._categories_cache = None
        logger.info("Reloaded all crawler configurations")


# Global instance
crawler_config = CrawlerConfigLoader()
