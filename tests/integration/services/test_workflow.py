"""
Test the complete LabelSquor workflow locally
- Fetch products from retailers
- Process and deduplicate
- Store in local SQLite database
"""
import asyncio
import sqlite3
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time

# Add project to path
import sys
sys.path.append(str(Path(__file__).parent))

from app.services.product_matcher_oss import OpenSourceProductMatcher, LightweightDeduplicator
from app.core.crawler_config import crawler_config


class LocalTestWorkflow:
    """Complete workflow test with local database"""
    
    def __init__(self):
        # In-memory SQLite database
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        
        # Create tables
        self._create_tables()
        
        # Initialize matcher
        print("🤖 Initializing ML models...")
        self.matcher = OpenSourceProductMatcher()
        self.deduplicator = LightweightDeduplicator()
        print("✅ Models loaded!")
        
    def _create_tables(self):
        """Create local database schema"""
        # Products table
        self.cursor.execute('''
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                brand TEXT,
                pack_size TEXT,
                category TEXT,
                min_price REAL,
                max_price REAL,
                mrp REAL,
                images TEXT,  -- JSON array
                ingredients_text TEXT,
                nutrition_text TEXT,
                retailers TEXT,  -- JSON array
                sources TEXT,  -- JSON array with URLs
                confidence_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hash TEXT UNIQUE
            )
        ''')
        
        # Raw crawled data
        self.cursor.execute('''
            CREATE TABLE crawled_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                retailer TEXT,
                url TEXT UNIQUE,
                name TEXT,
                brand TEXT,
                price REAL,
                pack_size TEXT,
                images TEXT,  -- JSON array
                raw_data TEXT,  -- Full JSON
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    async def run_test_crawl(self, search_terms=None, max_products=10):
        """Run a test crawl for specific search terms"""
        if not search_terms:
            # Get some terms from config
            config = crawler_config.load_search_terms()
            search_terms = config['priority_brands']['tier1'][:3]  # Top 3 brands
        
        print(f"\n🕷️  Starting test crawl for: {search_terms}")
        print("=" * 50)
        
        all_results = []
        
        for term in search_terms:
            print(f"\n🔍 Searching for: {term}")
            
            # Run crawler for each retailer
            for retailer in ['bigbasket', 'blinkit']:
                print(f"  → Crawling {retailer}...")
                
                results = await self._run_spider(
                    retailer=retailer,
                    search_term=term,
                    max_items=max_products
                )
                
                if results:
                    print(f"  ✅ Found {len(results)} products from {retailer}")
                    all_results.extend(results)
                else:
                    print(f"  ⚠️  No results from {retailer}")
        
        print(f"\n📊 Total products found: {len(all_results)}")
        
        # Process and store
        await self.process_crawled_data(all_results)
        
        return all_results
    
    async def _run_spider(self, retailer, search_term, max_items=5):
        """Run spider and collect results"""
        # For testing, we'll simulate results
        # In production, this would actually run Scrapy
        
        # Simulated product data based on search term
        if search_term.lower() == "maggi":
            if retailer == "bigbasket":
                return [
                    {
                        "retailer": "bigbasket",
                        "url": "https://bigbasket.com/pd/266109/maggi-masala/",
                        "name": "Maggi 2-Minute Masala Instant Noodles",
                        "brand": "Nestle",
                        "price": 14.00,
                        "mrp": 15.00,
                        "pack_size": "70 g",
                        "images": [
                            "https://bigbasket.com/images/maggi1.jpg",
                            "https://bigbasket.com/images/maggi2.jpg"
                        ],
                        "ingredients_text": "Wheat Flour, Edible Vegetable Oil, Salt, Spices...",
                        "category": "Instant Foods/Noodles"
                    },
                    {
                        "retailer": "bigbasket",
                        "url": "https://bigbasket.com/pd/266110/maggi-veg-atta/",
                        "name": "Maggi Veg Atta Noodles - Masala",
                        "brand": "Nestle",
                        "price": 28.00,
                        "mrp": 30.00,
                        "pack_size": "80 g",
                        "images": ["https://bigbasket.com/images/maggi-atta.jpg"],
                        "category": "Instant Foods/Noodles"
                    }
                ]
            else:  # blinkit
                return [
                    {
                        "retailer": "blinkit",
                        "url": "https://blinkit.com/p/maggi-masala/",
                        "name": "Maggi Masala 2 Minute Noodles",
                        "brand": "Nestle",
                        "price": 13.50,
                        "mrp": 15.00,
                        "pack_size": "70g",
                        "images": ["https://blinkit.com/images/maggi.jpg"],
                        "ingredients_text": "Wheat Flour (Atta), Palm Oil, Salt...",
                        "nutrition_text": "Energy: 313 kcal, Protein: 7.2g...",
                        "category": "Instant Noodles"
                    }
                ]
        
        elif search_term.lower() == "lays":
            if retailer == "bigbasket":
                return [
                    {
                        "retailer": "bigbasket",
                        "url": "https://bigbasket.com/pd/123456/lays-magic-masala/",
                        "name": "Lay's India's Magic Masala Potato Chips",
                        "brand": "Lays",
                        "price": 20.00,
                        "mrp": 20.00,
                        "pack_size": "52g",
                        "images": ["https://bigbasket.com/images/lays-masala.jpg"],
                        "category": "Snacks/Chips"
                    }
                ]
        
        return []
    
    async def process_crawled_data(self, products):
        """Process and deduplicate crawled products"""
        print("\n🔄 Processing crawled data...")
        print("-" * 50)
        
        # Step 1: Store raw crawled data
        for product in products:
            self._store_crawled_product(product)
        
        # Step 2: Find duplicate groups
        print("\n🔍 Finding duplicates...")
        duplicate_groups = self.matcher.match_products_batch(products, threshold=0.80)
        
        print(f"  → Found {len(duplicate_groups)} unique product groups")
        
        # Step 3: Consolidate each group
        consolidated_count = 0
        for group_indices in duplicate_groups:
            group = [products[i] for i in group_indices]
            
            if len(group) > 1:
                print(f"\n  📦 Consolidating {len(group)} variants:")
                for p in group:
                    print(f"     • {p['retailer']}: {p['name']} ({p['pack_size']})")
                
                # Consolidate
                consolidated = self._consolidate_products(group)
                
                # Store consolidated product
                if self._store_product(consolidated):
                    consolidated_count += 1
                    print(f"  ✅ Stored as: {consolidated['name']}")
            else:
                # Single product
                product = group[0]
                if self._store_product(product):
                    consolidated_count += 1
        
        print(f"\n✅ Stored {consolidated_count} unique products")
        
        # Show database contents
        self._show_database_summary()
    
    def _store_crawled_product(self, product):
        """Store raw crawled data"""
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO crawled_products 
                (retailer, url, name, brand, price, pack_size, images, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product['retailer'],
                product['url'],
                product['name'],
                product.get('brand'),
                product.get('price'),
                product.get('pack_size'),
                json.dumps(product.get('images', [])),
                json.dumps(product)
            ))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # URL already exists
    
    def _consolidate_products(self, group):
        """Consolidate multiple product variants"""
        # Start with first product as base
        consolidated = {
            'name': group[0]['name'],
            'brand': group[0]['brand'],
            'pack_size': group[0]['pack_size'],
            'category': group[0].get('category'),
            'retailers': [],
            'images': [],
            'sources': [],
            'min_price': float('inf'),
            'max_price': 0,
            'mrp': None,
            'confidence_score': 0.9
        }
        
        # Merge data from all sources
        all_ingredients = []
        all_nutrition = []
        
        for product in group:
            # Retailers
            consolidated['retailers'].append(product['retailer'])
            
            # Sources
            consolidated['sources'].append({
                'retailer': product['retailer'],
                'url': product['url'],
                'price': product.get('price')
            })
            
            # Images
            images = product.get('images', [])
            consolidated['images'].extend(images)
            
            # Prices
            if price := product.get('price'):
                consolidated['min_price'] = min(consolidated['min_price'], price)
                consolidated['max_price'] = max(consolidated['max_price'], price)
            
            if mrp := product.get('mrp'):
                consolidated['mrp'] = mrp
            
            # Text fields
            if ing := product.get('ingredients_text'):
                all_ingredients.append(ing)
            if nut := product.get('nutrition_text'):
                all_nutrition.append(nut)
        
        # Remove duplicate images
        consolidated['images'] = list(dict.fromkeys(consolidated['images']))
        
        # Pick best text (longest)
        if all_ingredients:
            consolidated['ingredients_text'] = max(all_ingredients, key=len)
        if all_nutrition:
            consolidated['nutrition_text'] = max(all_nutrition, key=len)
        
        # Create hash for deduplication
        consolidated['hash'] = self.deduplicator.create_product_hash(consolidated)
        
        return consolidated
    
    def _store_product(self, product):
        """Store consolidated product"""
        # Handle both consolidated and single products
        if isinstance(product.get('retailers'), list):
            # Consolidated product
            retailers = json.dumps(product['retailers'])
            sources = json.dumps(product.get('sources', []))
            images = json.dumps(product.get('images', []))
            min_price = product.get('min_price')
            max_price = product.get('max_price')
        else:
            # Single product
            retailers = json.dumps([product['retailer']])
            sources = json.dumps([{
                'retailer': product['retailer'],
                'url': product['url'],
                'price': product.get('price')
            }])
            images = json.dumps(product.get('images', []))
            min_price = product.get('price')
            max_price = product.get('price')
        
        # Create hash if not present
        if 'hash' not in product:
            product['hash'] = self.deduplicator.create_product_hash(product)
        
        try:
            self.cursor.execute('''
                INSERT INTO products 
                (name, brand, pack_size, category, min_price, max_price, mrp,
                 images, ingredients_text, nutrition_text, retailers, sources,
                 confidence_score, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product['name'],
                product.get('brand'),
                product.get('pack_size'),
                product.get('category'),
                min_price,
                max_price,
                product.get('mrp'),
                images,
                product.get('ingredients_text'),
                product.get('nutrition_text'),
                retailers,
                sources,
                product.get('confidence_score', 0.8),
                product['hash']
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            print(f"  ⏭️  Product already exists: {product['name']}")
            return False
    
    def _show_database_summary(self):
        """Show what's in the database"""
        print("\n📊 Database Summary")
        print("=" * 50)
        
        # Total products
        self.cursor.execute("SELECT COUNT(*) FROM products")
        total_products = self.cursor.fetchone()[0]
        print(f"Total unique products: {total_products}")
        
        # Products by brand
        print("\nProducts by brand:")
        self.cursor.execute('''
            SELECT brand, COUNT(*) as count 
            FROM products 
            GROUP BY brand 
            ORDER BY count DESC
        ''')
        for brand, count in self.cursor.fetchall():
            print(f"  • {brand}: {count} products")
        
        # Price ranges
        print("\nPrice insights:")
        self.cursor.execute('''
            SELECT name, min_price, max_price, 
                   json_array_length(retailers) as retailer_count
            FROM products
            WHERE min_price != max_price
        ''')
        for name, min_price, max_price, retailer_count in self.cursor.fetchall():
            savings = max_price - min_price
            print(f"  • {name}: ₹{min_price}-{max_price} ({retailer_count} retailers, save ₹{savings})")
        
        # Show sample product
        print("\n📦 Sample Product Details:")
        self.cursor.execute('''
            SELECT name, brand, pack_size, min_price, max_price,
                   images, retailers, ingredients_text
            FROM products
            WHERE json_array_length(retailers) > 1
            LIMIT 1
        ''')
        
        row = self.cursor.fetchone()
        if row:
            name, brand, size, min_p, max_p, images, retailers, ingredients = row
            print(f"  Name: {name}")
            print(f"  Brand: {brand}")
            print(f"  Size: {size}")
            print(f"  Price: ₹{min_p} - ₹{max_p}")
            print(f"  Images: {len(json.loads(images))} images")
            print(f"  Available on: {', '.join(json.loads(retailers))}")
            if ingredients:
                print(f"  Ingredients: {ingredients[:50]}...")


async def main():
    """Run the test workflow"""
    print("🚀 LabelSquor Test Workflow")
    print("=" * 50)
    
    # Initialize
    workflow = LocalTestWorkflow()
    
    # Test with specific products
    test_terms = ["maggi", "lays", "amul"]  # From search_terms.yaml
    
    # Run crawl
    results = await workflow.run_test_crawl(
        search_terms=test_terms,
        max_products=5
    )
    
    print("\n✨ Test completed!")
    print("\nNext steps:")
    print("1. Connect to Supabase for persistent storage")
    print("2. Run actual Scrapy spiders (not simulated)")
    print("3. Add more retailers (Zepto, Amazon)")
    print("4. Enable real-time crawling")


if __name__ == "__main__":
    asyncio.run(main())
