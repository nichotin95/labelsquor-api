"""
BigBasket spider for crawling product data
"""
import scrapy
from scrapy.http import Response
from urllib.parse import urljoin
import json

from labelsquor_crawlers.items import ProductItem
from .base import CategoryBasedSpider


class BigBasketSpider(CategoryBasedSpider):
    name = 'bigbasket'
    allowed_domains = ['bigbasket.com']
    retailer = 'bigbasket'  # For anti-block strategy
    
    # Custom settings will be merged with strategy settings
    custom_settings = {
        'USER_AGENT': None,  # Will use strategy user agents
    }
    
    # Starting categories
    start_urls = [
        'https://www.bigbasket.com/pc/snacks-branded-foods/chips-crisps/',
        'https://www.bigbasket.com/pc/beverages/soft-drinks/',
        'https://www.bigbasket.com/pc/dairy/milk/',
        'https://www.bigbasket.com/pc/snacks-branded-foods/biscuits-cookies/',
        'https://www.bigbasket.com/pc/bakery-cakes-dairy/breads-buns/',
        'https://www.bigbasket.com/pc/staples/atta-flours/',
        'https://www.bigbasket.com/pc/snacks-branded-foods/chocolates-candies/',
        'https://www.bigbasket.com/pc/staples/rice-rice-products/',
        'https://www.bigbasket.com/pc/dairy/paneer-tofu/',
        'https://www.bigbasket.com/pc/snacks-branded-foods/noodles-pasta-vermicelli/',
    ]
    
    def parse(self, response: Response):
        """Parse category page"""
        # BigBasket loads products dynamically, so we need to find the API calls
        # Look for product data in script tags
        scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        
        for script in scripts:
            try:
                data = json.loads(script)
                if data.get('@type') == 'ItemList':
                    # Found product list data
                    for item in data.get('itemListElement', []):
                        product_url = item.get('url')
                        if product_url:
                            yield response.follow(
                                product_url,
                                callback=self.parse_product,
                                meta={'breadcrumbs': response.meta.get('breadcrumbs', [])}
                            )
            except json.JSONDecodeError:
                continue
        
        # Also look for product links in HTML
        product_links = response.css('div[qa="product"] a::attr(href)').getall()
        for link in product_links:
            yield response.follow(link, callback=self.parse_product)
        
        # Follow pagination
        next_page = response.css('a[rel="next"]::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)
    
    def parse_product(self, response: Response):
        """Parse product page"""
        # Create product item
        item = ProductItem()
        
        # Basic info
        item['retailer'] = self.name
        item['url'] = response.url
        
        # Product name and brand
        item['name'] = response.css('h1::text').get()
        item['brand'] = response.css('a[qa="pd-brand"]::text').get()
        
        # Breadcrumbs for category
        breadcrumbs = response.css('nav[aria-label="breadcrumb"] a::text').getall()
        item['breadcrumbs'] = [b.strip() for b in breadcrumbs if b.strip()]
        
        if len(breadcrumbs) > 2:
            item['category'] = breadcrumbs[-2]
            item['subcategory'] = breadcrumbs[-1]
        
        # Price info
        price_text = response.css('td[qa="price"]::text').get()
        if price_text:
            item['price'] = self._extract_price(price_text)
        
        mrp_text = response.css('td[qa="mrp"]::text').get()
        if mrp_text:
            item['mrp'] = self._extract_price(mrp_text)
        
        # Images
        images = response.css('img[qa="pd-image"]::attr(src)').getall()
        item['images'] = [urljoin(response.url, img) for img in images]
        if images:
            item['primary_image'] = item['images'][0]
        
        # Product details
        item['description'] = response.css('div[qa="pd-details"]::text').get()
        
        # Pack size
        pack_info = response.css('div[qa="pack-size"]::text').get()
        if pack_info:
            item['pack_size'] = pack_info.strip()
        
        # Look for ingredients and nutrition in product details
        details_sections = response.css('div.prod-info-section')
        for section in details_sections:
            section_title = section.css('h2::text').get()
            if section_title:
                section_title_lower = section_title.lower()
                
                if 'ingredient' in section_title_lower:
                    item['ingredients_text'] = section.css('::text').getall()
                    item['ingredients_text'] = ' '.join(item['ingredients_text']).strip()
                    
                elif 'nutrition' in section_title_lower:
                    item['nutrition_text'] = section.css('::text').getall()
                    item['nutrition_text'] = ' '.join(item['nutrition_text']).strip()
        
        # Availability
        availability = response.css('button[qa="add"]::text').get()
        item['in_stock'] = availability and 'add' in availability.lower()
        
        # Seller info
        item['seller'] = response.css('span[qa="seller-name"]::text').get()
        
        # Ratings
        rating = response.css('span[qa="rating"]::text').get()
        if rating:
            item['rating'] = float(rating)
        
        review_count = response.css('span[qa="review-count"]::text').get()
        if review_count:
            item['review_count'] = int(''.join(filter(str.isdigit, review_count)))
        
        # Certifications (if visible)
        cert_images = response.css('img[alt*="certified"], img[alt*="organic"]')
        certifications = []
        for cert in cert_images:
            cert_text = cert.css('::attr(alt)').get()
            if cert_text:
                certifications.append(cert_text)
        item['certifications'] = certifications
        
        # Store page HTML for later processing
        item['page_html'] = response.text
        
        yield item
        
        # Look for similar products
        similar_links = response.css('div[qa="similar-products"] a::attr(href)').getall()
        for link in similar_links[:5]:  # Limit to 5 similar products
            yield response.follow(link, callback=self.parse_product)
    
    def _extract_price(self, price_text: str) -> float:
        """Extract numeric price from text"""
        try:
            # Remove currency symbol and convert to float
            price = ''.join(filter(lambda x: x.isdigit() or x == '.', price_text))
            return float(price)
        except (ValueError, AttributeError):
            return None
