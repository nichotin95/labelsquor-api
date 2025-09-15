"""
Unified product taxonomy for LabelSquor
This is our source of truth for categorizing products
"""
from typing import Dict, List, Optional, Tuple
from enum import Enum


class ProductCategory(Enum):
    """Top-level product categories"""
    SNACKS = "snacks"
    BEVERAGES = "beverages"
    DAIRY = "dairy"
    INSTANT_FOODS = "instant_foods"
    STAPLES = "staples"
    BAKERY = "bakery"
    BREAKFAST = "breakfast"
    CONDIMENTS = "condiments"
    FROZEN = "frozen"
    SWEETS = "sweets"


# Hierarchical category structure
TAXONOMY = {
    ProductCategory.SNACKS: {
        "chips_crisps": {
            "name": "Chips & Crisps",
            "keywords": ["chips", "crisps", "wafers", "potato chips"],
            "brands": ["lays", "kurkure", "bingo", "uncle chips", "haldiram"]
        },
        "namkeen_mixtures": {
            "name": "Namkeen & Mixtures",
            "keywords": ["namkeen", "mixture", "bhujia", "sev", "chivda"],
            "brands": ["haldiram", "bikaji", "balaji", "yellow diamond"]
        },
        "nuts_dryfruits": {
            "name": "Nuts & Dry Fruits",
            "keywords": ["almonds", "cashews", "raisins", "walnuts", "pistachios"],
            "brands": ["happilo", "nutraj", "tulsi", "borges"]
        },
        "popcorn": {
            "name": "Popcorn",
            "keywords": ["popcorn", "corn", "caramel corn"],
            "brands": ["act ii", "american corn", "4700bc"]
        }
    },
    ProductCategory.BEVERAGES: {
        "carbonated": {
            "name": "Carbonated Drinks",
            "keywords": ["cola", "soda", "aerated", "fizzy", "soft drink"],
            "brands": ["coca cola", "pepsi", "thums up", "sprite", "limca"]
        },
        "juices": {
            "name": "Juices",
            "keywords": ["juice", "fruit juice", "nectar", "squash"],
            "brands": ["real", "tropicana", "minute maid", "maaza", "frooti"]
        },
        "energy_health": {
            "name": "Energy & Health Drinks",
            "keywords": ["energy drink", "health drink", "protein drink", "sports drink"],
            "brands": ["red bull", "sting", "mountain dew", "gatorade", "glucon d"]
        },
        "water": {
            "name": "Water",
            "keywords": ["mineral water", "packaged water", "sparkling water"],
            "brands": ["bisleri", "kinley", "aquafina", "himalayan"]
        }
    },
    ProductCategory.DAIRY: {
        "milk": {
            "name": "Milk",
            "keywords": ["milk", "toned milk", "full cream", "skimmed milk"],
            "brands": ["amul", "mother dairy", "nestle", "nandini"]
        },
        "curd_yogurt": {
            "name": "Curd & Yogurt",
            "keywords": ["curd", "yogurt", "dahi", "lassi", "buttermilk"],
            "brands": ["amul", "mother dairy", "nestle", "danone"]
        },
        "cheese_paneer": {
            "name": "Cheese & Paneer",
            "keywords": ["cheese", "paneer", "cottage cheese", "mozzarella"],
            "brands": ["amul", "britannia", "go", "dlecta"]
        },
        "butter_cream": {
            "name": "Butter & Cream",
            "keywords": ["butter", "cream", "malai", "ghee"],
            "brands": ["amul", "mother dairy", "britannia", "nilgiri"]
        }
    },
    ProductCategory.INSTANT_FOODS: {
        "noodles": {
            "name": "Noodles",
            "keywords": ["noodles", "instant noodles", "cup noodles", "ramen"],
            "brands": ["maggi", "top ramen", "yippee", "wai wai", "ching's"]
        },
        "pasta": {
            "name": "Pasta",
            "keywords": ["pasta", "macaroni", "spaghetti", "penne"],
            "brands": ["maggi", "bambino", "disano", "borges"]
        },
        "ready_to_eat": {
            "name": "Ready to Eat",
            "keywords": ["ready to eat", "rte", "instant meal", "heat and eat"],
            "brands": ["mtr", "haldiram", "gits", "kohinoor", "tasty bite"]
        },
        "soups": {
            "name": "Soups",
            "keywords": ["soup", "instant soup", "cup soup"],
            "brands": ["knorr", "maggi", "lipton", "continental"]
        }
    },
    ProductCategory.STAPLES: {
        "atta_flours": {
            "name": "Atta & Flours",
            "keywords": ["atta", "wheat flour", "maida", "besan", "rice flour"],
            "brands": ["aashirvaad", "fortune", "rajdhani", "pillsbury"]
        },
        "rice": {
            "name": "Rice",
            "keywords": ["rice", "basmati", "sona masoori", "brown rice"],
            "brands": ["india gate", "dawat", "kohinoor", "fortune"]
        },
        "pulses": {
            "name": "Pulses & Dals",
            "keywords": ["dal", "lentils", "pulses", "toor", "moong", "chana"],
            "brands": ["tata sampann", "fortune", "rajdhani", "organic tattva"]
        },
        "cooking_oils": {
            "name": "Cooking Oils",
            "keywords": ["oil", "cooking oil", "sunflower", "mustard", "coconut"],
            "brands": ["fortune", "saffola", "sundrop", "dhara"]
        }
    }
}


