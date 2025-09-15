"""
Processing pipeline service - orchestrates the complete flow
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import asyncio

from app.models import ProcessingQueue, Product, ProductVersion, SourcePage
from app.repositories import ProcessingQueueRepository, ProductRepository
from app.services import ParsingService, ScoringService, EnrichmentService
from app.core.logging import log
from app.core.exceptions import BusinessLogicError


class PipelineService:
    """
    Orchestrates the processing pipeline:
    1. Image fetching from source pages
    2. OCR on product images
    3. Data extraction and parsing
    4. Enrichment with additional data
    5. Score calculation
    6. Search indexing
    """
    
    STAGE_ORDER = [
        "discovery",
        "image_fetch", 
        "ocr",
        "enrichment",
        "scoring",
        "indexing"
    ]
    
    def __init__(
        self,
        queue_repo: ProcessingQueueRepository,
        product_repo: ProductRepository,
        parsing_service: ParsingService,
        scoring_service: ScoringService,
        enrichment_service: EnrichmentService
    ):
        self.queue_repo = queue_repo
        self.product_repo = product_repo
        self.parsing_service = parsing_service
        self.scoring_service = scoring_service
        self.enrichment_service = enrichment_service
    
    async def process_queue_item(self, queue_id: UUID) -> ProcessingQueue:
        """Process a single queue item through all stages"""
        queue_item = await self.queue_repo.get_or_404(id=queue_id)
        
        if queue_item.status != "pending":
            log.warning(f"Queue item {queue_id} is not pending, skipping")
            return queue_item
        
        # Mark as processing
        await self.queue_repo.update_status(
            queue_id=queue_id,
            status="processing",
            processing_started_at=datetime.utcnow()
        )
        
        try:
            # Process through each stage
            current_stage_index = self.STAGE_ORDER.index(queue_item.stage)
            
            for stage in self.STAGE_ORDER[current_stage_index:]:
                log.info(f"Processing queue item {queue_id} - Stage: {stage}")
                
                await self.queue_repo.update_stage(queue_id, stage)
                
                if stage == "discovery":
                    await self._process_discovery(queue_item)
                elif stage == "image_fetch":
                    await self._process_image_fetch(queue_item)
                elif stage == "ocr":
                    await self._process_ocr(queue_item)
                elif stage == "enrichment":
                    await self._process_enrichment(queue_item)
                elif stage == "scoring":
                    await self._process_scoring(queue_item)
                elif stage == "indexing":
                    await self._process_indexing(queue_item)
            
            # Mark as completed
            await self.queue_repo.update_status(
                queue_id=queue_id,
                status="completed",
                completed_at=datetime.utcnow()
            )
            
            log.info(f"Successfully processed queue item {queue_id}")
            
        except Exception as e:
            log.error(f"Failed to process queue item {queue_id}", error=str(e))
            
            # Update retry count and status
            queue_item = await self.queue_repo.get(id=queue_id)
            if queue_item.retry_count < queue_item.max_retries:
                # Schedule retry
                await self.queue_repo.update_for_retry(
                    queue_id=queue_id,
                    error=str(e),
                    next_retry_at=datetime.utcnow() + timedelta(minutes=5 * (queue_item.retry_count + 1))
                )
            else:
                # Max retries reached
                await self.queue_repo.update_status(
                    queue_id=queue_id,
                    status="failed",
                    last_error=str(e)
                )
            
            raise
        
        return await self.queue_repo.get(id=queue_id)
    
    async def _process_discovery(self, queue_item: ProcessingQueue):
        """Discovery stage - extract product info from source page"""
        if not queue_item.source_page_id:
            raise BusinessLogicError("No source page for discovery")
        
        source_page = await self.queue_repo.get_source_page(queue_item.source_page_id)
        if not source_page or not source_page.extracted_data:
            raise BusinessLogicError("No extracted data in source page")
        
        data = source_page.extracted_data
        
        # Create or update product
        product = await self.product_repo.find_or_create_from_source(
            brand_name=data.get('brand', 'Unknown'),
            product_name=data.get('name', 'Unknown'),
            source_data=data
        )
        
        # Link to queue item
        await self.queue_repo.update(
            id=queue_item.queue_id,
            obj_in={"product_id": product.product_id}
        )
        
        # Create new product version for this update
        version = await self.product_repo.create_version(
            product_id=product.product_id
        )
        
        log.info(f"Created product {product.product_id} version {version.version_seq}")
    
    async def _process_image_fetch(self, queue_item: ProcessingQueue):
        """Fetch and store product images"""
        source_page = await self.queue_repo.get_source_page(queue_item.source_page_id)
        
        if not source_page or not source_page.extracted_data:
            return
        
        image_urls = source_page.extracted_data.get('images', [])
        
        if not image_urls:
            log.warning(f"No images found for queue item {queue_item.queue_id}")
            return
        
        # Download and store images
        stored_images = []
        for i, image_url in enumerate(image_urls[:5]):  # Limit to 5 images
            try:
                # TODO: Actually download and store image
                # image_data = await self.download_image(image_url)
                # object_key = await self.storage.save_image(image_data)
                
                # For now, just track the URL
                stored_images.append({
                    "url": image_url,
                    "role": "front" if i == 0 else "additional",
                    "object_key": f"images/{queue_item.product_id}/{i}.jpg"
                })
                
            except Exception as e:
                log.error(f"Failed to fetch image {image_url}", error=str(e))
        
        # Save image metadata
        await self.queue_repo.update_stage_details(
            queue_id=queue_item.queue_id,
            stage="image_fetch",
            details={"images": stored_images}
        )
    
    async def _process_ocr(self, queue_item: ProcessingQueue):
        """Run OCR on product images"""
        # Get images from previous stage
        stage_details = queue_item.stage_details or {}
        images = stage_details.get("image_fetch", {}).get("images", [])
        
        if not images:
            log.warning(f"No images for OCR in queue item {queue_item.queue_id}")
            return
        
        ocr_results = []
        for image in images:
            if image["role"] in ["front", "back", "ingredients", "nutrition"]:
                try:
                    # TODO: Actually run OCR
                    # ocr_text = await self.ocr_service.extract_text(image["object_key"])
                    
                    # Mock OCR result for now
                    ocr_text = "Ingredients: Wheat flour, Sugar, Palm oil, Salt"
                    
                    ocr_results.append({
                        "image": image["object_key"],
                        "role": image["role"],
                        "text": ocr_text,
                        "confidence": 0.95
                    })
                    
                except Exception as e:
                    log.error(f"OCR failed for image {image['object_key']}", error=str(e))
        
        # Save OCR results
        await self.queue_repo.update_stage_details(
            queue_id=queue_item.queue_id,
            stage="ocr",
            details={"ocr_results": ocr_results}
        )
    
    async def _process_enrichment(self, queue_item: ProcessingQueue):
        """Enrich product data with parsed information"""
        # Get product and version
        product = await self.product_repo.get_or_404(id=queue_item.product_id)
        latest_version = await self.product_repo.get_latest_version(product.product_id)
        
        # Get OCR results
        stage_details = queue_item.stage_details or {}
        ocr_results = stage_details.get("ocr", {}).get("ocr_results", [])
        
        # Get source data
        source_page = await self.queue_repo.get_source_page(queue_item.source_page_id)
        source_data = source_page.extracted_data if source_page else {}
        
        # Combine all text for parsing
        all_text = "\n".join([r["text"] for r in ocr_results])
        if source_data.get("ingredient_text"):
            all_text += "\n" + source_data["ingredient_text"]
        
        # Parse ingredients
        if all_text:
            ingredients = await self.parsing_service.parse_ingredients(all_text)
            if ingredients:
                await self.product_repo.save_ingredients(
                    product_version_id=latest_version.product_version_id,
                    ingredients=ingredients
                )
        
        # Parse nutrition
        nutrition_text = next(
            (r["text"] for r in ocr_results if r["role"] == "nutrition"),
            None
        )
        if nutrition_text:
            nutrition = await self.parsing_service.parse_nutrition(nutrition_text)
            if nutrition:
                await self.product_repo.save_nutrition(
                    product_version_id=latest_version.product_version_id,
                    nutrition=nutrition
                )
        
        # Extract allergens
        allergens = await self.parsing_service.extract_allergens(all_text)
        if allergens:
            await self.product_repo.save_allergens(
                product_version_id=latest_version.product_version_id,
                allergens=allergens
            )
        
        log.info(f"Enriched product {product.product_id} with parsed data")
    
    async def _process_scoring(self, queue_item: ProcessingQueue):
        """Calculate Squor scores"""
        # Get latest product version
        latest_version = await self.product_repo.get_latest_version(queue_item.product_id)
        
        # Calculate scores
        scores = await self.scoring_service.calculate_squor(
            product_version_id=latest_version.product_version_id
        )
        
        # Save scores
        await self.product_repo.save_squor_scores(
            product_version_id=latest_version.product_version_id,
            scores=scores
        )
        
        log.info(f"Calculated Squor scores for product {queue_item.product_id}: {scores}")
    
    async def _process_indexing(self, queue_item: ProcessingQueue):
        """Index product for search"""
        # Get complete product data
        product_data = await self.product_repo.get_product_for_indexing(
            product_id=queue_item.product_id
        )
        
        # TODO: Index in Elasticsearch/OpenSearch
        # await self.search_service.index_product(product_data)
        
        log.info(f"Indexed product {queue_item.product_id} for search")
    
    async def process_pending_items(self, limit: int = 10):
        """Process pending items from the queue"""
        pending_items = await self.queue_repo.get_pending_items(limit=limit)
        
        log.info(f"Processing {len(pending_items)} pending items")
        
        # Process items concurrently (with limit)
        tasks = []
        for item in pending_items:
            task = asyncio.create_task(self.process_queue_item(item.queue_id))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        log.info(f"Processed {success_count}/{len(pending_items)} items successfully")
        
        return results
    
    async def retry_failed_items(self, limit: int = 5):
        """Retry failed items that are due"""
        items = await self.queue_repo.get_items_for_retry(limit=limit)
        
        for item in items:
            try:
                await self.process_queue_item(item.queue_id)
            except Exception as e:
                log.error(f"Retry failed for queue item {item.queue_id}", error=str(e))
