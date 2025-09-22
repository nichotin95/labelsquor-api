"""
Demo: How Product Deduplication Works
Shows the complete flow from crawling to consolidated storage
"""
import asyncio
from typing import List, Dict, Any

# Simulated product data from different retailers
CRAWLED_PRODUCTS = [
    # Same product (Maggi) from 3 retailers
    {
        "retailer": "bigbasket",
        "url": "https://bigbasket.com/pd/266109/maggi-masala-noodles/",
        "name": "Maggi 2-Minute Masala Instant Noodles",
        "brand": "Nestle",
        "price": 14.00,
        "mrp": 15.00,
        "pack_size": "70 g",
        "images": ["maggi1.jpg", "maggi2.jpg"],
        "ingredients_text": "Wheat Flour, Edible Vegetable Oil, Salt, Spices..."
    },
    {
        "retailer": "blinkit",
        "url": "https://blinkit.com/p/maggi-noodles-masala/",
        "name": "Maggi Masala 2 Minute Noodles",
        "brand": "Nestle",
        "price": 13.50,
        "mrp": 15.00,
        "pack_size": "70g",
        "images": ["maggi-blinkit.jpg"],
        "ingredients_text": "Wheat Flour (Atta), Palm Oil, Salt, Spices & Condiments..."
    },
    {
        "retailer": "zepto",
        "url": "https://zepto.com/product/maggi-2min-masala",
        "name": "Maggi 2 Min Masala Noodles",
        "brand": "Nestle",
        "price": 14.50,
        "mrp": 15.00,
        "pack_size": "70 gm",
        "images": ["maggi_z1.jpg", "maggi_z2.jpg", "maggi_z3.jpg"],
        "nutrition_text": "Energy: 313 kcal, Protein: 7.2g, Carbs: 45g..."
    },
    # Different product (Lays)
    {
        "retailer": "bigbasket",
        "url": "https://bigbasket.com/pd/123456/lays-magic-masala/",
        "name": "Lay's India's Magic Masala Potato Chips",
        "brand": "Lays",
        "price": 20.00,
        "pack_size": "52g",
        "images": ["lays1.jpg"]
    }
]


class ProductDeduplicationDemo:
    """Demonstrates the complete deduplication flow"""
    
    def __init__(self):
        # Initialize the matcher
        from app.services.product_matcher_oss import OpenSourceProductMatcher
        self.matcher = OpenSourceProductMatcher()
        
        # Simulated database
        self.database = []
    
    async def process_crawled_products(self, products: List[Dict[str, Any]]):
        """Main processing flow"""
        print("🕷️  STEP 1: Products discovered from retailers")
        print("-" * 50)
        for p in products:
            print(f"  • {p['retailer']}: {p['name']} ({p['pack_size']})")
        
        print("\n🔍 STEP 2: Checking for duplicates")
        print("-" * 50)
        
        # Group products by potential matches
        product_groups = self.find_duplicate_groups(products)
        
        print(f"  Found {len(product_groups)} unique products")
        
        print("\n🤖 STEP 3: Consolidating product data")
        print("-" * 50)
        
        consolidated_products = []
        for group in product_groups:
            if len(group) > 1:
                print(f"\n  Merging {len(group)} sources:")
                for p in group:
                    print(f"    - {p['retailer']}: {p['name']}")
                
                # Consolidate data from multiple sources
                consolidated = self.consolidate_group(group)
                consolidated_products.append(consolidated)
                
                print(f"  ✅ Consolidated as: {consolidated['name']}")
                print(f"     Price range: ₹{consolidated['min_price']} - ₹{consolidated['max_price']}")
                print(f"     Total images: {len(consolidated['images'])}")
                print(f"     Has ingredients: {'✓' if consolidated.get('ingredients_text') else '✗'}")
                print(f"     Has nutrition: {'✓' if consolidated.get('nutrition_text') else '✗'}")
            else:
                # Single source
                consolidated_products.append(group[0])
                print(f"\n  Single source: {group[0]['name']}")
        
        print("\n💾 STEP 4: Storing in database")
        print("-" * 50)
        
        for product in consolidated_products:
            # Check if already exists
            existing = self.find_in_database(product)
            
            if existing:
                print(f"  ⏭️  Skipping (already exists): {product['name']}")
            else:
                self.database.append(product)
                print(f"  ✅ Stored: {product['name']}")
        
        print(f"\n📊 Final database: {len(self.database)} products")
    
    def find_duplicate_groups(self, products: List[Dict[str, Any]]) -> List[List[Dict]]:
        """Group duplicate products together"""
        # Use the matcher to find groups
        indices = self.matcher.match_products_batch(products, threshold=0.85)
        
        # Convert indices to actual products
        groups = []
        for index_group in indices:
            group = [products[i] for i in index_group]
            groups.append(group)
        
        return groups
    
    def consolidate_group(self, group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate multiple sources into one"""
        # Base from first product
        consolidated = {
            'name': group[0]['name'],
            'brand': group[0]['brand'],
            'pack_size': group[0]['pack_size'],
            'retailers': [],
            'images': [],
            'min_price': float('inf'),
            'max_price': 0,
            'mrp': group[0].get('mrp'),
            'sources': []
        }
        
        # Merge data from all sources
        for product in group:
            # Track retailers
            consolidated['retailers'].append(product['retailer'])
            
            # Collect all images
            if 'images' in product:
                consolidated['images'].extend(product['images'])
            
            # Price range
            if price := product.get('price'):
                consolidated['min_price'] = min(consolidated['min_price'], price)
                consolidated['max_price'] = max(consolidated['max_price'], price)
            
            # Merge text fields (keep longest)
            for field in ['ingredients_text', 'nutrition_text', 'description']:
                if value := product.get(field):
                    existing = consolidated.get(field, '')
                    if len(value) > len(existing):
                        consolidated[field] = value
            
            # Keep source URLs
            consolidated['sources'].append({
                'retailer': product['retailer'],
                'url': product['url'],
                'price': product.get('price')
            })
        
        # Remove duplicate images
        consolidated['images'] = list(set(consolidated['images']))
        
        # Use AI to pick best name (simulation)
        # In real implementation, this would use the quality ranker
        name_options = [p['name'] for p in group]
        consolidated['name'] = max(name_options, key=len)  # Pick most detailed
        
        return consolidated
    
    def find_in_database(self, product: Dict[str, Any]) -> bool:
        """Check if product already exists"""
        for existing in self.database:
            # Simple check - in real implementation would use matcher
            if (existing['brand'] == product['brand'] and 
                existing['pack_size'] == product['pack_size']):
                # Check name similarity
                existing_words = set(existing['name'].lower().split())
                new_words = set(product['name'].lower().split())
                overlap = len(existing_words & new_words) / len(existing_words | new_words)
                
                if overlap > 0.7:
                    return True
        
        return False


async def main():
    """Run the demo"""
    print("🚀 LabelSquor Product Deduplication Demo")
    print("=" * 50)
    
    demo = ProductDeduplicationDemo()
    await demo.process_crawled_products(CRAWLED_PRODUCTS)
    
    print("\n✨ Benefits of this approach:")
    print("  • No duplicate Maggi entries (merged 3 → 1)")
    print("  • Combined data from all retailers")
    print("  • Best price visibility (₹13.50 - ₹14.50)")
    print("  • Complete information (ingredients + nutrition)")
    print("  • All images collected (6 total)")
    print("  • Zero API costs (using open-source models)")


if __name__ == "__main__":
    asyncio.run(main())
