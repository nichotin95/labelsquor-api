"""
Base adapter class for retailer-specific crawling logic
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import re
from urllib.parse import urljoin, urlparse


class RetailerAdapter(ABC):
    """Base class for retailer-specific crawling logic"""
    
    def __init__(self):
        self.name = self.__class__.__name__.replace('Adapter', '').lower()
        self.base_url = self.get_base_url()
    
    @abstractmethod
    def get_base_url(self) -> str:
        """Return the base URL for this retailer"""
        pass
    
    @abstractmethod
    def get_search_url(self, term: str, page: int = 1) -> str:
        """Build search URL for a search term"""
        pass
    
    @abstractmethod
    def get_category_url(self, category_path: str, page: int = 1) -> str:
        """Build category browsing URL"""
        pass
    
    @abstractmethod
    def get_product_url_pattern(self) -> str:
        """Regex pattern to identify product URLs"""
        pass
    
    @abstractmethod
    def extract_product_urls(self, response) -> List[str]:
        """Extract product URLs from a listing page"""
        pass
    
    @abstractmethod
    def extract_product_data(self, response) -> Dict[str, Any]:
        """Extract product data from a product page"""
        pass
    
    def get_trending_url(self) -> Optional[str]:
        """URL for trending/new products (optional)"""
        return None
    
    def get_sitemap_urls(self) -> List[str]:
        """List of sitemap URLs to check"""
        return [
            urljoin(self.base_url, '/sitemap.xml'),
            urljoin(self.base_url, '/sitemap-index.xml'),
            urljoin(self.base_url, '/product-sitemap.xml'),
        ]
    
    def is_product_url(self, url: str) -> bool:
        """Check if a URL is a product page"""
        pattern = self.get_product_url_pattern()
        return bool(re.search(pattern, url))
    
    def normalize_url(self, url: str, base_url: str = None) -> str:
        """Normalize and validate URL"""
        # Make absolute URL
        if not url.startswith(('http://', 'https://')):
            base = base_url or self.base_url
            url = urljoin(base, url)
        
        # Remove tracking parameters
        parsed = urlparse(url)
        if parsed.query:
            # Keep only essential parameters
            url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        return url
    
    def extract_price(self, price_text: str) -> Optional[float]:
        """Extract numeric price from text"""
        if not price_text:
            return None
        
        # Remove currency symbols and extract numbers
        price = re.findall(r'[\d,]+\.?\d*', price_text)
        if price:
            # Remove commas and convert to float
            return float(price[0].replace(',', ''))
        return None
    
    def extract_text_safely(self, selector, response) -> Optional[str]:
        """Safely extract text from a selector"""
        try:
            texts = response.css(f'{selector}::text').getall()
            if texts:
                return ' '.join(text.strip() for text in texts if text.strip())
        except Exception:
            pass
        return None
    
    def get_selectors(self) -> Dict[str, List[str]]:
        """Get CSS selectors for common fields (override in subclasses)"""
        return {
            'name': ['h1::text', '[class*="product-name"]::text', '[class*="title"]::text'],
            'brand': ['[class*="brand"]::text', '[itemprop="brand"]::text'],
            'price': ['[class*="price"]::text', '[itemprop="price"]::text'],
            'mrp': ['[class*="mrp"]::text', '[class*="original-price"]::text'],
            'image': ['img[class*="product"]::attr(src)', '[itemprop="image"]::attr(src)'],
            'description': ['[class*="description"]::text', '[class*="details"]::text'],
            'rating': ['[class*="rating"]::text', '[itemprop="ratingValue"]::text'],
        }
    
    def extract_field(self, response, field: str) -> Optional[str]:
        """Extract a field using multiple selectors"""
        selectors = self.get_selectors().get(field, [])
        
        for selector in selectors:
            value = response.css(selector).get()
            if value:
                return value.strip()
        
        return None
    
    def extract_images(self, response) -> List[str]:
        """Extract all product images"""
        image_selectors = self.get_selectors().get('image', [])
        images = []
        
        for selector in image_selectors:
            found_images = response.css(selector).getall()
            images.extend(found_images)
        
        # Normalize URLs
        return [self.normalize_url(img, response.url) for img in images if img]
    
    def extract_ingredients_nutrition(self, response) -> Dict[str, Optional[str]]:
        """Extract ingredients and nutrition info"""
        result = {
            'ingredients_text': None,
            'nutrition_text': None
        }
        
        # Look for sections containing ingredients/nutrition
        info_sections = response.css('div[class*="info"], div[class*="details"], section[class*="product"]')
        
        for section in info_sections:
            section_text = ' '.join(section.css('::text').getall()).lower()
            
            if 'ingredient' in section_text and not result['ingredients_text']:
                result['ingredients_text'] = ' '.join(section.css('::text').getall()).strip()
            
            if 'nutrition' in section_text and not result['nutrition_text']:
                result['nutrition_text'] = ' '.join(section.css('::text').getall()).strip()
        
        return result
