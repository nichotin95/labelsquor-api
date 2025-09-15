"""
Blinkit (formerly Grofers) adapter for crawling
"""
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
from .base import RetailerAdapter


class BlinkitAdapter(RetailerAdapter):
    """Adapter for Blinkit.com"""
    
    def get_base_url(self) -> str:
        return "https://blinkit.com"
    
    def get_search_url(self, term: str, page: int = 1) -> str:
        """Blinkit search URL"""
        # Blinkit uses different URL structure
        return f"{self.base_url}/s/?q={term}"
    
    def get_category_url(self, category_path: str, page: int = 1) -> str:
        """Blinkit category URL"""
        # Ensure path starts with /
        if not category_path.startswith('/'):
            category_path = '/' + category_path
        
        return f"{self.base_url}{category_path}"
    
    def get_product_url_pattern(self) -> str:
        """Pattern for Blinkit product URLs"""
        # Blinkit uses /p/ for products
        return r'/p/[^/]+/[^/]+'
    
    def get_trending_url(self) -> Optional[str]:
        """Blinkit trending/new products"""
        return f"{self.base_url}/c/new-arrivals/"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        """Blinkit specific selectors"""
        return {
            'name': [
                'h1[class*="ProductName"]::text',
                'h1::text',
                '[class*="product-name"]::text'
            ],
            'brand': [
                '[class*="BrandName"]::text',
                'div[class*="brand"]::text',
                'span[class*="brand"]::text'
            ],
            'price': [
                '[class*="Price"]::text',
                'span[class*="selling-price"]::text',
                'div[class*="price"]:not([class*="mrp"])::text'
            ],
            'mrp': [
                '[class*="MRP"]::text',
                'span[class*="mrp"]::text',
                'del::text'
            ],
            'image': [
                'img[class*="ProductImage"]::attr(src)',
                'div[class*="product-image"] img::attr(src)',
                'img[alt*="product"]::attr(src)'
            ],
            'description': [
                'div[class*="Description"]::text',
                'div[class*="product-details"]::text'
            ],
            'unit': [
                'span[class*="Unit"]::text',
                'div[class*="weight"]::text',
                'span[class*="size"]::text'
            ]
        }
    
    def extract_product_urls(self, response) -> List[str]:
        """Extract product URLs from Blinkit listing page"""
        urls = []
        
        # Method 1: Product grid links
        product_links = response.css('a[href*="/p/"]::attr(href)').getall()
        urls.extend(product_links)
        
        # Method 2: Product cards
        product_cards = response.css('div[class*="ProductCard"] a::attr(href)').getall()
        urls.extend(product_cards)
        
        # Method 3: Any link matching product pattern
        all_links = response.css('a::attr(href)').getall()
        for link in all_links:
            if self.is_product_url(link):
                urls.append(link)
        
        # Normalize and deduplicate
        normalized = [self.normalize_url(url, response.url) for url in urls]
        return list(set(normalized))
    
    def extract_product_data(self, response) -> Dict[str, Any]:
        """Extract product data from Blinkit product page"""
        # Basic fields
        data = {
            'url': response.url,
            'retailer': 'blinkit',
            'name': self.extract_field(response, 'name'),
            'brand': self.extract_field(response, 'brand'),
            'images': self.extract_images(response),
        }
        
        # Price information
        price_text = self.extract_field(response, 'price')
        if price_text:
            data['price'] = self.extract_price(price_text)
            data['currency'] = 'INR'
        
        mrp_text = self.extract_field(response, 'mrp')
        if mrp_text:
            data['mrp'] = self.extract_price(mrp_text)
        
        # Unit/Size
        data['unit'] = self.extract_field(response, 'unit')
        data['description'] = self.extract_field(response, 'description')
        
        # Category from breadcrumbs
        breadcrumbs = response.css('nav[aria-label="breadcrumb"] a::text').getall()
        if not breadcrumbs:
            breadcrumbs = response.css('[class*="breadcrumb"] a::text').getall()
        
        if breadcrumbs:
            data['breadcrumbs'] = [b.strip() for b in breadcrumbs if b.strip()]
            if len(breadcrumbs) > 1:
                data['category'] = breadcrumbs[-2]
        
        # Availability - Blinkit shows delivery time if available
        delivery_time = response.css('[class*="DeliveryTime"]::text').get()
        data['in_stock'] = bool(delivery_time and 'min' in delivery_time.lower())
        
        # Extract detailed information
        info_data = self.extract_ingredients_nutrition(response)
        data.update(info_data)
        
        # Blinkit specific info extraction
        self._extract_blinkit_details(response, data)
        
        return data
    
    def _extract_blinkit_details(self, response, data: Dict[str, Any]):
        """Extract Blinkit-specific product details"""
        # Product highlights
        highlights = response.css('div[class*="Highlights"] li::text').getall()
        if highlights:
            data['highlights'] = [h.strip() for h in highlights if h.strip()]
        
        # Product info sections
        info_sections = response.css('div[class*="ProductInfo"] > div')
        
        for section in info_sections:
            # Look for title and content pairs
            title = section.css('div:first-child::text').get()
            content = section.css('div:last-child::text').get()
            
            if title and content:
                title_lower = title.lower()
                
                if 'manufacturer' in title_lower:
                    data['manufacturer'] = content.strip()
                elif 'country' in title_lower:
                    data['country_of_origin'] = content.strip()
                elif 'shelf life' in title_lower:
                    data['shelf_life'] = content.strip()
                elif 'storage' in title_lower:
                    data['storage_instructions'] = content.strip()
        
        # Important information section
        important_info = response.css('div[class*="ImportantInfo"]::text').getall()
        if important_info:
            data['important_info'] = ' '.join(info.strip() for info in important_info if info.strip())
