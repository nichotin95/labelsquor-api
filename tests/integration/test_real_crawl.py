#!/usr/bin/env python3
"""
Test real crawling with Scrapy
Fetches actual products from retailers
"""
import json
import os
import subprocess
import time
from pathlib import Path
import sqlite3
from datetime import datetime

# Change to crawler directory
CRAWLER_DIR = Path(__file__).parent / "crawlers"
os.chdir(CRAWLER_DIR)


def setup_test_db():
    """Create test database"""
    db = sqlite3.connect('test_products.db')
    cursor = db.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            retailer TEXT,
            url TEXT UNIQUE,
            name TEXT,
            brand TEXT,
            price REAL,
            mrp REAL,
            pack_size TEXT,
            images TEXT,
            category TEXT,
            breadcrumbs TEXT,
            description TEXT,
            in_stock BOOLEAN,
            crawled_at TIMESTAMP
        )
    ''')
    
    db.commit()
    return db


def run_spider_test(search_term="maggi", retailer="bigbasket", max_items=5):
    """Run actual spider and get results"""
    print(f"\n🕷️  Running {retailer} spider for '{search_term}'...")
    
    # Output file
    output_file = f"test_{retailer}_{search_term}.json"
    
    # Remove old output
    if os.path.exists(output_file):
        os.remove(output_file)
    
    # Run spider command
    cmd = [
        "scrapy", "crawl", "universal",
        "-a", f"retailer={retailer}",
        "-a", "strategy=search",
        "-a", f"target={search_term}",
        "-s", f"CLOSESPIDER_ITEMCOUNT={max_items}",
        "-L", "INFO",
        "-o", output_file
    ]
    
    print(f"  Command: {' '.join(cmd)}")
    
    try:
        # Run spider
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"  ❌ Spider failed: {result.stderr}")
            return []
        
        # Wait a moment for file to be written
        time.sleep(1)
        
        # Read results
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                products = json.load(f)
            
            print(f"  ✅ Found {len(products)} products")
            return products
        else:
            print("  ⚠️  No output file created")
            return []
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return []


def display_products(products):
    """Display crawled products"""
    print("\n📦 Products Found:")
    print("-" * 80)
    
    for i, product in enumerate(products, 1):
        print(f"\n{i}. {product.get('name', 'Unknown')}")
        print(f"   Brand: {product.get('brand', 'N/A')}")
        print(f"   Price: ₹{product.get('price', 'N/A')} (MRP: ₹{product.get('mrp', 'N/A')})")
        print(f"   Size: {product.get('pack_size', 'N/A')}")
        print(f"   URL: {product.get('url', 'N/A')}")
        
        # Images
        images = product.get('images', [])
        if images:
            print(f"   Images: {len(images)} found")
            for j, img in enumerate(images[:2], 1):  # Show first 2
                print(f"     {j}. {img}")
        
        # Category
        breadcrumbs = product.get('breadcrumbs', [])
        if breadcrumbs:
            print(f"   Category: {' > '.join(breadcrumbs)}")
        
        # Ingredients/Nutrition
        if product.get('ingredients_text'):
            print(f"   Ingredients: {product['ingredients_text'][:100]}...")
        if product.get('nutrition_text'):
            print(f"   Nutrition: {product['nutrition_text'][:100]}...")


def store_in_db(db, products):
    """Store products in database"""
    cursor = db.cursor()
    stored = 0
    
    for product in products:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO products
                (retailer, url, name, brand, price, mrp, pack_size,
                 images, category, breadcrumbs, description, in_stock, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product.get('retailer'),
                product.get('url'),
                product.get('name'),
                product.get('brand'),
                product.get('price'),
                product.get('mrp'),
                product.get('pack_size'),
                json.dumps(product.get('images', [])),
                product.get('category'),
                json.dumps(product.get('breadcrumbs', [])),
                product.get('description'),
                product.get('in_stock', True),
                datetime.now().isoformat()
            ))
            stored += 1
        except sqlite3.IntegrityError:
            print(f"  ⏭️  Skipping duplicate: {product.get('name')}")
    
    db.commit()
    print(f"\n💾 Stored {stored} new products in database")
    
    # Show database stats
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    print(f"📊 Total products in DB: {total}")


def test_deduplication(db):
    """Test deduplication across retailers"""
    cursor = db.cursor()
    
    print("\n🔍 Checking for duplicates across retailers...")
    
    # Find products with same brand and similar names
    cursor.execute('''
        SELECT brand, COUNT(*) as count, GROUP_CONCAT(retailer) as retailers,
               GROUP_CONCAT(name, ' | ') as names
        FROM products
        WHERE brand IS NOT NULL
        GROUP BY brand
        HAVING count > 1
    ''')
    
    duplicates = cursor.fetchall()
    if duplicates:
        print("\n📋 Potential duplicates found:")
        for brand, count, retailers, names in duplicates:
            print(f"\n  Brand: {brand} ({count} products)")
            print(f"  Retailers: {retailers}")
            print(f"  Products:")
            for name in names.split(' | '):
                print(f"    • {name}")


def main():
    """Run the test"""
    print("🚀 LabelSquor Real Crawl Test")
    print("=" * 50)
    
    # Setup database
    db = setup_test_db()
    
    # Load search terms from config
    import sys
    sys.path.append(str(Path(__file__).parent))
    from app.core.crawler_config import crawler_config
    
    config = crawler_config.load_search_terms()
    
    # Get top brands
    test_brands = config['priority_brands']['tier1'][:3]
    print(f"\n📋 Testing with brands: {test_brands}")
    
    all_products = []
    
    # Test each brand
    for brand in test_brands:
        print(f"\n{'='*50}")
        print(f"Testing: {brand}")
        print('='*50)
        
        # Try BigBasket
        products = run_spider_test(
            search_term=brand,
            retailer="bigbasket",
            max_items=3
        )
        
        if products:
            display_products(products)
            store_in_db(db, products)
            all_products.extend(products)
    
    # Test deduplication
    test_deduplication(db)
    
    print("\n✅ Test completed!")
    print(f"📊 Total products crawled: {len(all_products)}")
    print("\n💡 Next steps:")
    print("1. Add more retailers (Blinkit, Zepto)")
    print("2. Implement ML-based deduplication")
    print("3. Connect to Supabase")
    print("4. Build API endpoints")
    
    # Close database
    db.close()


if __name__ == "__main__":
    main()
