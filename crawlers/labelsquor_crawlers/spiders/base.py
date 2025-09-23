"""
Base spider class with anti-blocking measures
All retailer spiders should inherit from this
"""
import scrapy
from typing import Optional, Dict, Any
from ..antiblock.base import RetailerAntiBlockRegistry


class AntiBlockSpider(scrapy.Spider):
    """
    Base spider with built-in anti-blocking capabilities
    """
    
    # Override in subclasses
    retailer: Optional[str] = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load anti-block strategy
        if self.retailer:
            self.antiblock_strategy = RetailerAntiBlockRegistry.get_strategy(self.retailer)
            self.logger.info(f"Loaded {self.retailer} anti-block strategy")
            
            # Apply spider-specific settings from strategy
            if hasattr(self.antiblock_strategy, 'config'):
                self._apply_strategy_settings()
    
    def _apply_strategy_settings(self):
        """Apply settings from anti-block strategy"""
        config = self.antiblock_strategy.config
        
        # Custom settings for this spider
        if not hasattr(self, 'custom_settings'):
            self.custom_settings = {}
        
        # Apply download delay
        if 'download_delay' in config:
            self.custom_settings['DOWNLOAD_DELAY'] = config['download_delay']
        
        # Apply concurrent requests
        if 'concurrent_requests' in config:
            self.custom_settings['CONCURRENT_REQUESTS_PER_DOMAIN'] = config['concurrent_requests']
        
        # Apply autothrottle
        if 'autothrottle_target' in config:
            self.custom_settings['AUTOTHROTTLE_TARGET_CONCURRENCY'] = config['autothrottle_target']
        
        # Enable cookies if needed
        if config.get('cookies_enabled', False):
            self.custom_settings['COOKIES_ENABLED'] = True
    
    def start_requests(self):
        """Override this in subclasses"""
        raise NotImplementedError("Subclasses must implement start_requests()")
    
    def parse(self, response):
        """Override this in subclasses"""
        raise NotImplementedError("Subclasses must implement parse()")
    
    def handle_error(self, failure):
        """Common error handling"""
        self.logger.error(f"Request failed: {failure.value}")
        
        # Check if it's a blocking error
        if self.antiblock_strategy and hasattr(failure.value, 'response'):
            response = failure.value.response
            if self.antiblock_strategy.handle_blocking_response(response):
                self.logger.warning(f"Detected blocking on {response.url}")
                # The middleware will handle retry
        
        # Log to stats
        self.crawler.stats.inc_value(f'spider/{self.name}/errors/{failure.type.__name__}')


class SearchBasedSpider(AntiBlockSpider):
    """
    Base class for spiders that search for products
    """
    
    def __init__(self, search_terms=None, max_products=100, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Parse search terms
        if search_terms:
            if isinstance(search_terms, str):
                self.search_terms = [term.strip() for term in search_terms.split(',')]
            else:
                self.search_terms = search_terms
        else:
            # Default search terms
            self.search_terms = [
                'maggi', 'lays', 'kurkure', 'coca cola', 'pepsi',
                'amul', 'britannia', 'parle', 'haldiram', 'nestle'
            ]
        
        self.max_products = int(max_products)
        self.products_crawled = 0
    
    def should_continue_crawling(self) -> bool:
        """Check if we should continue crawling"""
        return self.products_crawled < self.max_products


class CategoryBasedSpider(AntiBlockSpider):
    """
    Base class for spiders that browse categories
    """
    
    # Override in subclasses
    categories: Dict[str, str] = {}
    
    def __init__(self, categories=None, max_pages=10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if categories:
            self.categories = categories
        
        self.max_pages = int(max_pages)
        self.pages_crawled = 0
