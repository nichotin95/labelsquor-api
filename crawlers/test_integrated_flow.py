#!/usr/bin/env python3
"""
Test the complete flow: Simple HTTP → JSON parsing → Data extraction
This shows how our crawler works WITHOUT Playwright!
"""

import httpx
import json
import re
from datetime import datetime


def crawl_and_process_maggi():
    """Complete flow without any browser automation"""
    
    print("🚀 BIGBASKET CRAWLER - SIMPLE & EFFECTIVE!\n")
    print("=" * 60)
    
    # Step 1: Simple HTTP request
    print("1️⃣ Making simple HTTP request to BigBasket...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = httpx.get("https://www.bigbasket.com/ps/?q=maggi", headers=headers)
    print(f"   ✅ Status: {response.status_code}")
    
    # Step 2: Extract JSON data from HTML
    print("\n2️⃣ Extracting embedded JSON data...")
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
    data = json.loads(match.group(1))
    
    products = []
    tabs = data['props']['pageProps']['SSRData']['tabs']
    
    for tab in tabs:
        for product in tab.get('product_info', {}).get('products', []):
            products.append(product)
    
    print(f"   ✅ Found {len(products)} products in JSON!")
    
    # Step 3: Process products
    print("\n3️⃣ Processing product data...")
    
    for i, product in enumerate(products[:3]):  # Show first 3
        print(f"\n   Product {i+1}:")
        print(f"   - Name: {product.get('desc', 'N/A')}")
        print(f"   - Brand: {product.get('brand', {}).get('name', 'N/A')}")
        print(f"   - Price: ₹{product.get('pricing', {}).get('discount', {}).get('sp', 'N/A')}")
        print(f"   - MRP: ₹{product.get('pricing', {}).get('discount', {}).get('mrp', 'N/A')}")
        
        # Extract images
        images = []
        if product.get('images'):
            for img in product['images']:
                if isinstance(img, dict) and img.get('s'):
                    images.append(img['s'])
        
        print(f"   - Images: {len(images)} found")
        if images:
            print(f"     • {images[0]}")
    
    # Step 4: Show what we'd do next
    print("\n4️⃣ Next steps in the pipeline:")
    print("   • Download product images")
    print("   • OCR back/side panels for ingredients")
    print("   • Parse nutrition info")
    print("   • Calculate Squor scores")
    print("   • Save to database")
    
    print("\n" + "=" * 60)
    print("✅ NO PLAYWRIGHT NEEDED! Just simple HTTP + JSON parsing!")
    print("✅ This works for BigBasket, Blinkit, and most modern sites!")
    
    return products


def show_universal_crawler_integration():
    """Show how this integrates with our universal crawler"""
    
    print("\n\n🔧 INTEGRATION WITH UNIVERSAL CRAWLER")
    print("=" * 60)
    
    print("\nThe universal crawler would call our adapter like this:")
    print("""
# In BigBasketAdapter.extract_product_data():
if '__NEXT_DATA__' in response.text:
    # Use JSON extraction (what we just did)
    return self._extract_from_nextjs(response)
else:
    # Fall back to HTML parsing
    return self._extract_from_html(response)
""")
    
    print("\nCommand to run:")
    print("scrapy crawl universal -a retailer=bigbasket -a strategy=search -a target='maggi'")
    
    print("\n✅ The adapter handles all the complexity internally!")


if __name__ == "__main__":
    # Run the demo
    products = crawl_and_process_maggi()
    show_universal_crawler_integration()
    
    # Save sample data
    with open('sample_crawl_results.json', 'w') as f:
        json.dump(products[:5], f, indent=2)
    
    print("\n💾 Sample data saved to sample_crawl_results.json")
