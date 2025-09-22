#!/usr/bin/env python3
"""
Test script to demonstrate SQUOR v2 scoring
Shows how scores are calculated and stored
"""

import json
from datetime import datetime


def demonstrate_squor_scoring():
    """Show SQUOR scoring examples"""
    
    print("🎯 SQUOR v2 SCORING DEMONSTRATION")
    print("="*60)
    
    # Example 1: Healthy Product
    print("\n📦 Example 1: Organic Whole Wheat Atta")
    print("-"*60)
    
    healthy_product = {
        "product": {"name": "Organic Whole Wheat Atta", "brand": "Nature's Best"},
        "ingredients": ["Organic whole wheat"],
        "nutrition": {
            "energy_kcal": 341,
            "protein_g": 11.8,
            "carbohydrate_g": 72.6,
            "sugar_g": 2.5,
            "fat_g": 1.5,
            "saturated_fat_g": 0.3,
            "sodium_mg": 3
        },
        "certifications": ["FSSAI", "India Organic", "USDA Organic"],
        "scores": {
            "safety": 95,        # No harmful ingredients, FSSAI certified
            "quality": 90,       # Organic, minimal processing
            "usability": 80,     # Clear labeling
            "origin": 85,        # Organic certified, traceable
            "responsibility": 75 # Sustainable but standard packaging
        }
    }
    
    calculate_and_display_squor(healthy_product)
    
    # Example 2: Processed Product
    print("\n\n📦 Example 2: Instant Noodles")
    print("-"*60)
    
    processed_product = {
        "product": {"name": "Masala Instant Noodles", "brand": "QuickEat"},
        "ingredients": [
            "Refined wheat flour", "Palm oil", "Salt", "Sugar",
            "Flavour enhancers (E621, E627, E631)", "Colours (E102, E110)",
            "Preservatives (E211)", "Acidity regulators"
        ],
        "nutrition": {
            "energy_kcal": 459,
            "protein_g": 9.4,
            "carbohydrate_g": 57.7,
            "sugar_g": 3.8,
            "fat_g": 21.8,
            "saturated_fat_g": 10.3,
            "sodium_mg": 1633
        },
        "certifications": ["FSSAI"],
        "scores": {
            "safety": 65,        # Has FSSAI but contains additives
            "quality": 45,       # Highly processed, palm oil
            "usability": 70,     # Instructions clear but high sodium not highlighted
            "origin": 30,        # No origin info, no organic claims
            "responsibility": 25 # Palm oil, non-recyclable packaging
        }
    }
    
    calculate_and_display_squor(processed_product)
    
    # Example 3: Premium Product
    print("\n\n📦 Example 3: Premium Organic Honey")
    print("-"*60)
    
    premium_product = {
        "product": {"name": "Wild Forest Honey", "brand": "Himalayan Gold"},
        "ingredients": ["100% Pure Honey"],
        "nutrition": {
            "energy_kcal": 304,
            "protein_g": 0.3,
            "carbohydrate_g": 82.4,
            "sugar_g": 82.1,
            "fat_g": 0,
            "saturated_fat_g": 0,
            "sodium_mg": 4
        },
        "certifications": ["FSSAI", "India Organic", "Fairtrade", "Carbon Neutral"],
        "scores": {
            "safety": 100,       # Pure, natural, certified
            "quality": 95,       # Unprocessed, pure
            "usability": 85,     # Clear labeling, usage instructions
            "origin": 95,        # Full traceability, fair trade
            "responsibility": 90 # Carbon neutral, glass jar recyclable
        }
    }
    
    calculate_and_display_squor(premium_product)
    
    # Show comparison
    print("\n\n📊 SQUOR COMPARISON")
    print("="*60)
    print("Product                          | Overall | S   | Q   | U   | O   | R   | Rating")
    print("-"*85)
    
    products = [
        ("Organic Whole Wheat Atta", healthy_product),
        ("Masala Instant Noodles", processed_product),
        ("Wild Forest Honey", premium_product)
    ]
    
    for name, product in products:
        scores = product['scores']
        overall = calculate_overall_squor(scores)
        rating = get_squor_rating(overall)
        
        print(f"{name:<30} | {overall:6.1f} | {scores['safety']:3d} | {scores['quality']:3d} | "
              f"{scores['usability']:3d} | {scores['origin']:3d} | {scores['responsibility']:3d} | {rating}")
    
    print("\n💡 Key Insights:")
    print("• Organic products score higher in Quality and Origin")
    print("• Processed foods lose points in Quality and Responsibility")
    print("• FSSAI certification is baseline for Safety")
    print("• Sustainability certifications boost Responsibility score")


def calculate_overall_squor(scores: dict) -> float:
    """Calculate weighted SQUOR score"""
    return (
        scores['safety'] * 0.25 +
        scores['quality'] * 0.25 +
        scores['usability'] * 0.15 +
        scores['origin'] * 0.15 +
        scores['responsibility'] * 0.20
    )


def get_squor_rating(score: float) -> str:
    """Get rating based on score"""
    if score >= 80:
        return "🟢 Excellent"
    elif score >= 60:
        return "🟡 Good"
    elif score >= 40:
        return "🟠 Fair"
    else:
        return "🔴 Poor"


def calculate_and_display_squor(product: dict):
    """Calculate and display SQUOR scores"""
    scores = product['scores']
    overall = calculate_overall_squor(scores)
    rating = get_squor_rating(overall)
    
    print(f"Product: {product['product']['name']}")
    print(f"Brand: {product['product']['brand']}")
    print(f"\n🎯 SQUOR Scores:")
    print(f"  S (Safety):         {scores['safety']:3d}/100")
    print(f"  Q (Quality):        {scores['quality']:3d}/100")
    print(f"  U (Usability):      {scores['usability']:3d}/100")
    print(f"  O (Origin):         {scores['origin']:3d}/100")
    print(f"  R (Responsibility): {scores['responsibility']:3d}/100")
    print(f"\n  Overall SQUOR:      {overall:.1f}/100 {rating}")
    
    # Show sub-metric breakdown
    print(f"\n📋 Key Factors:")
    if scores['safety'] < 70:
        print("  ⚠️  Safety concerns: Check ingredients and certifications")
    if scores['quality'] < 60:
        print("  ⚠️  Quality issues: High processing or artificial ingredients")
    if scores['origin'] < 50:
        print("  ⚠️  Origin transparency: Limited traceability information")
    if scores['responsibility'] < 50:
        print("  ⚠️  Sustainability: Consider environmental impact")


if __name__ == "__main__":
    demonstrate_squor_scoring()
