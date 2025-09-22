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
    
    def extract_images(self, response) -> List[str]:
        """Extract ALL product images from BigBasket - DON'T FILTER!"""
        images = []
        
        # Method 1: Product image gallery (most common)
        # BigBasket uses different selectors across pages
        gallery_selectors = [
            '.pd-image img::attr(src)',
            '.pd-image img::attr(data-src)',
            '.product-image img::attr(src)',
            'div[class*="product-image"] img::attr(src)',
            '#product-images img::attr(src)',
            '.item-img img::attr(src)'
        ]
        
        for selector in gallery_selectors:
            found = response.css(selector).getall()
            images.extend(found)
        
        # Method 2: Thumbnail images (often has back/side views)
        thumbnail_selectors = [
            '.thumbnail img::attr(src)',
            '.product-thumbs img::attr(src)',
            '.pd-thumbnail img::attr(src)',
            'div[class*="thumbnail"] img::attr(src)'
        ]
        
        for selector in thumbnail_selectors:
            found = response.css(selector).getall()
            images.extend(found)
        
        # Method 3: From JavaScript data
        # BigBasket often loads images via JS
        script_selectors = [
            'script:contains("productImages")',
            'script:contains("imageUrls")',
            'script:contains("gallery")'
        ]
        
        for selector in script_selectors:
            scripts = response.css(f'{selector}::text').getall()
            for script in scripts:
                # Extract URLs from JavaScript
                import re
                # Look for image URLs in JSON arrays
                urls = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', script)
                images.extend(urls)
                # Also look for paths that need domain
                paths = re.findall(r'"/media/[^"]+\.(?:jpg|jpeg|png|webp)[^"]*"', script)
                images.extend([p.strip('"') for p in paths])
        
        # Method 4: From meta tags (sometimes has main image)
        meta_images = response.css('meta[property="og:image"]::attr(content)').getall()
        images.extend(meta_images)
        
        # Normalize all URLs
        normalized = []
        seen = set()
        
        for img in images:
            if not img:
                continue
                
            # Clean the URL
            img = img.strip()
            
            # Convert to full URL
            if img.startswith('//'):
                img = 'https:' + img
            elif img.startswith('/'):
                # BigBasket uses bbassets.com CDN
                img = 'https://www.bbassets.com' + img
            elif not img.startswith('http'):
                # Relative URL
                img = 'https://www.bbassets.com/media/' + img
                
            # Only add if not seen
            if img not in seen and ('.jpg' in img or '.jpeg' in img or '.png' in img or '.webp' in img):
                seen.add(img)
                normalized.append(img)
        
        # IMPORTANT: Return ALL images - back/side views have ingredients!
        return normalized
    
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