class TaxonomyManager:
    """Manages product categorization and retailer mappings"""
    
    # Retailer-specific category mappings
    RETAILER_MAPPINGS = {
        "bigbasket": {
            ("snacks", "chips_crisps"): "/pc/snacks-branded-foods/chips-crisps/",
            ("snacks", "namkeen_mixtures"): "/pc/snacks-branded-foods/namkeen-snacks/",
            ("beverages", "carbonated"): "/pc/beverages/soft-drinks/",
            ("beverages", "juices"): "/pc/beverages/juices/",
            ("dairy", "milk"): "/pc/dairy/milk/",
            ("dairy", "curd_yogurt"): "/pc/dairy/curd/",
            ("instant_foods", "noodles"): "/pc/snacks-branded-foods/noodles-pasta-vermicelli/",
        },
        "blinkit": {
            ("snacks", "chips_crisps"): "/c/chips-crisps-nachos/",
            ("snacks", "namkeen_mixtures"): "/c/namkeen-snacks/",
            ("beverages", "carbonated"): "/c/soft-drinks/",
            ("beverages", "juices"): "/c/juices-drinks/",
            ("dairy", "milk"): "/c/milk/",
            ("instant_foods", "noodles"): "/c/noodles/",
        },
        "zepto": {
            ("snacks", "chips_crisps"): "/categories/chips-wafers",
            ("snacks", "namkeen_mixtures"): "/categories/namkeen",
            ("beverages", "carbonated"): "/categories/soft-drinks",
            ("beverages", "juices"): "/categories/juices",
            ("dairy", "milk"): "/categories/milk-products",
            ("instant_foods", "noodles"): "/categories/instant-noodles",
        }
    }
    
    @classmethod
    def get_all_categories(cls) -> List[Tuple[str, str, str]]:
        """Get all category paths as (main, sub, display_name)"""
        categories = []
        for main_cat in ProductCategory:
            for sub_key, sub_data in TAXONOMY[main_cat].items():
                categories.append((
                    main_cat.value,
                    sub_key,
                    sub_data["name"]
                ))
        return categories
    
    @classmethod
    def get_retailer_mapping(cls, category: Tuple[str, str], retailer: str) -> Optional[str]:
        """Get retailer-specific URL for a category"""
        if retailer not in cls.RETAILER_MAPPINGS:
            return None
        return cls.RETAILER_MAPPINGS[retailer].get(category)
    
    @classmethod
    def get_category_keywords(cls, main_category: str, sub_category: str) -> List[str]:
        """Get search keywords for a category"""
        if main_cat := ProductCategory(main_category):
            if sub_data := TAXONOMY[main_cat].get(sub_category):
                return sub_data["keywords"]
        return []
    
    @classmethod
    def get_category_brands(cls, main_category: str, sub_category: str) -> List[str]:
        """Get popular brands for a category"""
        if main_cat := ProductCategory(main_category):
            if sub_data := TAXONOMY[main_cat].get(sub_category):
                return sub_data["brands"]
        return []
    
    @classmethod
    def categorize_product(cls, product_name: str, brand: str = None) -> Optional[Tuple[str, str]]:
        """Attempt to categorize a product based on name and brand"""
        product_lower = product_name.lower()
        brand_lower = brand.lower() if brand else ""
        
        # Check each category's keywords and brands
        for main_cat in ProductCategory:
            for sub_key, sub_data in TAXONOMY[main_cat].items():
                # Check keywords
                for keyword in sub_data["keywords"]:
                    if keyword in product_lower:
                        return (main_cat.value, sub_key)
                
                # Check if brand matches
                if brand_lower:
                    for known_brand in sub_data["brands"]:
                        if known_brand in brand_lower or brand_lower in known_brand:
                            return (main_cat.value, sub_key)
        
        return None


# Universal search terms
UNIVERSAL_SEARCH_TERMS = {
    "priority_brands": [
        "maggi", "lays", "kurkure", "britannia", "parle", "amul",
        "haldiram", "nestle", "cadbury", "coca cola", "pepsi"
    ],
    "health_keywords": [
        "sugar free", "low fat", "organic", "whole grain", "protein",
        "gluten free", "vegan", "diabetic", "zero calorie"
    ],
    "trending_keywords": [
        "new launch", "limited edition", "combo pack", "family pack",
        "festive special", "regional flavour"
    ],
    "certification_keywords": [
        "fssai", "agmark", "bis", "iso", "organic certified",
        "india organic", "jaivik bharat"
    ]
}
