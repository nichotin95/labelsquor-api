#!/usr/bin/env python3
"""
Easy runner for crawlers with anti-blocking measures
Automatically detects environment and applies appropriate settings
"""
import os
import sys
import subprocess
import argparse
import json
from typing import List, Optional


def detect_environment() -> str:
    """Detect if running on GCP, GitHub Actions, or local"""
    # GitHub Actions
    if os.environ.get('GITHUB_ACTIONS'):
        return 'github'
    
    # Google Cloud
    if os.path.exists('/sys/class/dmi/id/product_name'):
        try:
            with open('/sys/class/dmi/id/product_name', 'r') as f:
                if 'Google' in f.read():
                    return 'gcp'
        except:
            pass
    
    # Check for GCP metadata server
    try:
        import requests
        response = requests.get(
            'http://metadata.google.internal',
            timeout=1,
            headers={'Metadata-Flavor': 'Google'}
        )
        if response.status_code == 200:
            return 'gcp'
    except:
        pass
    
    return 'local'


def get_scrapy_settings(environment: str, retailer: str) -> List[str]:
    """Get appropriate Scrapy settings for environment"""
    settings = []
    
    if environment == 'gcp':
        # Use GCP-specific settings with proxy
        settings.extend([
            '-s', 'SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings_gcp',
            '-s', 'LOG_LEVEL=INFO',
        ])
        print("🌐 Running on GCP - enabling proxy rotation")
    
    elif environment == 'github':
        # GitHub Actions - no proxy needed
        settings.extend([
            '-s', 'DOWNLOAD_DELAY=1',
            '-s', 'LOG_LEVEL=INFO',
        ])
        print("🐙 Running on GitHub Actions - using GitHub IPs")
    
    else:
        # Local development
        settings.extend([
            '-s', 'DOWNLOAD_DELAY=0.5',
            '-s', 'LOG_LEVEL=DEBUG',
        ])
        print("💻 Running locally - minimal restrictions")
    
    return settings


def run_simple_parser(retailer: str, search_terms: List[str], max_products: int):
    """Run the simple parser (no Scrapy) for supported retailers"""
    if retailer == 'bigbasket':
        print("🛒 Using simple BigBasket parser (recommended for cloud)")
        
        cmd = f"""
from simple_bigbasket_parser import SimpleBigBasketParser
import json

parser = SimpleBigBasketParser()
all_products = []
search_terms = {search_terms}

for term in search_terms:
    print(f"Searching for: {{term}}")
    products = parser.search_products(term.strip())
    all_products.extend(products[:{max_products//len(search_terms)}])

# Save results
with open('{retailer}_results.json', 'w') as f:
    json.dump(all_products, f, indent=2)

print(f"✅ Crawled {{len(all_products)}} products")
print(f"💾 Results saved to {retailer}_results.json")
"""
        
        subprocess.run([sys.executable, '-c', cmd])
        return True
    
    return False


def run_scrapy_spider(retailer: str, search_terms: List[str], max_products: int, environment: str):
    """Run Scrapy spider with appropriate settings"""
    spider_map = {
        'bigbasket': 'bigbasket',
        'amazon': 'amazon_in',
        'flipkart': 'flipkart',
        'blinkit': 'blinkit',
        'zepto': 'zepto',
    }
    
    spider_name = spider_map.get(retailer)
    if not spider_name:
        print(f"❌ Unknown retailer: {retailer}")
        return
    
    # Build command
    cmd = ['scrapy', 'crawl', spider_name]
    
    # Add environment-specific settings
    settings = get_scrapy_settings(environment, retailer)
    cmd.extend(settings)
    
    # Add spider arguments
    cmd.extend([
        '-a', f'search_terms={",".join(search_terms)}',
        '-a', f'max_products={max_products}',
    ])
    
    print(f"🕷️  Running Scrapy spider: {spider_name}")
    print(f"📝 Command: {' '.join(cmd)}")
    
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        description='Run LabelSquor crawlers with anti-blocking measures'
    )
    
    parser.add_argument(
        'retailer',
        choices=['bigbasket', 'amazon', 'flipkart', 'blinkit', 'zepto', 'all'],
        help='Retailer to crawl'
    )
    
    parser.add_argument(
        '--search-terms',
        default='maggi,lays,amul,britannia',
        help='Comma-separated search terms'
    )
    
    parser.add_argument(
        '--max-products',
        type=int,
        default=100,
        help='Maximum products to crawl'
    )
    
    parser.add_argument(
        '--force-scrapy',
        action='store_true',
        help='Force using Scrapy instead of simple parser'
    )
    
    parser.add_argument(
        '--environment',
        choices=['local', 'gcp', 'github'],
        help='Override environment detection'
    )
    
    args = parser.parse_args()
    
    # Detect environment
    environment = args.environment or detect_environment()
    print(f"🔍 Detected environment: {environment}")
    
    # Parse search terms
    search_terms = [term.strip() for term in args.search_terms.split(',')]
    
    # Try simple parser first (for supported retailers)
    if not args.force_scrapy:
        if run_simple_parser(args.retailer, search_terms, args.max_products):
            return
    
    # Fall back to Scrapy
    if args.retailer == 'all':
        # Run all retailers
        for retailer in ['bigbasket', 'amazon', 'flipkart', 'blinkit', 'zepto']:
            print(f"\n{'='*50}")
            print(f"Crawling {retailer.upper()}")
            print(f"{'='*50}\n")
            
            if not args.force_scrapy:
                if run_simple_parser(retailer, search_terms, args.max_products):
                    continue
            
            run_scrapy_spider(retailer, search_terms, args.max_products, environment)
    else:
        # Run specific retailer
        run_scrapy_spider(args.retailer, search_terms, args.max_products, environment)


if __name__ == '__main__':
    main()
