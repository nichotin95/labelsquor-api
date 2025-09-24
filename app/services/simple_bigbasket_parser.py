#!/usr/bin/env python3
"""
Simple BigBasket parser - no Playwright needed!
BigBasket returns product data as JSON in the HTML
"""

import httpx
import json
import re
import os
from typing import List, Dict, Any


class SimpleBigBasketParser:
    """Parse BigBasket search results from embedded JSON"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        # ScrapingDog API configuration
        self.scrapingdog_api_key = os.getenv('SCRAPINGDOG_API_KEY', '68d3f5896e702d62b1475720')
        self.scrapingdog_url = 'https://api.scrapingdog.com/scrape'
    
    def search_products(self, query: str) -> List[Dict[str, Any]]:
        """Search for products and extract data"""
        url = f"https://www.bigbasket.com/ps/?q={query}"
        
        print(f"🔍 Searching BigBasket for: {query}")
        
        # Use ScrapingDog API to bypass anti-scraping measures
        params = {
            'api_key': self.scrapingdog_api_key,
            'url': url,
            'render': 'false'  # We don't need JS rendering for BigBasket
        }
        
        try:
            response = httpx.get(self.scrapingdog_url, params=params, timeout=60.0)
        except httpx.TimeoutException:
            print(f"❌ Request timed out - ScrapingDog may be slow or API key invalid")
            return []
        except Exception as e:
            print(f"❌ Error calling ScrapingDog API: {str(e)}")
            return []
        
        if response.status_code != 200:
            print(f"❌ Failed with status: {response.status_code}")
            if response.status_code == 403:
                print(f"❌ ScrapingDog API key may be invalid or quota exceeded")
            return []
        
        # Extract Next.js data
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        if not match:
            print("❌ No Next.js data found")
            return []
        
        try:
            data = json.loads(match.group(1))
            products = []
            
            # Navigate to products
            tabs = data.get('props', {}).get('pageProps', {}).get('SSRData', {}).get('tabs', [])
            
            for tab in tabs:
                tab_products = tab.get('product_info', {}).get('products', [])
                
                for product in tab_products:
                    # Extract clean product data
                    cleaned = {
                        'id': product.get('id'),
                        'name': product.get('p_desc', product.get('desc', '')),
                        'brand': product.get('p_brand', product.get('brand', '')),
                        'category': tab.get('slug', ''),
                        'url': f"https://www.bigbasket.com{product.get('absolute_url', '')}",
                        
                        # Pricing - handle string prices
                        'price': self._parse_price(product.get('pricing', {}).get('discount', {}).get('sp', product.get('sp', '0'))),
                        'mrp': self._parse_price(product.get('pricing', {}).get('discount', {}).get('mrp', product.get('mrp', '0'))),
                        'discount': product.get('pricing', {}).get('discount', {}).get('d', 0),
                        
                        # Images
                        'images': self._extract_images(product),
                        
                        # Additional info
                        'pack_size': product.get('w', ''),
                        'pack_desc': product.get('pack_desc', ''),
                        'in_stock': product.get('availability', {}).get('avail_status') == '001',
                        'rating': product.get('rating_info', {}).get('avg_rating', 0),
                        'review_count': product.get('rating_info', {}).get('rating_count', 0),
                        
                        # USP might have ingredient hints
                        'usp': product.get('usp', ''),
                        
                        # Raw data for further processing
                        'raw_data': product
                    }
                    
                    products.append(cleaned)
                    print(f"✅ Found: {cleaned['name']} - ₹{cleaned['price']}")
            
            print(f"\n📦 Total products found: {len(products)}")
            return products
            
        except Exception as e:
            print(f"❌ Error parsing data: {e}")
            return []
    
    def _parse_price(self, price_value) -> float:
        """Parse price from string or number"""
        if isinstance(price_value, (int, float)):
            return float(price_value)
        if isinstance(price_value, str):
            # Remove currency symbols and convert
            price_str = price_value.replace('₹', '').replace(',', '').strip()
            try:
                return float(price_str)
            except:
                return 0.0
        return 0.0
    
    def _extract_images(self, product: Dict) -> List[str]:
        """Extract all product images"""
        images = []
        
        # Main image
        if product.get('primary_image'):
            images.append(product['primary_image'])
        
        # Image array
        if product.get('images'):
            for img in product['images']:
                if isinstance(img, dict):
                    # Different resolution keys
                    for res in ['l', 'm', 's', 'xl']:
                        if img.get(res):
                            images.append(img[res])
                            break
                elif isinstance(img, str):
                    images.append(img)
        
        # Image paths from different resolutions
        for key in ['img_s', 'img_m', 'img_l', 'img_xl']:
            if product.get(key):
                images.append(product[key])
        
        # Tab images
        if product.get('tabs', {}).get('images'):
            for tab_img in product['tabs']['images']:
                if isinstance(tab_img, str):
                    images.append(tab_img)
        
        # Clean URLs - fix double domain issue
        cleaned_images = []
        for img in images:
            if img and isinstance(img, str):
                # Remove double domain
                img = img.replace('https://www.bbassets.com/mod_images/bb_images/https://www.bbassets.com', 'https://www.bbassets.com')
                # Ensure proper URL
                if not img.startswith('http'):
                    img = f"https://www.bbassets.com/{img.lstrip('/')}"
                cleaned_images.append(img)
        
        return list(dict.fromkeys(cleaned_images))  # Remove duplicates while preserving order
    
    def get_product_details(self, product_url: str) -> Dict[str, Any]:
        """Get detailed product info from product page"""
        print(f"\n📄 Fetching product details from: {product_url}")
        
        # Use ScrapingDog API for product details
        params = {
            'api_key': self.scrapingdog_api_key,
            'url': product_url,
            'render': 'false'
        }
        
        try:
            response = httpx.get(self.scrapingdog_url, params=params, timeout=60.0)
        except httpx.TimeoutException:
            print(f"❌ Request timed out - ScrapingDog may be slow")
            return {}
        except Exception as e:
            print(f"❌ Error calling ScrapingDog API: {str(e)}")
            return {}
            
        if response.status_code != 200:
            print(f"❌ Failed to fetch product details: {response.status_code}")
            return {}
        
        # Extract Next.js data from product page
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        if not match:
            return {}
        
        try:
            data = json.loads(match.group(1))
            product_data = data.get('props', {}).get('pageProps', {}).get('productDetails', {})
            
            # Product pages have more detailed info
            return {
                'description': product_data.get('long_desc', ''),
                'ingredients': product_data.get('variable_weight', {}).get('ingredient_text', ''),
                'nutrition': product_data.get('variable_weight', {}).get('nutrition_text', ''),
                'manufacturer': product_data.get('manufacturer', ''),
                'country_of_origin': product_data.get('country_of_origin', ''),
                'shelf_life': product_data.get('shelf_life', ''),
                'all_images': self._extract_images(product_data),
            }
        except:
            return {}


# Demo usage
if __name__ == "__main__":
    parser = SimpleBigBasketParser()
    
    # Search for maggi
    products = parser.search_products("maggi")
    
    # Save results
    with open('maggi_products.json', 'w') as f:
        json.dump(products, f, indent=2)
    
    print(f"\n💾 Results saved to maggi_products.json")
    
    # Get details for first product
    if products:
        details = parser.get_product_details(products[0]['url'])
        if details:
            print(f"\nDetailed info for {products[0]['name']}:")
            for key, value in details.items():
                if value:
                    print(f"  {key}: {str(value)[:100]}...")
