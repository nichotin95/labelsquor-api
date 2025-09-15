"""
BigBasket Product Discovery Spider
Multiple strategies to find product URLs
"""
import scrapy
import json
from urllib.parse import urlencode
from typing import Iterator


class BigBasketDiscoverySpider(scrapy.Spider):
    name = 'bigbasket_discovery'
    allowed_domains = ['bigbasket.com', 'www.bigbasket.com']
    
    def start_requests(self):
        """Use multiple strategies to discover products"""
        
        # Strategy 1: Sitemap
        yield scrapy.Request(
            'https://www.bigbasket.com/sitemap.xml',
            callback=self.parse_sitemap,
            meta={'strategy': 'sitemap'}
        )
        
        # Strategy 2: Search API (discovered through network inspection)
        search_terms = [
            'maggi', 'lays', 'kurkure', 'coca cola', 'pepsi',
            'amul', 'britannia', 'parle', 'haldiram', 'nestle',
            'cadbury', 'oreo', 'horlicks', 'bournvita', 'complan'
        ]
        
        for term in search_terms:
            # BigBasket's internal search API
            search_url = f'https://www.bigbasket.com/custompage/getsearchdata/?slug={term}&type=ps'
            yield scrapy.Request(
                search_url,
                callback=self.parse_search_api,
                meta={'search_term': term, 'strategy': 'search_api'}
            )
        
        # Strategy 3: Category pages with pagination
        categories = [
            ('snacks-branded-foods', 'chips-crisps'),
            ('beverages', 'soft-drinks'),
            ('dairy', 'milk'),
            ('snacks-branded-foods', 'biscuits-cookies'),
            ('bakery-cakes-dairy', 'breads-buns'),
            ('staples', 'atta-flours'),
            ('snacks-branded-foods', 'chocolates-candies'),
            ('staples', 'rice-rice-products'),
            ('dairy', 'paneer-tofu'),
            ('snacks-branded-foods', 'noodles-pasta-vermicelli'),
        ]
        
        for main_cat, sub_cat in categories:
            # Category URLs with page parameter
            for page in range(1, 6):  # First 5 pages
                url = f'https://www.bigbasket.com/pc/{main_cat}/{sub_cat}/?page={page}'
                yield scrapy.Request(
                    url,
                    callback=self.parse_category_page,
                    meta={'category': f'{main_cat}/{sub_cat}', 'page': page, 'strategy': 'category'}
                )
    
    def parse_sitemap(self, response):
        """Parse sitemap.xml for product URLs"""
        # Look for product URLs in sitemap
        namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Product URLs usually contain /pd/
        product_urls = response.xpath('//ns:url/ns:loc[contains(text(), "/pd/")]/text()', namespaces=namespaces).getall()
        
        self.logger.info(f"Found {len(product_urls)} products in sitemap")
        
        for url in product_urls[:100]:  # Limit for testing
            yield {
                'url': url,
                'discovery_method': 'sitemap',
                'type': 'product'
            }
        
        # Also look for category sitemaps
        category_sitemaps = response.xpath('//ns:sitemap/ns:loc/text()', namespaces=namespaces).getall()
        for sitemap_url in category_sitemaps:
            if 'product' in sitemap_url or 'category' in sitemap_url:
                yield scrapy.Request(sitemap_url, callback=self.parse_sitemap)
    
    def parse_search_api(self, response):
        """Parse BigBasket's search API response"""
        try:
            # BigBasket returns HTML, but might have JSON in script tags
            # Look for JSON data in the response
            scripts = response.xpath('//script[@type="application/json"]/text()').getall()
            
            for script in scripts:
                try:
                    data = json.loads(script)
                    # Extract product URLs from the JSON structure
                    if 'products' in data:
                        for product in data['products']:
                            if 'url' in product:
                                yield {
                                    'url': product['url'],
                                    'discovery_method': 'search_api',
                                    'search_term': response.meta.get('search_term'),
                                    'type': 'product'
                                }
                except json.JSONDecodeError:
                    continue
            
            # Also try to find product links in HTML
            product_links = response.css('a[href*="/pd/"]::attr(href)').getall()
            for link in product_links:
                yield {
                    'url': response.urljoin(link),
                    'discovery_method': 'search_results',
                    'search_term': response.meta.get('search_term'),
                    'type': 'product'
                }
                
        except Exception as e:
            self.logger.error(f"Error parsing search API: {e}")
    
    def parse_category_page(self, response):
        """Parse category pages for product links"""
        # Strategy 1: Look for product links in HTML
        product_links = response.css('a[href*="/pd/"]::attr(href)').getall()
        
        for link in product_links:
            yield {
                'url': response.urljoin(link),
                'discovery_method': 'category_page',
                'category': response.meta.get('category'),
                'page': response.meta.get('page'),
                'type': 'product'
            }
        
        # Strategy 2: Look for AJAX endpoints in JavaScript
        # BigBasket often loads products via AJAX
        ajax_patterns = [
            r'productlist["\']?\s*:\s*["\']([^"\']+)',
            r'api/[^"\']*products[^"\']*',
            r'/ps/v1/[^"\']+',
        ]
        
        scripts = response.xpath('//script/text()').getall()
        for script in scripts:
            for pattern in ajax_patterns:
                import re
                matches = re.findall(pattern, script)
                for match in matches:
                    if match.startswith('/'):
                        ajax_url = response.urljoin(match)
                        yield scrapy.Request(
                            ajax_url,
                            callback=self.parse_ajax_products,
                            meta={'category': response.meta.get('category')}
                        )
        
        # Strategy 3: Look for "Load More" or pagination AJAX calls
        load_more = response.css('[class*="load-more"]::attr(data-url)').get()
        if load_more:
            yield scrapy.Request(
                response.urljoin(load_more),
                callback=self.parse_ajax_products,
                meta={'category': response.meta.get('category')}
            )
    
    def parse_ajax_products(self, response):
        """Parse AJAX responses containing product data"""
        try:
            data = json.loads(response.text)
            
            # Common patterns in e-commerce AJAX responses
            products = (
                data.get('products', []) or 
                data.get('data', {}).get('products', []) or
                data.get('items', []) or
                data.get('results', [])
            )
            
            for product in products:
                # Extract URL from various possible fields
                url = (
                    product.get('url') or 
                    product.get('product_url') or
                    product.get('link') or
                    product.get('permalink')
                )
                
                if url:
                    yield {
                        'url': response.urljoin(url),
                        'discovery_method': 'ajax_api',
                        'category': response.meta.get('category'),
                        'type': 'product',
                        'product_id': product.get('id') or product.get('product_id'),
                        'name': product.get('name') or product.get('title')
                    }
                    
        except json.JSONDecodeError:
            # If not JSON, try to extract links from HTML response
            product_links = response.css('a[href*="/pd/"]::attr(href)').getall()
            for link in product_links:
                yield {
                    'url': response.urljoin(link),
                    'discovery_method': 'ajax_html',
                    'type': 'product'
                }
