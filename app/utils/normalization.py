"""
Text normalization utilities for consistent data processing
"""
import re
import unicodedata
from typing import Optional, List


def normalize_text(text: str) -> str:
    """
    Normalize text for consistency:
    - Remove extra whitespace
    - Convert to lowercase
    - Remove accents
    - Remove special characters
    """
    if not text:
        return ""
    
    # Normalize unicode
    text = unicodedata.normalize('NFKD', text)
    
    # Remove accents
    text = ''.join(char for char in text if not unicodedata.combining(char))
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove special characters but keep alphanumeric and spaces
    text = re.sub(r'[^a-z0-9\s\-]', '', text)
    
    return text.strip()


def normalize_brand_name(name: str) -> str:
    """
    Normalize brand name for deduplication:
    - Standard normalization
    - Remove common suffixes (Ltd, Inc, etc.)
    """
    normalized = normalize_text(name)
    
    # Remove common company suffixes
    suffixes = [
        'ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation',
        'llc', 'llp', 'pvt', 'private', 'co', 'company', 'industries',
        'foods', 'brands', 'group'
    ]
    
    for suffix in suffixes:
        pattern = rf'\b{suffix}\b\.?$'
        normalized = re.sub(pattern, '', normalized).strip()
    
    return normalized


def normalize_product_name(name: str, brand_name: Optional[str] = None) -> str:
    """
    Normalize product name:
    - Standard normalization
    - Remove brand name if present
    - Remove common product terms
    """
    normalized = normalize_text(name)
    
    # Remove brand name if provided
    if brand_name:
        brand_normalized = normalize_text(brand_name)
        normalized = normalized.replace(brand_normalized, '').strip()
    
    return normalized


def normalize_unit(value: str) -> tuple[float, str]:
    """
    Normalize unit values (e.g., "500ml" -> (500, "ml"))
    Returns (quantity, unit) tuple
    """
    if not value:
        return (0, "")
    
    # Extract number and unit
    match = re.match(r'([\d.]+)\s*([a-zA-Z]+)', value.strip())
    if match:
        quantity = float(match.group(1))
        unit = match.group(2).lower()
        
        # Normalize common units
        unit_map = {
            'g': 'g',
            'gm': 'g',
            'gram': 'g',
            'grams': 'g',
            'kg': 'kg',
            'kilogram': 'kg',
            'kilograms': 'kg',
            'ml': 'ml',
            'milliliter': 'ml',
            'milliliters': 'ml',
            'l': 'l',
            'liter': 'l',
            'liters': 'l',
            'oz': 'oz',
            'ounce': 'oz',
            'ounces': 'oz',
            'lb': 'lb',
            'pound': 'lb',
            'pounds': 'lb'
        }
        
        unit = unit_map.get(unit, unit)
        return (quantity, unit)
    
    return (0, value)


def normalize_category(category: str) -> str:
    """Normalize category name"""
    normalized = normalize_text(category)
    
    # Remove common category terms
    terms = ['products', 'items', 'goods']
    for term in terms:
        normalized = normalized.replace(term, '').strip()
    
    return normalized


def extract_allergens(text: str) -> List[str]:
    """
    Extract common allergens from text
    Returns normalized list of allergens
    """
    if not text:
        return []
    
    text_lower = text.lower()
    
    # Common allergen patterns
    allergen_patterns = {
        'milk': ['milk', 'dairy', 'lactose', 'whey', 'casein', 'cream', 'butter'],
        'eggs': ['egg', 'eggs', 'albumin', 'mayonnaise'],
        'peanuts': ['peanut', 'peanuts', 'groundnut'],
        'tree_nuts': ['almond', 'cashew', 'walnut', 'pistachio', 'hazelnut', 'pecan'],
        'wheat': ['wheat', 'gluten', 'flour'],
        'soy': ['soy', 'soya', 'soybean', 'tofu'],
        'fish': ['fish', 'salmon', 'tuna', 'cod', 'anchovy'],
        'shellfish': ['shrimp', 'crab', 'lobster', 'prawn', 'shellfish'],
        'sesame': ['sesame', 'tahini'],
        'mustard': ['mustard'],
        'celery': ['celery'],
        'lupin': ['lupin', 'lupine'],
        'molluscs': ['mollusc', 'mollusk', 'oyster', 'mussel', 'squid'],
        'sulphites': ['sulphite', 'sulfite', 'sulphur', 'sulfur']
    }
    
    found_allergens = set()
    
    for allergen, keywords in allergen_patterns.items():
        for keyword in keywords:
            if keyword in text_lower:
                found_allergens.add(allergen)
                break
    
    return sorted(list(found_allergens))


def parse_gtin(gtin: str) -> Optional[str]:
    """
    Parse and validate GTIN (barcode)
    Returns normalized GTIN or None if invalid
    """
    if not gtin:
        return None
    
    # Remove any non-numeric characters
    gtin_clean = re.sub(r'\D', '', gtin)
    
    # Check valid lengths (8, 12, 13, 14 digits)
    if len(gtin_clean) not in [8, 12, 13, 14]:
        return None
    
    # Validate checksum
    if validate_gtin_checksum(gtin_clean):
        return gtin_clean
    
    return None


def validate_gtin_checksum(gtin: str) -> bool:
    """Validate GTIN checksum using Luhn algorithm"""
    if not gtin or not gtin.isdigit():
        return False
    
    # Calculate checksum
    total = 0
    for i, digit in enumerate(gtin[:-1]):
        if (len(gtin) - i - 1) % 2 == 0:
            total += int(digit) * 3
        else:
            total += int(digit)
    
    check_digit = (10 - (total % 10)) % 10
    
    return check_digit == int(gtin[-1])
