"""
BigBasket adapter for crawling
"""
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
from .base import RetailerAdapter


class BigBasketAdapter(RetailerAdapter):
    """Adapter for BigBasket.com"""
    
    def get_base_url(self) -> str:
        return "https://www.bigbasket.com"
    
    def get_search_url(self, term: str, page: int = 1) -> str:
        """BigBasket search URL"""
        params = {
            'q': term,
            'page': page
        }
        return f"{self.base_url}/ps/?{urlencode(params)}"
    
    def get_category_url(self, category_path: str, page: int = 1) -> str:
        """BigBasket category URL"""
        # Ensure path starts with /
        if not category_path.startswith('/'):
            category_path = '/' + category_path
        
        # Add page parameter if > 1
        if page > 1:
            return f"{self.base_url}{category_path}?page={page}"
        return f"{self.base_url}{category_path}"
    
    def get_product_url_pattern(self) -> str:
        """Pattern for BigBasket product URLs"""
        return r'/pd/\d+/[^/]+/'
    
    def get_trending_url(self) -> Optional[str]:
        """BigBasket trending products"""
        return f"{self.base_url}/cl/new-products/"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        """BigBasket specific selectors"""
        return {
            'name': [
                'h1.pd-name::text',
                'h1::text',
                '[qa="product-name"]::text'
            ],
            'brand': [
                'a[qa="pd-brand"]::text',
                '.pd-brand a::text',
                '[class*="brand"]::text'
            ],
            'price': [
                'td[qa="price"]::text',
                '.pd-price::text',
                '[class*="selling-price"]::text'
            ],
            'mrp': [
                'td[qa="mrp"]::text',
                '.pd-mrp::text',
                '[class*="mrp"]::text'
            ],
            'image': [
                'img[qa="pd-image"]::attr(src)',
                '.pd-image img::attr(src)',
                'img[class*="product-image"]::attr(src)'
            ],
            'description': [
                'div[qa="pd-details"]::text',
                '.pd-details::text',
                '[class*="description"]::text'
            ],
            'pack_size': [
                'div[qa="pack-size"]::text',
                '.pack-size::text',
                '[class*="weight"]::text'
            ],
            'rating': [
                'span[qa="rating"]::text',
                '.rating-value::text'
            ]
        }
    
    def extract_product_urls(self, response) -> List[str]:
        """Extract product URLs from BigBasket listing page"""
        urls = []
        
        # Method 1: Product cards with qa attributes
        product_links = response.css('div[qa="product"] a::attr(href)').getall()
        urls.extend(product_links)
        
        # Method 2: Any link matching product pattern
        all_links = response.css('a::attr(href)').getall()
        for link in all_links:
            if self.is_product_url(link):
                urls.append(link)
        
        # Normalize and deduplicate
        normalized = [self.normalize_url(url, response.url) for url in urls]
        return list(set(normalized))
    
    def extract_product_data(self, response) -> Dict[str, Any]:
        """Extract product data from BigBasket product page"""
        # Basic fields
        data = {
            'url': response.url,
            'retailer': 'bigbasket',
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
        
        # Additional fields
        data['pack_size'] = self.extract_field(response, 'pack_size')
        data['description'] = self.extract_field(response, 'description')
        
        # Rating
        rating_text = self.extract_field(response, 'rating')
        if rating_text:
            try:
                data['rating'] = float(rating_text)
            except ValueError:
                pass
        
        # Breadcrumbs for category
        breadcrumbs = response.css('nav[aria-label="breadcrumb"] a::text').getall()
        if breadcrumbs:
            data['breadcrumbs'] = [b.strip() for b in breadcrumbs if b.strip()]
            if len(breadcrumbs) > 1:
                data['category'] = breadcrumbs[-2]
                if len(breadcrumbs) > 2:
                    data['subcategory'] = breadcrumbs[-1]
        
        # Availability
        add_button = response.css('button[qa="add"]::text').get()
        data['in_stock'] = bool(add_button and 'add' in add_button.lower())
        
        # Seller
        data['seller'] = response.css('span[qa="seller-name"]::text').get()
        
        # Ingredients and nutrition
        info_data = self.extract_ingredients_nutrition(response)
        data.update(info_data)
        
        # Look specifically in product info sections
        self._extract_detailed_info(response, data)
        
        return data
    
    def _extract_detailed_info(self, response, data: Dict[str, Any]):
        """Extract detailed product information from tabs/sections"""
        # BigBasket often has tabbed content
        tabs = response.css('div.tabs-content, div[class*="product-info"]')
        
        for tab in tabs:
            tab_title = tab.css('h2::text, h3::text').get()
            if tab_title:
                tab_title_lower = tab_title.lower()
                
                if 'ingredient' in tab_title_lower:
                    ingredients = ' '.join(tab.css('::text').getall()).strip()
                    if ingredients and len(ingredients) > len(data.get('ingredients_text', '')):
                        data['ingredients_text'] = ingredients
                
                elif 'nutrition' in tab_title_lower:
                    nutrition = ' '.join(tab.css('::text').getall()).strip()
                    if nutrition and len(nutrition) > len(data.get('nutrition_text', '')):
                        data['nutrition_text'] = nutrition
                
                elif 'about' in tab_title_lower or 'description' in tab_title_lower:
                    about = ' '.join(tab.css('::text').getall()).strip()
                    if about and len(about) > len(data.get('description', '')):
                        data['description'] = about
        
        # Extract key features
        features = response.css('div[class*="key-features"] li::text').getall()
        if features:
            data['key_features'] = [f.strip() for f in features if f.strip()]
        
        # Extract manufacturer info
        manufacturer = response.css('div:contains("Manufacturer") + div::text').get()
        if manufacturer:
            data['manufacturer'] = manufacturer.strip()
        
        # Extract country of origin
        country = response.css('div:contains("Country of Origin") + div::text').get()
        if country:
            data['country_of_origin'] = country.strip()
