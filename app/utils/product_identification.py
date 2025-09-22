"""
Product identification utilities for proper duplicate detection
"""

import hashlib
import re
from typing import Dict, Any, Optional


def extract_retailer_product_id(url: str, retailer: str) -> Optional[str]:
    """
    Extract unique product ID from retailer URL
    
    Args:
        url: Product URL
        retailer: Retailer name
        
    Returns:
        Unique product ID or None if not found
    """
    if retailer.lower() == "bigbasket":
        # BigBasket URLs: https://www.bigbasket.com/pd/40328023/product-name/
        match = re.search(r'/pd/(\d+)/', url)
        if match:
            return f"bb_{match.group(1)}"
    
    elif retailer.lower() == "blinkit":
        # Blinkit URLs: https://blinkit.com/prn/product-name/prid/12345
        match = re.search(r'/prid/(\d+)', url)
        if match:
            return f"bk_{match.group(1)}"
    
    elif retailer.lower() == "zepto":
        # Zepto URLs: https://www.zepto.com/product/product-name-12345
        match = re.search(r'/product/.*-(\d+)$', url)
        if match:
            return f"ze_{match.group(1)}"
    
    return None


def generate_product_hash(brand: str, name: str, pack_size: str = "") -> str:
    """
    Generate a unique hash for product identification
    
    Args:
        brand: Brand name
        name: Product name
        pack_size: Pack size (e.g., "70g", "200ml")
        
    Returns:
        SHA-256 hash for product identification
    """
    # Normalize inputs
    brand_norm = str(brand).strip().lower() if brand else ""
    name_norm = str(name).strip().lower() if name else ""
    pack_norm = str(pack_size).strip().lower() if pack_size else ""
    
    # Handle brand dict format
    if isinstance(brand, dict):
        brand_norm = brand.get("name", "").strip().lower()
    
    # Create unique identifier
    identifier = f"{brand_norm}|{name_norm}|{pack_norm}"
    
    # Generate hash
    return hashlib.sha256(identifier.encode('utf-8')).hexdigest()


def extract_ean_code(product_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract EAN/GTIN code from product data
    
    Args:
        product_data: Product data from crawler
        
    Returns:
        EAN code or None if not found
    """
    # Check various possible fields for EAN/GTIN
    ean_fields = [
        "ean", "ean_code", "gtin", "gtin_primary", "barcode", 
        "upc", "isbn", "product_code"
    ]
    
    # Check direct fields
    for field in ean_fields:
        if field in product_data and product_data[field]:
            ean = str(product_data[field]).strip()
            if ean and len(ean) >= 8:  # Valid EAN should be at least 8 digits
                return ean
    
    # Check in extracted_data
    extracted_data = product_data.get("extracted_data", {})
    for field in ean_fields:
        if field in extracted_data and extracted_data[field]:
            ean = str(extracted_data[field]).strip()
            if ean and len(ean) >= 8:
                return ean
    
    # Check in metadata or other nested structures
    metadata = product_data.get("metadata", {})
    for field in ean_fields:
        if field in metadata and metadata[field]:
            ean = str(metadata[field]).strip()
            if ean and len(ean) >= 8:
                return ean
    
    return None


def create_unique_product_key(product_data: Dict[str, Any]) -> str:
    """
    Create a unique key for product identification
    
    Priority:
    1. EAN/GTIN code (globally unique)
    2. Retailer product ID (from URL)
    3. Product hash (brand + name + pack_size)
    
    Args:
        product_data: Product data from crawler
        
    Returns:
        Unique product key
    """
    # Priority 1: EAN code (best for cross-retailer identification)
    ean_code = extract_ean_code(product_data)
    if ean_code:
        return f"ean_{ean_code}"
    
    # Priority 2: Retailer product ID
    url = product_data.get("url", "")
    retailer = product_data.get("retailer", "")
    retailer_id = extract_retailer_product_id(url, retailer)
    if retailer_id:
        return retailer_id
    
    # Priority 3: Fallback to product hash
    brand = product_data.get("brand", "")
    name = product_data.get("name", "")
    pack_size = product_data.get("pack_size", "") or product_data.get("weight", "")
    
    product_hash = generate_product_hash(brand, name, pack_size)
    return f"hash_{product_hash[:16]}"


def should_analyze_product(
    product_data: Dict[str, Any], 
    existing_product_keys: set
) -> tuple[bool, str]:
    """
    Determine if a product should be analyzed based on unique identification
    
    Args:
        product_data: Product data from crawler
        existing_product_keys: Set of already analyzed product keys
        
    Returns:
        (should_analyze, reason)
    """
    product_key = create_unique_product_key(product_data)
    
    if product_key in existing_product_keys:
        return False, f"Already analyzed (key: {product_key})"
    
    return True, f"New product (key: {product_key})"


def are_products_identical(product1: Dict[str, Any], product2: Dict[str, Any]) -> bool:
    """
    Check if two products are identical based on unique identification
    
    Args:
        product1: First product data
        product2: Second product data
        
    Returns:
        True if products are identical
    """
    key1 = create_unique_product_key(product1)
    key2 = create_unique_product_key(product2)
    
    return key1 == key2


def get_product_debug_info(product_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Get debug information for product identification
    
    Args:
        product_data: Product data from crawler
        
    Returns:
        Debug information dictionary
    """
    url = product_data.get("url", "")
    retailer = product_data.get("retailer", "")
    brand = product_data.get("brand", "")
    name = product_data.get("name", "")
    
    ean_code = extract_ean_code(product_data)
    retailer_id = extract_retailer_product_id(url, retailer)
    product_key = create_unique_product_key(product_data)
    product_hash = generate_product_hash(brand, name, "")
    
    return {
        "url": url,
        "retailer": retailer,
        "ean_code": ean_code or "None",
        "retailer_id": retailer_id or "None", 
        "product_key": product_key,
        "product_hash": product_hash[:16],
        "brand": str(brand),
        "name": name,
    }
