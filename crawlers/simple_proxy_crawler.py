#!/usr/bin/env python3
"""
Simple proxy-enabled crawler that returns results directly
"""
import httpx
import json
import random
import asyncio
import re
from typing import List, Dict, Any

# Free proxy sources
PROXY_SOURCES = [
    'https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&limit=20',
    'https://www.proxy-list.download/api/v1/get?type=http',
]

# User agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
]


async def get_proxies() -> List[str]:
    """Fetch fresh proxy list"""
    proxies = []
    
    async with httpx.AsyncClient() as client:
        for url in PROXY_SOURCES:
            try:
                response = await client.get(url, timeout=10)
                if response.status_code == 200:
                    content = response.text.strip()
                    # Parse proxy list
                    for line in content.split('\n')[:20]:
                        line = line.strip()
                        if ':' in line and not line.startswith('#'):
                            proxies.append(f"http://{line}")
            except:
                pass
    
    print(f"📋 Loaded {len(proxies)} proxies")
    return proxies


async def search_bigbasket_with_proxy(search_term: str, max_products: int = 10) -> List[Dict[str, Any]]:
    """Search BigBasket using proxies"""
    import os
    import re
    
    products = []
    
    # Check if we're in GCP environment
    is_gcp = os.environ.get("K_SERVICE") or os.environ.get("GAE_ENV") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    
    if not is_gcp:
        # Try direct connection first when not on GCP
        print("🔍 Trying direct connection (local environment)")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.bigbasket.com/",
                }
                
                search_url = f"https://www.bigbasket.com/ps/?q={search_term}"
                response = await client.get(search_url, headers=headers)
                
                if response.status_code == 200:
                    # Extract Next.js data from HTML
                    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
                    if match:
                        data = json.loads(match.group(1))
                        print(f"✅ Direct connection successful")
                        
                        # Navigate to products
                        tabs = data.get('props', {}).get('pageProps', {}).get('SSRData', {}).get('tabs', [])
                        
                        for tab in tabs:
                            tab_products = tab.get('product_info', {}).get('products', [])
                            
                            for product in tab_products[:max_products]:
                                # Extract pricing
                                pricing = product.get('pricing', {}).get('discount', {})
                                sp = pricing.get('sp', product.get('sp', 0))
                                mrp = pricing.get('mrp', product.get('mrp', 0))
                                
                                # Extract brand name
                                brand = product.get('p_brand', product.get('brand', {}))
                                if isinstance(brand, dict):
                                    brand_name = brand.get('name', 'Unknown')
                                else:
                                    brand_name = str(brand) if brand else 'Unknown'
                                
                                products.append({
                                    "name": product.get('p_desc', product.get('desc', 'Unknown')),
                                    "brand": brand_name,
                                    "price": f"₹{sp}",
                                    "mrp": f"₹{mrp}",
                                    "image": product.get('p_imageURL', product.get('images', [{}])[0].get('s', '') if product.get('images') else ''),
                                    "url": f"https://www.bigbasket.com{product.get('absolute_url', '')}",
                                    "retailer": "bigbasket"
                                })
                                
                            if products:
                                return products[:max_products]
                elif response.status_code == 403:
                    print("❌ Direct connection blocked, trying proxies...")
                    
        except Exception as e:
            print(f"❌ Direct connection failed: {str(e)[:50]}")
    
    # If direct fails or we're on GCP, use proxies
    proxies = await get_proxies()
    
    if not proxies:
        print("❌ No proxies available")
        return []
    
    # BigBasket search URL
    search_url = f"https://www.bigbasket.com/ps/?q={search_term}"
    
    # Try different proxies
    for proxy in random.sample(proxies, min(5, len(proxies))):
        try:
            print(f"🔄 Trying proxy: {proxy}")
            
            # Create client with proxy
            transport = httpx.AsyncHTTPTransport(proxy=proxy)
            async with httpx.AsyncClient(transport=transport, timeout=15) as client:
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.bigbasket.com/",
                }
                
                response = await client.get(search_url, headers=headers)
                
                if response.status_code == 200:
                    # Extract Next.js data from HTML
                    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
                    if match:
                        data = json.loads(match.group(1))
                        print(f"✅ Success with proxy {proxy}")
                        
                        # Navigate to products
                        tabs = data.get('props', {}).get('pageProps', {}).get('SSRData', {}).get('tabs', [])
                        
                        for tab in tabs:
                            tab_products = tab.get('product_info', {}).get('products', [])
                            
                            for product in tab_products[:max_products]:
                                # Extract pricing
                                pricing = product.get('pricing', {}).get('discount', {})
                                sp = pricing.get('sp', product.get('sp', 0))
                                mrp = pricing.get('mrp', product.get('mrp', 0))
                                
                                # Extract brand name
                                brand = product.get('p_brand', product.get('brand', {}))
                                if isinstance(brand, dict):
                                    brand_name = brand.get('name', 'Unknown')
                                else:
                                    brand_name = str(brand) if brand else 'Unknown'
                                
                                products.append({
                                    "name": product.get('p_desc', product.get('desc', 'Unknown')),
                                    "brand": brand_name,
                                    "price": f"₹{sp}",
                                    "mrp": f"₹{mrp}",
                                    "image": product.get('p_imageURL', product.get('images', [{}])[0].get('s', '') if product.get('images') else ''),
                                    "url": f"https://www.bigbasket.com{product.get('absolute_url', '')}",
                                    "retailer": "bigbasket"
                                })
                                
                            if products:
                                return products[:max_products]
                
                elif response.status_code == 403:
                    print(f"❌ Proxy blocked: {proxy}")
                    continue
                    
        except Exception as e:
            print(f"❌ Proxy failed {proxy}: {str(e)[:50]}")
            continue
    
    return products


async def crawl_bigbasket(search_terms: List[str], max_products: int) -> Dict[str, Any]:
    """Main crawler function"""
    all_products = []
    products_per_term = max(1, max_products // len(search_terms))
    
    for term in search_terms:
        print(f"\n🔍 Searching for: {term}")
        products = await search_bigbasket_with_proxy(term, products_per_term)
        all_products.extend(products)
        print(f"   Found {len(products)} products")
    
    return {
        "products_found": len(all_products),
        "products": all_products[:max_products],
        "success": len(all_products) > 0
    }


if __name__ == "__main__":
    # Test the crawler
    import sys
    
    if len(sys.argv) > 1:
        search_terms = sys.argv[1].split(',')
        max_products = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    else:
        search_terms = ["maggi", "lays"]
        max_products = 10
    
    print("🕷️ Simple Proxy Crawler")
    print(f"Search terms: {search_terms}")
    print(f"Max products: {max_products}")
    
    result = asyncio.run(crawl_bigbasket(search_terms, max_products))
    
    print(f"\n✅ Total products found: {result['products_found']}")
    print(json.dumps(result, indent=2))
