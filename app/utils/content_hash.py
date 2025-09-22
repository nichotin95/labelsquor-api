"""
Content hashing utilities for duplicate detection
"""

import hashlib
import json
from typing import Any, Dict, List, Optional


def calculate_product_content_hash(product_data: Dict[str, Any]) -> str:
    """
    Calculate a content hash for product data to detect changes
    
    Args:
        product_data: Product data from crawler
        
    Returns:
        SHA-256 hash of normalized content
    """
    # Extract key fields that matter for product analysis
    content_fields = {
        "name": product_data.get("name", "").strip().lower(),
        "brand": _normalize_brand(product_data.get("brand", "")),
        "price": product_data.get("price", 0),
        "weight": product_data.get("weight", "").strip(),
        "pack_size": product_data.get("pack_size", "").strip(),
        "description": product_data.get("description", "").strip().lower(),
        "ingredients": _normalize_list(product_data.get("ingredients", [])),
        "nutrition": _normalize_nutrition(product_data.get("nutrition", {})),
        "claims": _normalize_list(product_data.get("claims", [])),
        "images": _normalize_image_urls(product_data.get("images", [])),
        "category": product_data.get("category", "").strip().lower(),
    }
    
    # Create deterministic JSON string
    content_json = json.dumps(content_fields, sort_keys=True, separators=(',', ':'))
    
    # Generate SHA-256 hash
    return hashlib.sha256(content_json.encode('utf-8')).hexdigest()


def _normalize_brand(brand_data: Any) -> str:
    """Normalize brand data to string"""
    if isinstance(brand_data, dict):
        return brand_data.get("name", "").strip().lower()
    return str(brand_data).strip().lower() if brand_data else ""


def _normalize_list(items: List[Any]) -> List[str]:
    """Normalize list of items to lowercase strings, sorted"""
    if not items:
        return []
    normalized = [str(item).strip().lower() for item in items if item]
    return sorted(normalized)


def _normalize_nutrition(nutrition: Dict[str, Any]) -> Dict[str, float]:
    """Normalize nutrition data"""
    if not nutrition:
        return {}
    
    normalized = {}
    for key, value in nutrition.items():
        try:
            normalized[key.lower().strip()] = float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            normalized[key.lower().strip()] = 0.0
    
    return dict(sorted(normalized.items()))


def _normalize_image_urls(image_urls: List[str]) -> List[str]:
    """
    Normalize image URLs for comparison
    We only care about the core image identifiers, not CDN params
    """
    if not image_urls:
        return []
    
    normalized = []
    for url in image_urls:
        if not url:
            continue
        # Remove query parameters and fragments for comparison
        clean_url = url.split('?')[0].split('#')[0].strip()
        normalized.append(clean_url)
    
    return sorted(normalized)


def should_create_new_version(
    current_data: Dict[str, Any], 
    previous_version_hash: Optional[str]
) -> tuple[bool, str]:
    """
    Determine if a new product version should be created
    
    Args:
        current_data: New product data from crawler
        previous_version_hash: Hash from the most recent version
        
    Returns:
        (should_create, reason)
    """
    if not previous_version_hash:
        return True, "No previous version exists"
    
    current_hash = calculate_product_content_hash(current_data)
    
    if current_hash != previous_version_hash:
        return True, f"Content changed (hash: {current_hash[:8]}...)"
    
    return False, f"Content identical (hash: {current_hash[:8]}...)"


def identify_content_changes(
    current_data: Dict[str, Any], 
    previous_data: Dict[str, Any]
) -> List[str]:
    """
    Identify specific fields that changed between versions
    
    Returns:
        List of changed field names
    """
    changes = []
    
    # Key fields to track
    fields_to_compare = [
        "name", "brand", "price", "weight", "pack_size", 
        "description", "ingredients", "nutrition", "claims", "images"
    ]
    
    for field in fields_to_compare:
        current_value = current_data.get(field)
        previous_value = previous_data.get(field)
        
        # Normalize for comparison
        if field == "brand":
            current_value = _normalize_brand(current_value)
            previous_value = _normalize_brand(previous_value)
        elif field in ["ingredients", "claims"]:
            current_value = _normalize_list(current_value or [])
            previous_value = _normalize_list(previous_value or [])
        elif field == "nutrition":
            current_value = _normalize_nutrition(current_value or {})
            previous_value = _normalize_nutrition(previous_value or {})
        elif field == "images":
            current_value = _normalize_image_urls(current_value or [])
            previous_value = _normalize_image_urls(previous_value or [])
        else:
            current_value = str(current_value or "").strip().lower()
            previous_value = str(previous_value or "").strip().lower()
        
        if current_value != previous_value:
            changes.append(field)
    
    return changes
