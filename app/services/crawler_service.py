"""
Web crawler service for retailer product pages
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
import asyncio
import httpx
from bs4 import BeautifulSoup
import hashlib

from app.repositories import RetailerRepository, SourcePageRepository, ProcessingQueueRepository
from app.models import Retailer, CrawlSession, SourcePage, ProcessingQueue
from app.core.logging import log
from app.core.exceptions import ExternalServiceError
from app.utils.normalization import normalize_text


class CrawlerService:
    """Service for crawling retailer websites"""
    
    def __init__(
        self,
        retailer_repo: RetailerRepository,
        source_page_repo: SourcePageRepository,
        processing_queue_repo: ProcessingQueueRepository
    ):
        self.retailer_repo = retailer_repo
        self.source_page_repo = source_page_repo
        self.queue_repo = processing_queue_repo
        
        # HTTP client with retries
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; LabelSquor/1.0)"
            },
            follow_redirects=True
        )
    
    async def crawl_retailer(self, retailer_code: str) -> CrawlSession:
        """Crawl a specific retailer"""
        retailer = await self.retailer_repo.get_by_code(retailer_code)
        if not retailer:
            raise ValueError(f"Retailer {retailer_code} not found")
        
        # Create crawl session
        session = await self.retailer_repo.create_crawl_session(retailer.retailer_id)
        
        try:
            # Start crawling based on retailer config
            if retailer_code == "bigbasket":
                await self._crawl_bigbasket(retailer, session)
            elif retailer_code == "blinkit":
                await self._crawl_blinkit(retailer, session)
            elif retailer_code == "zepto":
                await self._crawl_zepto(retailer, session)
            elif retailer_code == "amazon_in":
                await self._crawl_amazon_in(retailer, session)
            else:
                raise NotImplementedError(f"Crawler not implemented for {retailer_code}")
            
            # Mark session as completed
            await self.retailer_repo.complete_crawl_session(session.session_id)
            
        except Exception as e:
            log.error(f"Crawl failed for {retailer_code}", error=str(e))
            await self.retailer_repo.fail_crawl_session(session.session_id, str(e))
            raise
        
        return session
    
    async def _crawl_bigbasket(self, retailer: Retailer, session: CrawlSession):
        """BigBasket specific crawler"""
        # Categories to crawl
        categories = [
            "/pc/snacks-branded-foods/chips-crisps",
            "/pc/beverages/soft-drinks",
            "/pc/dairy/milk",
            "/pc/snacks-branded-foods/biscuits-cookies",
            "/pc/bakery-cakes-dairy/breads-buns",
            "/pc/staples/atta-flours"
        ]
        
        base_url = "https://www.bigbasket.com"
        
        for category_path in categories:
            try:
                await self._crawl_category_page(
                    retailer=retailer,
                    session=session,
                    category_url=f"{base_url}{category_path}",
                    parser_type="bigbasket"
                )
                
                # Rate limiting
                await asyncio.sleep(1 / retailer.rate_limit_rps)
                
            except Exception as e:
                log.error(f"Failed to crawl category {category_path}", error=str(e))
    
    async def _crawl_category_page(
        self,
        retailer: Retailer,
        session: CrawlSession,
        category_url: str,
        parser_type: str
    ):
        """Crawl a category page and extract product URLs"""
        try:
            response = await self.client.get(category_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract product URLs based on parser type
            product_urls = []
            
            if parser_type == "bigbasket":
                # BigBasket uses specific selectors
                product_links = soup.select('div[qa="product"] a')
                product_urls = [
                    f"https://www.n .com{link['href']}" 
                    for link in product_links if link.get('href')
                ]
            
            log.info(f"Found {len(product_urls)} products in {category_url}")
            
            # Process each product URL
            for product_url in product_urls[:50]:  # Limit for testing
                await self._process_product_url(
                    retailer=retailer,
                    session=session,
                    product_url=product_url,
                    parser_type=parser_type
                )
                
                await asyncio.sleep(1 / retailer.rate_limit_rps)
                
        except Exception as e:
            log.error(f"Failed to crawl category page {category_url}", error=str(e))
    
    async def _process_product_url(
        self,
        retailer: Retailer,
        session: CrawlSession,
        product_url: str,
        parser_type: str
    ):
        """Process a single product URL"""
        try:
            # Check if we already have this URL
            existing = await self.source_page_repo.get_by_url(product_url)
            
            if existing and existing.last_crawled_at:
                # Skip if crawled recently (within 7 days)
                if existing.last_crawled_at > datetime.utcnow() - timedelta(days=7):
                    return
            
            # Fetch the page
            response = await self.client.get(product_url)
            response.raise_for_status()
            
            # Parse product data
            product_data = await self._parse_product_page(
                html=response.text,
                parser_type=parser_type
            )
            
            if not product_data:
                return
            
            # Create or update source page
            source_page = await self._save_source_page(
                retailer=retailer,
                session=session,
                url=product_url,
                html=response.text,
                product_data=product_data
            )
            
            # Add to processing queue
            await self.queue_repo.create_queue_item(
                product_id=source_page.product_id,
                source_page_id=source_page.source_page_id,
                priority=7  # High priority for new products
            )
            
            # Update session metrics
            await self.retailer_repo.increment_session_metrics(
                session_id=session.session_id,
                pages_processed=1,
                products_found=1,
                products_new=1 if not existing else 0
            )
            
        except Exception as e:
            log.error(f"Failed to process product URL {product_url}", error=str(e))
            await self.retailer_repo.increment_session_metrics(
                session_id=session.session_id,
                errors_count=1
            )
    
    async def _parse_product_page(
        self,
        html: str,
        parser_type: str
    ) -> Optional[Dict[str, Any]]:
        """Parse product data from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        if parser_type == "bigbasket":
            return self._parse_bigbasket_product(soup)
        
        return None
    
    def _parse_bigbasket_product(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse BigBasket product page"""
        data = {}
        
        try:
            # Product name
            name_elem = soup.select_one('h1')
            if name_elem:
                data['name'] = name_elem.text.strip()
            
            # Brand
            brand_elem = soup.select_one('a[qa="pd-brand"]')
            if brand_elem:
                data['brand'] = brand_elem.text.strip()
            
            # Price
            price_elem = soup.select_one('td[qa="price"]')
            if price_elem:
                data['price'] = float(price_elem.text.replace('₹', '').strip())
            
            # Images
            image_elems = soup.select('img[qa="pd-image"]')
            data['images'] = [img['src'] for img in image_elems if img.get('src')]
            
            # Description
            desc_elem = soup.select_one('div[qa="pd-details"]')
            if desc_elem:
                data['description'] = desc_elem.text.strip()
            
            # Extract potential ingredient text
            for section in soup.select('div.prod-info-section'):
                text = section.text.lower()
                if 'ingredient' in text or 'composition' in text:
                    data['ingredient_text'] = section.text.strip()
                    break
            
        except Exception as e:
            log.error("Failed to parse BigBasket product", error=str(e))
        
        return data
    
    async def _save_source_page(
        self,
        retailer: Retailer,
        session: CrawlSession,
        url: str,
        html: str,
        product_data: Dict[str, Any]
    ) -> SourcePage:
        """Save or update source page"""
        # Calculate hashes
        html_hash = hashlib.sha256(html.encode()).hexdigest()
        content_hash = hashlib.sha256(str(product_data).encode()).hexdigest()
        
        # Create/update source page
        source_page_data = {
            "retailer_id": retailer.retailer_id,
            "crawl_session_id": session.session_id,
            "url": url,
            "title": product_data.get('name'),
            "html_hash": html_hash,
            "content_hash": content_hash,
            "extracted_data": product_data,
            "last_crawled_at": datetime.utcnow(),
            "status_code": 200
        }
        
        # TODO: Save HTML to object storage
        # source_page_data["html_object_key"] = await self.storage.save_html(html)
        
        # Check if product exists or create new
        product = await self._find_or_create_product(product_data)
        if product:
            source_page_data["product_id"] = product.product_id
        
        # Save source page
        source_page = await self.source_page_repo.upsert_by_url(
            url=url,
            data=source_page_data
        )
        
        return source_page
    
    async def _find_or_create_product(self, product_data: Dict[str, Any]):
        """Find existing product or create placeholder"""
        # This is simplified - in reality you'd have more sophisticated matching
        brand_name = product_data.get('brand', 'Unknown')
        product_name = product_data.get('name', 'Unknown')
        
        # TODO: Implement product matching/creation logic
        # For now, return None and let the processing pipeline create products
        return None
    
    async def schedule_retailers(self):
        """Schedule all active retailers for crawling"""
        retailers = await self.retailer_repo.get_retailers_due_for_crawl()
        
        for retailer in retailers:
            log.info(f"Scheduling crawl for {retailer.name}")
            # Add to task queue (Celery/Dramatiq)
            # For now, just update next crawl time
            await self.retailer_repo.update_next_crawl_time(
                retailer_id=retailer.retailer_id,
                next_crawl_at=datetime.utcnow() + timedelta(hours=retailer.crawl_frequency_hours)
            )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
