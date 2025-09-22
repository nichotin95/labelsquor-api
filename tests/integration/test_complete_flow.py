#!/usr/bin/env python3
"""
Complete workflow test with proper deduplication
Shows how the system will work end-to-end
"""
import json
import sqlite3
from datetime import datetime
import hashlib


def create_product_signature(product):
    """Create a signature for matching products"""
    brand = product.get('brand', '').lower().strip()
    
    # Extract numeric size for better matching
    import re
    size_match = re.search(r'(\d+)\s*g', product.get('pack_size', '').lower())
    size = size_match.group(1) if size_match else ''
    
    # Simple signature
    return f"{brand}_{size}"


def display_workflow():
    """Display the complete workflow with realistic data"""
    
    print("🚀 LabelSquor Complete Workflow Demo")
    print("=" * 60)
    
    # Step 1: Discovery
    print("\n📡 STEP 1: Product Discovery (from search_terms.yaml)")
    print("-" * 60)
    print("  Search terms loaded from config:")
    print("    • Tier 1 (Priority 9): maggi, lays, kurkure, britannia...")
    print("    • Tier 2 (Priority 8): dabur, patanjali, mother dairy...")
    print("    • Categories: chips, noodles, biscuits, dairy...")
    
    # Step 2: Crawling
    print("\n🕷️  STEP 2: Crawling Products from Multiple Retailers")
    print("-" * 60)
    
    # Simulated crawl results
    crawled_data = [
        # Maggi from 3 retailers - WILL BE MERGED
        {
            "id": 1,
            "retailer": "bigbasket",
            "url": "https://bigbasket.com/pd/266109/maggi-masala-70g/",
            "name": "Maggi 2-Minute Masala Instant Noodles",
            "brand": "Nestle",
            "price": 14.00,
            "mrp": 15.00,
            "pack_size": "70 g",
            "images": [
                "https://bigbasket.com/media/maggi_front.jpg",
                "https://bigbasket.com/media/maggi_back.jpg"
            ],
            "ingredients_text": "Wheat Flour, Edible Vegetable Oil, Salt, Mineral, Spices & Condiments",
            "nutrition_text": None,
            "in_stock": True
        },
        {
            "id": 2,
            "retailer": "blinkit",
            "url": "https://blinkit.com/p/maggi-noodles-masala-70g/",
            "name": "Maggi Masala 2 Minute Noodles",
            "brand": "Nestle",
            "price": 13.50,
            "mrp": 15.00,
            "pack_size": "70g",
            "images": [
                "https://blinkit.com/products/maggi_main.jpg"
            ],
            "ingredients_text": "Wheat Flour (Atta), Palm Oil, Salt, Mineral Salt",
            "nutrition_text": "Energy: 313 kcal, Protein: 7.2g, Carbohydrates: 45.3g",
            "in_stock": True
        },
        {
            "id": 3,
            "retailer": "zepto",
            "url": "https://zepto.com/product/maggi-2min-masala-70g",
            "name": "Maggi 2 Min Masala Noodles",
            "brand": "Nestle",
            "price": 14.50,
            "mrp": 15.00,
            "pack_size": "70 gm",
            "images": [
                "https://zepto.com/img/maggi_1.jpg",
                "https://zepto.com/img/maggi_2.jpg",
                "https://zepto.com/img/maggi_nutrition.jpg"
            ],
            "ingredients_text": None,
            "nutrition_text": "Per 100g: Energy 446 kcal, Total Fat 17.2g",
            "in_stock": False  # Out of stock
        },
        # Different size Maggi - SEPARATE PRODUCT
        {
            "id": 4,
            "retailer": "bigbasket",
            "url": "https://bigbasket.com/pd/266110/maggi-atta-80g/",
            "name": "Maggi Veg Atta Noodles - Masala",
            "brand": "Nestle",
            "price": 28.00,
            "mrp": 30.00,
            "pack_size": "80 g",
            "images": ["https://bigbasket.com/media/maggi_atta.jpg"],
            "in_stock": True
        },
        # Lays - SINGLE SOURCE
        {
            "id": 5,
            "retailer": "bigbasket",
            "url": "https://bigbasket.com/pd/123456/lays-magic-masala/",
            "name": "Lay's India's Magic Masala Potato Chips",
            "brand": "Lays",
            "price": 20.00,
            "mrp": 20.00,
            "pack_size": "52g",
            "images": ["https://bigbasket.com/media/lays_masala.jpg"],
            "in_stock": True
        }
    ]
    
    for p in crawled_data:
        status = "✅" if p['in_stock'] else "❌"
        print(f"  {status} {p['retailer']}: {p['name']} (₹{p['price']}) - {p['pack_size']}")
    
    # Step 3: Deduplication
    print("\n🔍 STEP 3: ML-Based Deduplication")
    print("-" * 60)
    
    # Group by signature
    groups = {}
    for product in crawled_data:
        sig = create_product_signature(product)
        if sig not in groups:
            groups[sig] = []
        groups[sig].append(product)
    
    print(f"  Unique product signatures found: {len(groups)}")
    for sig, products in groups.items():
        if len(products) > 1:
            print(f"\n  🎯 Found duplicates for: {sig}")
            for p in products:
                print(f"     • {p['retailer']}: {p['name']}")
    
    # Step 4: Consolidation
    print("\n🤖 STEP 4: AI-Powered Consolidation")
    print("-" * 60)
    
    consolidated_products = []
    
    for sig, group in groups.items():
        if len(group) == 1:
            # Single source
            product = group[0]
            print(f"\n  📦 Single source: {product['name']}")
            consolidated_products.append(product)
        else:
            # Multiple sources - consolidate
            print(f"\n  🔄 Consolidating {len(group)} sources for: {group[0]['brand']} {group[0]['pack_size']}")
            
            # Merge data
            merged = {
                'name': group[0]['name'],  # In real system, AI picks best name
                'brand': group[0]['brand'],
                'pack_size': group[0]['pack_size'],
                'retailers': [],
                'prices': {},
                'images': [],
                'ingredients_text': None,
                'nutrition_text': None,
                'availability': {}
            }
            
            # Collect from all sources
            for p in group:
                merged['retailers'].append(p['retailer'])
                merged['prices'][p['retailer']] = p['price']
                merged['images'].extend(p['images'])
                merged['availability'][p['retailer']] = p['in_stock']
                
                # Keep longest text
                if p.get('ingredients_text') and (not merged['ingredients_text'] or 
                    len(p['ingredients_text']) > len(merged['ingredients_text'])):
                    merged['ingredients_text'] = p['ingredients_text']
                
                if p.get('nutrition_text') and (not merged['nutrition_text'] or 
                    len(p['nutrition_text']) > len(merged['nutrition_text'])):
                    merged['nutrition_text'] = p['nutrition_text']
            
            # Remove duplicate images
            merged['images'] = list(dict.fromkeys(merged['images']))
            
            # Calculate price range
            prices = list(merged['prices'].values())
            merged['min_price'] = min(prices)
            merged['max_price'] = max(prices)
            merged['best_price_retailer'] = min(merged['prices'], key=merged['prices'].get)
            
            # Show consolidated result
            print(f"    ✅ Name: {merged['name']}")
            print(f"    💰 Price range: ₹{merged['min_price']} - ₹{merged['max_price']}")
            print(f"    🏪 Best price: {merged['best_price_retailer']} (₹{merged['min_price']})")
            print(f"    📸 Total images: {len(merged['images'])}")
            print(f"    📝 Has ingredients: {'✅' if merged['ingredients_text'] else '❌'}")
            print(f"    📊 Has nutrition: {'✅' if merged['nutrition_text'] else '❌'}")
            
            # Availability
            in_stock_at = [r for r, avail in merged['availability'].items() if avail]
            if in_stock_at:
                print(f"    🛒 In stock at: {', '.join(in_stock_at)}")
            else:
                print(f"    ❌ Out of stock everywhere")
            
            consolidated_products.append(merged)
    
    # Step 5: Storage
    print("\n💾 STEP 5: Storing in Database")
    print("-" * 60)
    
    # Create in-memory database
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            brand TEXT,
            pack_size TEXT,
            min_price REAL,
            max_price REAL,
            best_retailer TEXT,
            retailers TEXT,
            images TEXT,
            has_ingredients BOOLEAN,
            has_nutrition BOOLEAN,
            signature TEXT UNIQUE
        )
    ''')
    
    stored = 0
    for product in consolidated_products:
        sig = create_product_signature(product)
        
        # Handle both consolidated and single products
        if 'retailers' in product and isinstance(product['retailers'], list):
            # Consolidated
            retailers = json.dumps(product['retailers'])
            images = json.dumps(product['images'])
            min_price = product['min_price']
            max_price = product['max_price']
            best_retailer = product.get('best_price_retailer', product['retailers'][0])
            has_ingredients = bool(product.get('ingredients_text'))
            has_nutrition = bool(product.get('nutrition_text'))
        else:
            # Single
            retailers = json.dumps([product['retailer']])
            images = json.dumps(product.get('images', []))
            min_price = product['price']
            max_price = product['price']
            best_retailer = product['retailer']
            has_ingredients = bool(product.get('ingredients_text'))
            has_nutrition = bool(product.get('nutrition_text'))
        
        try:
            cursor.execute('''
                INSERT INTO products 
                (name, brand, pack_size, min_price, max_price, best_retailer,
                 retailers, images, has_ingredients, has_nutrition, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product['name'], product['brand'], product['pack_size'],
                min_price, max_price, best_retailer,
                retailers, images, has_ingredients, has_nutrition, sig
            ))
            stored += 1
            print(f"  ✅ Stored: {product['name']}")
        except sqlite3.IntegrityError:
            print(f"  ⏭️  Already exists: {product['name']}")
    
    conn.commit()
    
    # Final summary
    print(f"\n📊 Final Summary")
    print("-" * 60)
    print(f"  • Products crawled: {len(crawled_data)}")
    print(f"  • Unique products: {stored}")
    print(f"  • Space saved: {len(crawled_data) - stored} duplicate entries avoided")
    
    # Show database
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    
    print(f"\n📦 Products in Database:")
    for p in products:
        _, name, brand, size, min_p, max_p, best, retailers, images, has_ing, has_nut, _ = p
        retailers_list = json.loads(retailers)
        images_count = len(json.loads(images))
        
        print(f"\n  {name}")
        print(f"    Brand: {brand} | Size: {size}")
        if min_p != max_p:
            print(f"    Price: ₹{min_p} - ₹{max_p} (best at {best})")
        else:
            print(f"    Price: ₹{min_p}")
        print(f"    Available on: {', '.join(retailers_list)} ({len(retailers_list)} retailers)")
        print(f"    Data: {images_count} images, Ingredients: {'✅' if has_ing else '❌'}, Nutrition: {'✅' if has_nut else '❌'}")
    
    print("\n✨ Key Benefits Demonstrated:")
    print("  1. Automatic deduplication (3 Maggi entries → 1)")
    print("  2. Price comparison across retailers")
    print("  3. Complete data aggregation (all images, best texts)")
    print("  4. Inventory tracking (know where products are in stock)")
    print("  5. Zero manual intervention needed")
    print("  6. Runs with FREE open-source ML models")


if __name__ == "__main__":
    display_workflow()
