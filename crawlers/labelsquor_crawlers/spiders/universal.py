"""
Universal spider that works with all retailers using adapters
"""
import scrapy
import json
from typing import Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

from labelsquor_crawlers.adapters.factory import RetailerAdapterFactory
from labelsquor_crawlers.items import ProductItem


class UniversalSpider(scrapy.Spider):
    """Single spider that handles all retailers through adapters"""
    name = 'universal'
    
    def __init__(self, retailer: str = None, strategy: str = 'discover', 
                 target: str = None, task_id: str = None, *args, **kwargs):
        """
        Initialize universal spider
        
        Args:
            retailer: Retailer name (bigbasket, blinkit, etc.)
            strategy: Crawling strategy (discover, search, category, product, sitemap)
            target: Target value (search term, category path, product URL, etc.)
            task_id: Optional task ID for tracking
        """
        super().__init__(*args, **kwargs)
        
        if not retailer:
            raise ValueError("Retailer must be specified")
        
        self.retailer = retailer.lower()
        self.strategy = strategy
        self.target = target
        self.task_id = task_id
        
        # Get retailer adapter
        self.adapter = RetailerAdapterFactory.get_adapter(self.retailer)
        self.allowed_domains = [urlparse(self.adapter.base_url).netloc]
        
        # Crawl statistics
        self.stats = {
            'products_found': 0,
            'pages_crawled': 0,
            'errors': 0
        }
        
        self.logger.info(f"Initialized {self.retailer} spider with strategy: {strategy}")
    
    def start_requests(self):
        """Generate initial requests based on strategy"""
        if self.strategy == 'search':
            # Search for a term
            url = self.adapter.get_search_url(self.target)
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={'page': 1, 'search_term': self.target}
            )
            
        elif self.strategy == 'category':
            # Browse a category
            url = self.adapter.get_category_url(self.target)
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={'page': 1, 'category': self.target}
            )
            
        elif self.strategy == 'product':
            # Crawl specific product URL
            yield scrapy.Request(
                self.target,
                callback=self.parse_product,
                meta={'direct_crawl': True}
            )
            
        elif self.strategy == 'sitemap':
            # Parse sitemaps
            for sitemap_url in self.adapter.get_sitemap_urls():
                yield scrapy.Request(
                    sitemap_url,
                    callback=self.parse_sitemap,
                    meta={'sitemap_index': True}
                )
                
        elif self.strategy == 'trending':
            # Get trending products
            if trending_url := self.adapter.get_trending_url():
                yield scrapy.Request(
                    trending_url,
                    callback=self.parse_listing,
                    meta={'page': 1, 'trending': True}
                )
                
        else:
            # Default: discover mode - try multiple strategies
            yield from self._discover_mode()
    
    def _discover_mode(self):
        """Discovery mode: use multiple strategies to find products"""
        # 1. Try sitemap first
        for sitemap_url in self.adapter.get_sitemap_urls()[:1]:
            yield scrapy.Request(
                sitemap_url,
                callback=self.parse_sitemap,
                meta={'discovery': True},
                dont_filter=True
            )
        
        # 2. Search for popular terms
        popular_searches = ['chips', 'biscuits', 'noodles', 'chocolate', 'milk']
        for term in popular_searches[:3]:
            url = self.adapter.get_search_url(term)
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={'search_term': term, 'discovery': True}
            )
        
        # 3. Browse main categories
        if self.retailer == 'bigbasket':
            categories = ['/pc/snacks-branded-foods/', '/pc/beverages/', '/pc/dairy/']
        elif self.retailer == 'blinkit':
            categories = ['/c/chips-crisps-nachos/', '/c/soft-drinks/', '/c/dairy-products/']
        else:
            categories = []
        
        for cat in categories[:2]:
            url = self.adapter.get_category_url(cat)
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={'category': cat, 'discovery': True}
            )
    
    def parse_listing(self, response):
        """Parse product listing pages (search results, categories)"""
        self.stats['pages_crawled'] += 1
        
        # Extract product URLs
        product_urls = self.adapter.extract_product_urls(response)
        self.logger.info(f"Found {len(product_urls)} products on {response.url}")
        
        for url in product_urls:
            self.stats['products_found'] += 1
            
            # Yield discovery result
            yield {
                'type': 'product_url',
                'url': url,
                'retailer': self.retailer,
                'discovery_method': self.strategy,
                'source_url': response.url,
                'metadata': {
                    'search_term': response.meta.get('search_term'),
                    'category': response.meta.get('category'),
                    'page': response.meta.get('page', 1)
                }
            }
            
            # Follow to product page if not in discovery mode
            if not response.meta.get('discovery'):
                yield scrapy.Request(
                    url,
                    callback=self.parse_product,
                    meta={'listing_url': response.url}
                )
        
        # Handle pagination
        current_page = response.meta.get('page', 1)
        max_pages = self.settings.getint('MAX_PAGES_PER_CATEGORY', 5)
        
        if current_page < max_pages and product_urls:
            # Try next page
            next_page = current_page + 1
            
            if response.meta.get('search_term'):
                next_url = self.adapter.get_search_url(
                    response.meta['search_term'], 
                    page=next_page
                )
            elif response.meta.get('category'):
                next_url = self.adapter.get_category_url(
                    response.meta['category'],
                    page=next_page
                )
            else:
                next_url = None
            
            if next_url:
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_listing,
                    meta={**response.meta, 'page': next_page}
                )
    
    def parse_product(self, response):
        """Parse individual product pages"""
        try:
            # Extract product data using adapter
            product_data = self.adapter.extract_product_data(response)
            
            # Create product item
            item = ProductItem()
            
            # Map extracted data to item fields
            item['url'] = product_data.get('url', response.url)
            item['retailer'] = self.retailer
            item['crawled_at'] = datetime.utcnow().isoformat()
            
            # Basic info
            item['name'] = product_data.get('name')
            item['brand'] = product_data.get('brand')
            item['category'] = product_data.get('category')
            item['subcategory'] = product_data.get('subcategory')
            item['breadcrumbs'] = product_data.get('breadcrumbs', [])
            
            # Pricing
            item['price'] = product_data.get('price')
            item['mrp'] = product_data.get('mrp')
            item['currency'] = product_data.get('currency', 'INR')
            
            if item['price'] and item['mrp'] and item['mrp'] > item['price']:
                item['discount'] = round((item['mrp'] - item['price']) / item['mrp'] * 100, 2)
            
            # Images
            item['images'] = product_data.get('images', [])
            if item['images']:
                item['primary_image'] = item['images'][0]
            
            # Product details
            item['description'] = product_data.get('description')
            item['ingredients_text'] = product_data.get('ingredients_text')
            item['nutrition_text'] = product_data.get('nutrition_text')
            
            # Additional info
            item['pack_size'] = product_data.get('pack_size') or product_data.get('unit')
            item['manufacturer'] = product_data.get('manufacturer')
            item['country_of_origin'] = product_data.get('country_of_origin')
            
            # Availability
            item['in_stock'] = product_data.get('in_stock', True)
            item['seller'] = product_data.get('seller')
            
            # Ratings
            item['rating'] = product_data.get('rating')
            item['review_count'] = product_data.get('review_count')
            
            # Certifications
            item['certifications'] = product_data.get('certifications', [])
            
            # Store HTML for later processing
            item['page_html'] = response.text
            
            # Add metadata
            item['sku'] = self._extract_sku(response.url)
            
            yield item
            
        except Exception as e:
            self.logger.error(f"Error parsing product {response.url}: {e}")
            self.stats['errors'] += 1
            
            # Yield error for tracking
            yield {
                'type': 'error',
                'url': response.url,
                'error': str(e),
                'retailer': self.retailer
            }
    
    def parse_sitemap(self, response):
        """Parse XML sitemaps"""
        namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Check if this is a sitemap index
        sitemap_urls = response.xpath('//ns:sitemap/ns:loc/text()', namespaces=namespaces).getall()
        
        if sitemap_urls:
            # This is a sitemap index, follow sitemaps
            for sitemap_url in sitemap_urls:
                if 'product' in sitemap_url.lower():
                    yield scrapy.Request(
                        sitemap_url,
                        callback=self.parse_sitemap,
                        priority=10
                    )
        else:
            # This is a regular sitemap, extract URLs
            urls = response.xpath('//ns:url/ns:loc/text()', namespaces=namespaces).getall()
            
            for url in urls:
                if self.adapter.is_product_url(url):
                    yield {
                        'type': 'product_url',
                        'url': url,
                        'retailer': self.retailer,
                        'discovery_method': 'sitemap'
                    }
                    
                    # Follow product URLs if not in discovery mode
                    if not response.meta.get('discovery'):
                        yield scrapy.Request(
                            url,
                            callback=self.parse_product,
                            meta={'from_sitemap': True}
                        )
    
    def _extract_sku(self, url: str) -> Optional[str]:
        """Extract SKU/product ID from URL"""
        # Try to extract numeric ID from URL
        import re
        
        # Common patterns
        patterns = [
            r'/pd/(\d+)/',  # BigBasket
            r'/p/([^/]+)/',  # Blinkit
            r'/dp/([A-Z0-9]+)',  # Amazon style
            r'/product/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def closed(self, reason):
        """Spider closed callback"""
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Stats: {json.dumps(self.stats, indent=2)}")
        
        # Report back to task tracker if task_id is set
        if self.task_id:
            # This would update the task status in database
            pass
