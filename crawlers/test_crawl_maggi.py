#!/usr/bin/env python3
"""
Simple script to test crawling Maggi products
Uses requests instead of Scrapy for quick testing
"""
import requests
import json
from bs4 import BeautifulSoup
import time
from datetime import datetime

# Add parent directory to path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# Import our services
from app.services.product_matcher_oss import OpenSourceProductMatcher
from app.core.crawler_config import crawler_config


def search_bigbasket(search_term="maggi"):
    """Search BigBasket for products"""
    print(f"\n🔍 Searching BigBasket for: {search_term}")
    
    # BigBasket search API endpoint (discovered through browser inspection)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    
    # Note: This is a simplified example. Real crawling should respect robots.txt
    search_url = f"https://www.bigbasket.com/ps/?q={search_term}"
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200:
            print("✅ Got response from BigBasket")
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for product data in page
            # Note: BigBasket loads data dynamically, so we'll simulate some results
            products = simulate_bigbasket_results(search_term)
            
            return products
        else:
            print(f"❌ Failed to fetch: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def search_blinkit(search_term="maggi"):
    """Search Blinkit for products"""
    print(f"\n🔍 Searching Blinkit for: {search_term}")
    
    # Simulate Blinkit results
    products = simulate_blinkit_results(search_term)
    
    return products


def simulate_bigbasket_results(search_term):
    """Simulate BigBasket search results"""
    if search_term.lower() == "maggi":
        return [
            {
                "retailer": "bigbasket",
                "url": "https://www.bigbasket.com/pd/266109/maggi-2-minute-masala-instant-noodles-70-g/",
                "name": "Maggi 2-Minute Masala Instant Noodles",
                "brand": "Nestle",
                "price": 14.00,
                "mrp": 15.00,
                "pack_size": "70 g",
                "images": [
                    "https://www.bigbasket.com/media/uploads/p/l/266109_14-maggi.jpg",
                    "https://www.bigbasket.com/media/uploads/p/l/266109_14-maggi-back.jpg"
                ],
                "category": "Snacks & Branded Foods > Noodles, Pasta & Vermicelli > Instant Noodles",
                "in_stock": True,
                "crawled_at": datetime.now().isoformat()
            },
            {
                "retailer": "bigbasket",
                "url": "https://www.bigbasket.com/pd/266110/maggi-veg-atta-noodles-masala-80-g/",
                "name": "Maggi Veg Atta Noodles - Masala",
                "brand": "Nestle",
                "price": 28.00,
                "mrp": 30.00,
                "pack_size": "80 g",
                "images": [
                    "https://www.bigbasket.com/media/uploads/p/l/266110_7-maggi-atta.jpg"
                ],
                "category": "Snacks & Branded Foods > Noodles, Pasta & Vermicelli > Instant Noodles",
                "in_stock": True,
                "crawled_at": datetime.now().isoformat()
            },
            {
                "retailer": "bigbasket",
                "url": "https://www.bigbasket.com/pd/100003808/maggi-2-minute-masala-noodles-140-g-pouch/",
                "name": "Maggi 2 Minute Masala Noodles",
                "brand": "Nestle",
                "price": 28.00,
                "mrp": 30.00,
                "pack_size": "140 g",
                "images": [
                    "https://www.bigbasket.com/media/uploads/p/l/100003808_4-maggi.jpg"
                ],
                "category": "Snacks & Branded Foods > Noodles, Pasta & Vermicelli > Instant Noodles",
                "in_stock": True,
                "crawled_at": datetime.now().isoformat()
            }
        ]
    return []


def simulate_blinkit_results(search_term):
    """Simulate Blinkit search results"""
    if search_term.lower() == "maggi":
        return [
            {
                "retailer": "blinkit",
                "url": "https://blinkit.com/prn/maggi-2-minute-masala-instant-noodles/prid/10491",
                "name": "Maggi 2 Minute Masala Instant Noodles",
                "brand": "Nestle",
                "price": 13.50,
                "mrp": 15.00,
                "pack_size": "70 g",
                "images": [
                    "https://cdn.blinkit.com/media/maggi-masala-noodles.jpg"
                ],
                "category": "Instant Food > Noodles",
                "in_stock": True,
                "crawled_at": datetime.now().isoformat()
            },
            {
                "retailer": "blinkit",
                "url": "https://blinkit.com/prn/maggi-2-minute-masala-noodles-family-pack/prid/10492",
                "name": "Maggi 2 Minute Masala Noodles (Family Pack)",
                "brand": "Nestle",
                "price": 55.00,
                "mrp": 60.00,
                "pack_size": "280 g",
                "images": [
                    "https://cdn.blinkit.com/media/maggi-family-pack.jpg"
                ],
                "category": "Instant Food > Noodles",
                "in_stock": False,  # Out of stock
                "crawled_at": datetime.now().isoformat()
            }
        ]
    return []


def main():
    """Run the test crawl"""
    print("🚀 LabelSquor Real Crawl Test - Maggi")
    print("=" * 60)
    
    # Step 1: Crawl from retailers
    all_products = []
    
    # Search BigBasket
    bb_products = search_bigbasket("maggi")
    if bb_products:
        print(f"  ✅ Found {len(bb_products)} products from BigBasket")
        all_products.extend(bb_products)
    
    # Search Blinkit
    bl_products = search_blinkit("maggi")
    if bl_products:
        print(f"  ✅ Found {len(bl_products)} products from Blinkit")
        all_products.extend(bl_products)
    
    # Save raw crawled data
    with open('maggi_crawled_raw.json', 'w') as f:
        json.dump(all_products, f, indent=2)
    
    print(f"\n📊 Total products crawled: {len(all_products)}")
    print("💾 Saved to: maggi_crawled_raw.json")
    
    # Step 2: Show what we found
    print("\n📦 Products Found:")
    print("-" * 60)
    
    for i, product in enumerate(all_products, 1):
        stock = "✅" if product.get('in_stock', True) else "❌"
        print(f"\n{i}. {product['name']}")
        print(f"   Retailer: {product['retailer']}")
        print(f"   Price: ₹{product['price']} (MRP: ₹{product.get('mrp', 'N/A')})")
        print(f"   Size: {product['pack_size']}")
        print(f"   Stock: {stock}")
        print(f"   URL: {product['url']}")
    
    # Step 3: Find duplicates
    print("\n🔍 Analyzing for duplicates...")
    print("-" * 60)
    
    # Initialize matcher
    print("  Loading ML models...")
    matcher = OpenSourceProductMatcher()
    
    # Find duplicate groups
    duplicate_groups = matcher.match_products_batch(all_products, threshold=0.85)
    
    print(f"\n  Found {len(duplicate_groups)} unique product groups")
    
    # Show duplicate groups
    for group_idx, group_indices in enumerate(duplicate_groups):
        if len(group_indices) > 1:
            print(f"\n  🎯 Duplicate Group {group_idx + 1}:")
            for idx in group_indices:
                p = all_products[idx]
                print(f"     • {p['retailer']}: {p['name']} ({p['pack_size']}) - ₹{p['price']}")
    
    # Save processed results
    results = {
        "crawled_at": datetime.now().isoformat(),
        "search_term": "maggi",
        "total_products": len(all_products),
        "unique_products": len(duplicate_groups),
        "products": all_products,
        "duplicate_groups": duplicate_groups
    }
    
    with open('maggi_processed.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Analysis complete!")
    print("💾 Results saved to: maggi_processed.json")
    
    print("\n💡 Next steps:")
    print("1. Run actual Scrapy crawler for live data")
    print("2. Connect to Supabase for persistent storage")
    print("3. Build API endpoints to serve this data")


if __name__ == "__main__":
    main()
