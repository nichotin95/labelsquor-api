"""
BigBasket spider with Playwright for JavaScript rendering
This handles dynamic content loading
"""
import scrapy
from scrapy_playwright.page import PageMethod
import json


class BigBasketPlaywrightSpider(scrapy.Spider):
    name = 'bigbasket_playwright'
    allowed_domains = ['bigbasket.com']
    
    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'args': ['--no-sandbox']
        }
    }
    
    def start_requests(self):
        # Start with category pages that load products dynamically
        categories = [
            'https://www.bigbasket.com/pc/snacks-branded-foods/chips-crisps/',
            'https://www.bigbasket.com/pc/beverages/soft-drinks/',
            'https://www.bigbasket.com/pc/snacks-branded-foods/noodles-pasta-vermicelli/',
        ]
        
        for url in categories:
            yield scrapy.Request(
                url,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        # Wait for products to load
                        PageMethod('wait_for_selector', 'div[qa="product"]'),
                        # Scroll to trigger lazy loading
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 2000),  # Wait 2 seconds
                        # Scroll again to load more
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 2000),
                    ],
                },
                callback=self.parse_category_with_js
            )
    
    def parse_category_with_js(self, response):
        """Parse category page after JavaScript execution"""
        # Now we should have all dynamically loaded products
        products = response.css('div[qa="product"]')
        
        self.logger.info(f"Found {len(products)} products on {response.url}")
        
        for product in products:
            # Extract product URL
            product_url = product.css('a::attr(href)').get()
            if product_url:
                full_url = response.urljoin(product_url)
                
                # Extract basic info from the listing
                yield {
                    'url': full_url,
                    'name': product.css('[qa="product-name"]::text').get(),
                    'brand': product.css('[qa="product-brand"]::text').get(),
                    'price': product.css('[qa="price"]::text').re_first(r'[\d.]+'),
                    'discovery_method': 'playwright_category',
                    'type': 'product_summary'
                }
                
                # Follow to product detail page
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_product,
                    meta={
                        'playwright': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_selector', 'h1'),  # Wait for product title
                        ]
                    }
                )
        
        # Check for "Load More" button
        load_more_button = response.css('button:contains("Load More")')
        if load_more_button:
            # Click load more and parse again
            yield scrapy.Request(
                response.url,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('click', 'button:contains("Load More")'),
                        PageMethod('wait_for_timeout', 3000),
                    ],
                },
                callback=self.parse_category_with_js,
                dont_filter=True  # Allow revisiting the same URL
            )
    
    def parse_product(self, response):
        """Parse product detail page"""
        # Extract comprehensive product information
        product = {
            'url': response.url,
            'name': response.css('h1::text').get(),
            'brand': response.css('[class*="brand"]::text').get(),
            'images': response.css('img[class*="product"]::attr(src)').getall(),
            'discovery_method': 'playwright_detail',
            'type': 'product_detail'
        }
        
        # Look for ingredients and nutrition in various places
        info_sections = response.css('div[class*="info"], div[class*="details"], div[class*="description"]')
        
        for section in info_sections:
            section_text = ' '.join(section.css('::text').getall())
            if 'ingredient' in section_text.lower():
                product['ingredients_text'] = section_text
            elif 'nutrition' in section_text.lower():
                product['nutrition_text'] = section_text
        
        yield product
