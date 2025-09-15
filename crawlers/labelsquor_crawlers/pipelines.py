"""
Scrapy pipelines to process and send data to LabelSquor API
"""
import httpx
from datetime import datetime
from typing import Dict, Any
import hashlib
import json
from tenacity import retry, stop_after_attempt, wait_exponential

from scrapy import Spider
from scrapy.exceptions import DropItem
from itemadapter import ItemAdapter


class ValidationPipeline:
    """Validate and clean scraped items"""
    
    def process_item(self, item, spider: Spider):
        adapter = ItemAdapter(item)
        
        # Required fields
        if not adapter.get('name') or not adapter.get('url'):
            raise DropItem(f"Missing required fields: {item}")
        
        # Clean and normalize
        adapter['name'] = adapter.get('name', '').strip()
        adapter['brand'] = adapter.get('brand', '').strip()
        
        # Ensure lists
        for field in ['images', 'breadcrumbs', 'certifications']:
            if adapter.get(field) and not isinstance(adapter[field], list):
                adapter[field] = [adapter[field]]
        
        # Add timestamp
        adapter['crawled_at'] = datetime.utcnow().isoformat()
        
        return item


class LabelSquorAPIPipeline:
    """Send scraped data to LabelSquor API"""
    
    def __init__(self, api_url: str, api_key: str = None):
        self.api_url = api_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {}
        )
        self.session = None
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            api_url=crawler.settings.get('LABELSQUOR_API_URL', 'http://localhost:8000'),
            api_key=crawler.settings.get('LABELSQUOR_API_KEY')
        )
    
    async def open_spider(self, spider: Spider):
        """Initialize crawl session"""
        try:
            # Create crawl session
            response = await self.client.post(
                f"{self.api_url}/api/v1/crawler/sessions",
                json={
                    "retailer": spider.name,
                    "spider_version": getattr(spider, 'version', '1.0')
                }
            )
            response.raise_for_status()
            self.session = response.json()
            spider.logger.info(f"Created crawl session: {self.session['session_id']}")
        except Exception as e:
            spider.logger.error(f"Failed to create session: {e}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def process_item(self, item, spider: Spider):
        """Send item to API"""
        adapter = ItemAdapter(item)
        
        # Prepare data for API
        product_data = {
            "source_page": {
                "url": adapter['url'],
                "retailer": adapter['retailer'],
                "title": adapter.get('name'),
                "extracted_data": {
                    "name": adapter.get('name'),
                    "brand": adapter.get('brand'),
                    "price": adapter.get('price'),
                    "mrp": adapter.get('mrp'),
                    "images": adapter.get('images', []),
                    "description": adapter.get('description'),
                    "ingredients_text": adapter.get('ingredients_text'),
                    "nutrition_text": adapter.get('nutrition_text'),
                    "breadcrumbs": adapter.get('breadcrumbs', []),
                    "in_stock": adapter.get('in_stock', True),
                    "seller": adapter.get('seller'),
                    "rating": adapter.get('rating'),
                    "review_count": adapter.get('review_count'),
                    "pack_size": adapter.get('pack_size'),
                    "unit": adapter.get('unit'),
                    "certifications": adapter.get('certifications', [])
                },
                "crawl_session_id": self.session['session_id'] if self.session else None
            }
        }
        
        # Calculate content hash
        content_hash = hashlib.sha256(
            json.dumps(product_data['source_page']['extracted_data'], sort_keys=True).encode()
        ).hexdigest()
        
        product_data['source_page']['content_hash'] = content_hash
        
        try:
            # Send to API
            response = await self.client.post(
                f"{self.api_url}/api/v1/crawler/products",
                json=product_data
            )
            response.raise_for_status()
            
            result = response.json()
            spider.logger.info(f"Sent product to API: {result.get('product_id')}")
            
            # Add API response to item for downstream pipelines
            adapter['api_product_id'] = result.get('product_id')
            adapter['api_queue_id'] = result.get('queue_id')
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                # Duplicate, not an error
                spider.logger.debug(f"Product already exists: {adapter['url']}")
            else:
                spider.logger.error(f"API error: {e.response.text}")
                raise
        except Exception as e:
            spider.logger.error(f"Failed to send to API: {e}")
            raise
        
        return item
    
    async def close_spider(self, spider: Spider):
        """Close crawl session"""
        if self.session:
            try:
                # Update session status
                await self.client.patch(
                    f"{self.api_url}/api/v1/crawler/sessions/{self.session['session_id']}",
                    json={"status": "completed"}
                )
            except Exception as e:
                spider.logger.error(f"Failed to close session: {e}")
        
        await self.client.aclose()


class CloudStoragePipeline:
    """Store HTML and images to cloud storage"""
    
    def __init__(self, storage_type: str, bucket_name: str):
        self.storage_type = storage_type
        self.bucket_name = bucket_name
        self.storage_client = None
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            storage_type=crawler.settings.get('CLOUD_STORAGE_TYPE', 'local'),
            bucket_name=crawler.settings.get('CLOUD_STORAGE_BUCKET', 'labelsquor-crawl-data')
        )
    
    def open_spider(self, spider: Spider):
        """Initialize storage client"""
        if self.storage_type == 's3':
            import boto3
            self.storage_client = boto3.client('s3')
        elif self.storage_type == 'gcs':
            from google.cloud import storage
            self.storage_client = storage.Client()
        
    async def process_item(self, item, spider: Spider):
        """Store HTML to cloud storage"""
        if self.storage_type == 'local':
            return item
        
        adapter = ItemAdapter(item)
        
        if adapter.get('page_html'):
            # Generate object key
            url_hash = hashlib.sha256(adapter['url'].encode()).hexdigest()[:16]
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            object_key = f"html/{spider.name}/{timestamp}/{url_hash}.html"
            
            try:
                if self.storage_type == 's3':
                    self.storage_client.put_object(
                        Bucket=self.bucket_name,
                        Key=object_key,
                        Body=adapter['page_html'].encode('utf-8'),
                        ContentType='text/html'
                    )
                elif self.storage_type == 'gcs':
                    bucket = self.storage_client.bucket(self.bucket_name)
                    blob = bucket.blob(object_key)
                    blob.upload_from_string(adapter['page_html'], content_type='text/html')
                
                # Add storage location to item
                adapter['html_object_key'] = object_key
                spider.logger.debug(f"Stored HTML to {object_key}")
                
            except Exception as e:
                spider.logger.error(f"Failed to store HTML: {e}")
        
        return item
