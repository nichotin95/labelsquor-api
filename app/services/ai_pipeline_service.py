"""
AI-Enhanced Pipeline Service
Integrates crawling -> AI analysis -> database storage with proper retry mechanisms
"""

import json
import os

# Import our unified analyzer
import sys
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from PIL import Image

from app.core.database import AsyncSessionLocal
from app.core.logging import log
from app.core.exceptions import BusinessLogicError
from app.repositories import ProductRepository
from app.models import (
    AllergensV,
    CertificationsV,
    ClaimsV,
    IngredientsV,
    NutritionV,
    ProcessingQueue,
    Product,
    ProductImage,
    ProductVersion,
    SourcePage,
    SquorComponent,
    SquorScore,
)
from app.repositories.processing_queue import ProcessingQueueRepository
from app.repositories.product import ProductRepository
from app.services.image_hosting_service import image_hosting_service

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from product_analyzer import AnalysisResult, ProductAnalyzer


class AIPipelineService:
    """
    Enhanced pipeline service with AI integration
    Handles the complete flow: Crawler -> Queue -> AI Analysis -> Database
    """

    STAGE_ORDER = [
        "discovery",  # Extract basic product info from crawler
        "enrichment",  # Run Google AI analysis with image URLs
        "scoring",  # Calculate Squor scores and map data
        "indexing",  # Update search index
    ]

    def __init__(self, api_key: str):
        self.analyzer = ProductAnalyzer(api_key)
        self.queue_repo = ProcessingQueueRepository()
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def process_crawler_result(self, crawler_data: Dict[str, Any], force_reanalysis: bool = False) -> UUID:
        """
        Entry point: Receive data from crawler and create processing queue item

        Args:
            crawler_data: Raw data from Scrapy crawler containing:
                - url: Product URL
                - name: Product name
                - brand: Brand name
                - images: List of image URLs
                - extracted_data: Additional scraped data
            force_reanalysis: Force re-analysis even if content is identical

        Returns:
            UUID of created queue item
        """
        # First, create or update source_page
        source_page = await self._create_source_page(crawler_data)

        # Create queue item for processing
        queue_item = ProcessingQueue(
            source_page_id=source_page.source_page_id,
            status="pending",
            stage="discovery",
            priority=self._calculate_priority(crawler_data),
            stage_details={
                "crawler_data": crawler_data, 
                "created_at": datetime.utcnow().isoformat(),
                "force_reanalysis": force_reanalysis
            },
        )

        async with AsyncSessionLocal() as session:
            session.add(queue_item)
            await session.commit()
            await session.refresh(queue_item)

        log.info(f"Created processing queue item {queue_item.queue_id} for {crawler_data.get('url')}")
        return queue_item.queue_id

    async def process_queue_item(self, queue_id: UUID) -> ProcessingQueue:
        """Process a single queue item through all stages with proper retry handling"""
        async with AsyncSessionLocal() as session:
            queue_item = await session.get(ProcessingQueue, queue_id)
            if not queue_item:
                raise BusinessLogicError(f"Queue item {queue_id} not found")

            if queue_item.status != "pending":
                log.warning(f"Queue item {queue_id} is not pending (status: {queue_item.status})")
                return queue_item

            # Mark as processing
            queue_item.status = "processing"
            queue_item.processing_started_at = datetime.utcnow()
            await session.commit()

        try:
            # Process through each stage
            current_stage_index = self.STAGE_ORDER.index(queue_item.stage)

            for stage in self.STAGE_ORDER[current_stage_index:]:
                log.info(f"Processing {queue_id} - Stage: {stage}")

                # Update stage
                async with AsyncSessionLocal() as session:
                    queue_item = await session.get(ProcessingQueue, queue_id)
                    queue_item.stage = stage
                    await session.commit()

                # Check if this is a duplicate and should skip AI analysis
                is_duplicate = queue_item.stage_details.get("is_duplicate", False)
                
                # Process stage
                if stage == "discovery":
                    await self._process_discovery(queue_item)
                elif stage == "enrichment":
                    if is_duplicate:
                        log.info(f"Skipping AI analysis for duplicate content: {queue_item.stage_details.get('skip_reason')}")
                        # Copy existing AI results if available
                        await self._copy_existing_analysis(queue_item)
                    else:
                        analysis_result = await self._process_enrichment(queue_item)
                        queue_item.stage_details["ai_result"] = analysis_result
                        
                        # Save the AI result to database
                        async with AsyncSessionLocal() as session:
                            await session.merge(queue_item)
                            await session.commit()
                elif stage == "scoring":
                    if is_duplicate:
                        log.info(f"Skipping scoring for duplicate content")
                        # Scoring already exists for this content
                    else:
                        # Process comprehensive data storage and scoring
                        await self._process_comprehensive_analysis(queue_item)
                        await self._process_data_mapping(queue_item)
                        await self._process_scoring(queue_item)
                elif stage == "indexing":
                    await self._process_indexing(queue_item)

            # Mark as completed
            async with AsyncSessionLocal() as session:
                queue_item = await session.get(ProcessingQueue, queue_id)
                queue_item.status = "completed"
                queue_item.completed_at = datetime.utcnow()
                await session.commit()

            log.info(f"Successfully processed queue item {queue_id}")
            return queue_item

        except Exception as e:
            log.error(f"Failed to process queue item {queue_id}: {str(e)}")
            await self._handle_failure(queue_id, str(e))
            raise

    async def _process_discovery(self, queue_item: ProcessingQueue):
        """Extract basic product info and create/update product record with smart duplicate detection"""
        from app.utils.content_hash import calculate_product_content_hash
        
        crawler_data = queue_item.stage_details.get("crawler_data", {})

        # Calculate content hash for duplicate detection
        content_hash = calculate_product_content_hash(crawler_data)

        # Create temporary product repo with session
        async with AsyncSessionLocal() as session:
            product_repo = ProductRepository(session)
            
            # Find or create brand
            brand_data = crawler_data.get("brand", "Unknown")
            # Handle case where brand might be a dict from consolidation
            if isinstance(brand_data, dict):
                brand_name = brand_data.get("name", "Unknown")
            else:
                brand_name = str(brand_data) if brand_data else "Unknown"
            
            brand = await product_repo.find_or_create_brand(brand_name)

            # Generate proper product identification
            from app.utils.product_identification import create_unique_product_key, extract_retailer_product_id, generate_product_hash
            
            product_name = crawler_data.get("name", "Unknown Product")
            retailer = crawler_data.get("retailer", "")
            url = crawler_data.get("url", "")
            pack_size = crawler_data.get("pack_size", "") or crawler_data.get("weight", "")
            
            # Extract retailer product ID and generate hash
            retailer_product_id = extract_retailer_product_id(url, retailer)
            product_hash = generate_product_hash(brand_name, product_name, pack_size)
            
            # Find or create product with proper identification
            product = await product_repo.find_or_create_product(
                brand_id=brand.brand_id,
                name=product_name,
                metadata={
                    "first_seen_at": datetime.utcnow().isoformat(),
                    "source_url": url,
                    "retailer": retailer,
                    **crawler_data.get("extracted_data", {}),  # Include EAN and other extracted data
                },
                retailer_product_id=retailer_product_id,
                product_hash=product_hash
            )

            # Smart duplicate detection: Check if content has changed
            force_reanalysis = queue_item.stage_details.get("force_reanalysis", False)
            should_create, reason = await product_repo.should_create_new_version(
                product.product_id, content_hash
            )

            if should_create or force_reanalysis:
                # Create new version with content hash
                version = await product_repo.create_product_version_with_content_hash(
                    product_id=product.product_id, 
                    content_hash=content_hash,
                    source="crawler"
                )
                if force_reanalysis and not should_create:
                    log.info(f"Forced re-analysis for product {product.product_id}: Content identical but force_reanalysis=True")
                else:
                    log.info(f"Created new version for product {product.product_id}: {reason}")
                
                # Update queue item for processing
                queue_item.product_id = product.product_id
                queue_item.stage_details["product_id"] = str(product.product_id)
                queue_item.stage_details["version_id"] = str(version.product_version_id)
                queue_item.stage_details["version_seq"] = version.version_seq
                queue_item.stage_details["content_hash"] = content_hash
                queue_item.stage_details["is_duplicate"] = False
            else:
                # Content is identical, skip AI analysis
                log.info(f"Skipping duplicate analysis for product {product.product_id}: {reason}")
                
                # Find the existing version with this content
                from sqlalchemy import select, desc
                from app.models.product import ProductVersion
                
                stmt = (
                    select(ProductVersion)
                    .where(ProductVersion.product_id == product.product_id)
                    .order_by(desc(ProductVersion.version_seq))
                    .limit(1)
                )
                result = await session.execute(stmt)
                existing_version = result.scalar_one()
                
                # Update queue item to reference existing version
                queue_item.product_id = product.product_id
                queue_item.stage_details["product_id"] = str(product.product_id)
                queue_item.stage_details["version_id"] = str(existing_version.product_version_id)
                queue_item.stage_details["version_seq"] = existing_version.version_seq
                queue_item.stage_details["content_hash"] = content_hash
                queue_item.stage_details["is_duplicate"] = True
                queue_item.stage_details["skip_reason"] = reason
        
        # Save the updated queue item to persist stage_details
        async with AsyncSessionLocal() as update_session:
            await update_session.merge(queue_item)
            await update_session.commit()

    async def _copy_existing_analysis(self, queue_item: ProcessingQueue):
        """Copy existing AI analysis results for duplicate content"""
        version_id = queue_item.stage_details.get("version_id")
        
        if not version_id:
            log.warning(f"No version_id found for queue item {queue_item.queue_id}")
            return
        
        # Find existing SQUOR scores for this product version
        async with AsyncSessionLocal() as session:
            from app.models import SquorScore
            from sqlalchemy import select
            
            stmt = select(SquorScore).where(SquorScore.product_version_id == UUID(version_id))
            result = await session.execute(stmt)
            existing_scores = result.scalars().all()
            
            if existing_scores:
                # Create a mock AI result based on existing scores
                latest_score = existing_scores[-1]  # Get most recent
                
                mock_ai_result = {
                    "raw_data": {
                        "squor": {
                            "s": latest_score.score_json.get("original_scores", {}).get("safety", 0),
                            "q": latest_score.score_json.get("original_scores", {}).get("quality", 0),
                            "u": latest_score.score_json.get("original_scores", {}).get("usability", 0),
                            "o": latest_score.score_json.get("original_scores", {}).get("origin", 0),
                            "r": latest_score.score_json.get("original_scores", {}).get("responsibility", 0),
                            "reasons": {
                                # Get reasons from components if available
                                "s": "Previous analysis - content unchanged",
                                "q": "Previous analysis - content unchanged", 
                                "u": "Previous analysis - content unchanged",
                                "o": "Previous analysis - content unchanged",
                                "r": "Previous analysis - content unchanged"
                            }
                        }
                    },
                    "usage": {"cost": 0.0, "tokens": 0, "requests": 0},
                    "duplicate_analysis": True
                }
                
                queue_item.stage_details["ai_result"] = mock_ai_result
                log.info(f"Copied existing analysis for duplicate content (score: {latest_score.score})")
            else:
                log.warning(f"No existing analysis found for version {version_id}, will skip processing")

    async def _process_comprehensive_analysis(self, queue_item: ProcessingQueue):
        """Save comprehensive AI analysis data to database"""
        from app.services.ai_analysis_service import AIAnalysisService
        
        ai_result = queue_item.stage_details.get("ai_result", {})
        version_id = queue_item.stage_details.get("version_id")
        
        if not ai_result or not version_id:
            log.warning(f"No AI result or version ID found for comprehensive analysis")
            return
        
        async with AsyncSessionLocal() as session:
            analysis_service = AIAnalysisService(session)
            
            try:
                analysis = await analysis_service.save_comprehensive_analysis(
                    product_version_id=UUID(version_id),
                    ai_result=ai_result
                )
                
                # Store analysis ID in queue item for reference
                queue_item.stage_details["analysis_id"] = str(analysis.analysis_id)
                
                log.info(f"Saved comprehensive analysis {analysis.analysis_id} for queue item {queue_item.queue_id}")
                
            except Exception as e:
                log.error(f"Failed to save comprehensive analysis: {str(e)}")
                # Don't fail the entire pipeline, just log the error
                pass

    async def _process_image_fetch(self, queue_item: ProcessingQueue) -> List[Dict[str, Any]]:
        """Download and categorize product images"""
        crawler_data = queue_item.stage_details.get("crawler_data", {})
        image_urls = crawler_data.get("images", [])

        downloaded_images = []

        for idx, url in enumerate(image_urls[:5]):  # Limit to 5 images
            try:
                # Download image
                response = await self.http_client.get(url)
                response.raise_for_status()

                # Open with PIL to validate
                img = Image.open(BytesIO(response.content))

                # Categorize image (heuristic based on order)
                if idx == 0:
                    role = "front"
                elif idx == 1:
                    role = "back"
                elif idx == 2:
                    role = "nutrition"
                else:
                    role = f"side_{idx-2}"

                # Store image metadata
                image_data = {
                    "url": url,
                    "role": role,
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "size_bytes": len(response.content),
                    "image_bytes": response.content,  # Keep in memory for AI
                }
                downloaded_images.append(image_data)

                # Save to database
                await self._save_product_image(product_id=queue_item.product_id, image_data=image_data)

            except Exception as e:
                log.error(f"Failed to download image {url}: {str(e)}")

        return downloaded_images

    async def _process_enrichment(self, queue_item: ProcessingQueue) -> Dict[str, Any]:
        """Run AI analysis using image URLs directly"""
        crawler_data = queue_item.stage_details.get("crawler_data", {})
        image_urls = crawler_data.get("images", [])
        
        if not image_urls:
            log.warning("No images available for AI analysis, skipping")
            return {}

        # Check token limits before proceeding
        can_proceed, message, limits = self.analyzer.check_limits()
        if not can_proceed:
            raise BusinessLogicError(f"AI analysis limit reached: {message}")

        # Run analysis with URLs directly
        product_url = crawler_data.get("url", "")
        
        # Call the analyzer with image URLs - Gemini will fetch them
        result = await self.analyzer.analyze_product_from_urls(
            image_urls=image_urls[:5],  # Limit to 5 images
            product_url=product_url,
            product_info=crawler_data,  # Pass all crawler data for context
            mode="standard"
        )

        # Log usage
        log.info(f"AI Analysis completed - Tokens: {result.tokens_used}, Cost: ${result.cost_estimate:.4f}")

        # Handle best image selection and upload
        best_image_info = result.raw_data.get("best_image", {})
        best_image_index = best_image_info.get("index", 1) - 1  # Convert to 0-based
        best_image_reason = best_image_info.get("reason", "No AI selection available")
        
        # Fallback: if AI didn't select an image, use the first one
        if not best_image_info and image_urls:
            best_image_index = 0
            best_image_reason = "Fallback: selected first available image"
            log.info(f"AI didn't select best image, using first image as fallback")
        
        if 0 <= best_image_index < len(image_urls):
            best_image_url = image_urls[best_image_index]
            
            # Upload to our storage
            hosted_url = await image_hosting_service.upload_image_from_url(
                image_url=best_image_url,
                product_id=str(queue_item.product_id),
                image_type="primary"
            )
            
            if hosted_url:
                # Update product with primary image
                async with AsyncSessionLocal() as session:
                    product = await session.get(Product, queue_item.product_id)
                    if product:
                        product.primary_image_url = hosted_url
                        product.primary_image_source = crawler_data.get("retailer", "unknown")
                        await session.commit()
                        log.info(f"Updated product {queue_item.product_id} with primary image: {hosted_url}")
            
            # Add to result for tracking
            if "best_image" not in result.raw_data:
                result.raw_data["best_image"] = {}
            result.raw_data["best_image"]["selected_url"] = best_image_url
            result.raw_data["best_image"]["hosted_url"] = hosted_url
            result.raw_data["best_image"]["reason"] = best_image_reason

        # Return serializable data
        return {
            "consumer_data": result.consumer_data,
            "brand_data": result.brand_data,
            "raw_data": result.raw_data,
            "tokens_used": result.tokens_used,
            "cost_estimate": result.cost_estimate,
            "processing_time": result.processing_time,
        }

    async def _process_data_mapping(self, queue_item: ProcessingQueue):
        """Map AI analysis results to database schema"""
        ai_result = queue_item.stage_details.get("ai_result", {})
        raw_data = ai_result.get("raw_data", {})
        brand_data = ai_result.get("brand_data", {})

        version_id = UUID(queue_item.stage_details["version_id"])

        # Save ingredients
        ingredients_list = raw_data.get("ingredients", [])
        if ingredients_list:
            await self._save_ingredients(version_id, ingredients_list, raw_data)

        # Save nutrition
        nutrition = raw_data.get("nutrition", {})
        if nutrition:
            await self._save_nutrition(version_id, nutrition)

        # Save allergens
        allergens = raw_data.get("warnings", [])
        await self._save_allergens(version_id, allergens)

        # Save claims
        claims = raw_data.get("claims", [])
        if claims:
            await self._save_claims(version_id, claims)

        # Save certifications
        certs = raw_data.get("certifications", [])
        if certs:
            await self._save_certifications(version_id, certs)

    async def _process_scoring(self, queue_item: ProcessingQueue):
        """Calculate and save Squor scores with reasoning"""
        ai_result = queue_item.stage_details.get("ai_result", {})
        raw_data = ai_result.get("raw_data", {})
        
        # Handle new SQUOR format from Gemini
        squor_data = raw_data.get("squor", {})
        if squor_data:
            # Map new format: s, q, u, o, r -> safety, quality, usability, origin, responsibility
            scores_data = {
                "safety": squor_data.get("s", 0),
                "quality": squor_data.get("q", 0), 
                "usability": squor_data.get("u", 0),
                "origin": squor_data.get("o", 0),
                "responsibility": squor_data.get("r", 0)
            }
            # Map reasons from s,q,u,o,r keys to full names
            raw_reasons = squor_data.get("reasons", {})
            score_reasons = {
                "safety": raw_reasons.get("s", ""),
                "quality": raw_reasons.get("q", ""),
                "usability": raw_reasons.get("u", ""),
                "origin": raw_reasons.get("o", ""),
                "responsibility": raw_reasons.get("r", "")
            }
        else:
            # Fallback to old format
            scores_data = raw_data.get("scores", {})
            score_reasons = raw_data.get("score_reasons", {})
        
        version_id = UUID(queue_item.stage_details["version_id"])

        # Calculate weighted total score (convert 0-5 scale to 0-100)
        weights = {"safety": 0.25, "quality": 0.25, "usability": 0.15, "origin": 0.15, "responsibility": 0.20}
        
        # Convert 0-5 scores to 0-100 scale
        scaled_scores = {k: v * 20 for k, v in scores_data.items()}  # 5 * 20 = 100
        total_score = sum(scaled_scores.get(comp, 0) * weights.get(comp, 0.2) for comp in weights.keys())

        async with AsyncSessionLocal() as session:
            squor_score = SquorScore(
                product_version_id=version_id,
                scheme="SQUOR_V2",
                score=total_score,
                grade=self._get_grade(total_score),
                score_json={"components": scaled_scores, "weights": weights, "method": "ai_v2", "confidence": 0.85, "original_scores": scores_data},
            )
            session.add(squor_score)
            await session.commit()
            await session.refresh(squor_score)

            # Add SQUOR component scores with reasoning
            for component, score in scaled_scores.items():
                comp = SquorComponent(
                    squor_id=squor_score.squor_id,
                    component_key=component,
                    value=score,  # Already scaled to 0-100
                    weight=weights.get(component, 0.2),
                    explain_md=score_reasons.get(component, ""),
                )
                session.add(comp)

            await session.commit()

            # Save claims analysis and flags
            await self._save_claims_analysis(version_id, raw_data)

    async def _process_indexing(self, queue_item: ProcessingQueue):
        """Update search index with analyzed data"""
        # This would integrate with your search service
        # For now, just log completion
        log.info(f"Indexed product {queue_item.product_id} for search")

    # Helper methods
    async def _create_source_page(self, crawler_data: Dict[str, Any]) -> SourcePage:
        """Create or update source page record"""
        async with AsyncSessionLocal() as session:
            # Check if exists
            stmt = select(SourcePage).where(SourcePage.url == crawler_data["url"])
            result = await session.execute(stmt)
            source_page = result.scalar_one_or_none()

            if source_page:
                # Update existing
                source_page.last_crawled_at = datetime.utcnow()
                source_page.extracted_data = crawler_data
                source_page.title = crawler_data.get("name", "")
            else:
                # Create new
                # Handle consolidated products that have 'sources' instead of 'retailer'
                retailer_code = crawler_data.get("retailer")
                if not retailer_code and crawler_data.get("sources"):
                    # For consolidated products, use the first source
                    retailer_code = crawler_data["sources"][0]
                    
                retailer_id = await self._get_retailer_id(retailer_code)
                if not retailer_id:
                    log.warning(f"Could not find retailer for code: {retailer_code}")
                    # Skip creating source_page if no retailer found
                    return None
                    
                source_page = SourcePage(
                    url=crawler_data["url"],
                    title=crawler_data.get("name", ""),
                    extracted_data=crawler_data,
                    last_crawled_at=datetime.utcnow(),
                    retailer_id=retailer_id,
                )
                session.add(source_page)

            await session.commit()
            await session.refresh(source_page)
            return source_page

    async def _save_ingredients(self, version_id: UUID, ingredients: List[str], raw_data: Dict):
        """Save ingredients with SCD2 versioning"""
        async with AsyncSessionLocal() as session:
            # Close previous version
            stmt = (
                update(IngredientsV)
                .where(IngredientsV.product_version_id == version_id, IngredientsV.is_current == True)
                .values(is_current=False, valid_to=datetime.utcnow())
            )
            await session.execute(stmt)

            # Create new version
            ingredients_v = IngredientsV(
                product_version_id=version_id,
                raw_text=", ".join(ingredients),
                normalized_list_json=ingredients,
                tree_json=self._build_ingredient_tree(ingredients),
                confidence=0.9,
                valid_from=datetime.utcnow(),
                is_current=True,
            )
            session.add(ingredients_v)
            await session.commit()

    async def _save_nutrition(self, version_id: UUID, nutrition: Dict[str, Any]):
        """Save nutrition facts with SCD2 versioning"""
        async with AsyncSessionLocal() as session:
            # Close previous version
            stmt = (
                update(NutritionV)
                .where(NutritionV.product_version_id == version_id, NutritionV.is_current == True)
                .values(is_current=False, valid_to=datetime.utcnow())
            )
            await session.execute(stmt)

            # Create new version
            nutrition_v = NutritionV(
                product_version_id=version_id,
                per_100g_json=nutrition.get("per_100g", {}),
                per_serving_json=nutrition.get("per_serving", {}),
                serving_size=nutrition.get("serving_size", ""),
                confidence=0.85,
                valid_from=datetime.utcnow(),
                is_current=True,
            )
            session.add(nutrition_v)
            await session.commit()

    async def _save_allergens(self, version_id: UUID, warnings: List[str]):
        """Extract and save allergen information"""
        # Extract allergens from warnings
        common_allergens = ["milk", "wheat", "soy", "nuts", "eggs", "fish", "shellfish"]
        declared = []
        may_contain = []

        for warning in warnings:
            if not isinstance(warning, str):
                continue
            warning_lower = warning.lower()
            for allergen in common_allergens:
                if allergen in warning_lower:
                    if "may contain" in warning_lower:
                        may_contain.append(allergen)
                    else:
                        declared.append(allergen)

        if declared or may_contain:
            async with AsyncSessionLocal() as session:
                # Close previous version
                stmt = (
                    update(AllergensV)
                    .where(AllergensV.product_version_id == version_id, AllergensV.is_current == True)
                    .values(is_current=False, valid_to=datetime.utcnow())
                )
                await session.execute(stmt)

                # Create new version
                allergens_v = AllergensV(
                    product_version_id=version_id,
                    declared_list=declared,
                    may_contain_list=may_contain,
                    confidence=0.8,
                    valid_from=datetime.utcnow(),
                    is_current=True,
                )
                session.add(allergens_v)
                await session.commit()

    async def _handle_failure(self, queue_id: UUID, error: str):
        """Handle processing failure with retry logic"""
        async with AsyncSessionLocal() as session:
            queue_item = await session.get(ProcessingQueue, queue_id)

            queue_item.retry_count += 1
            queue_item.last_error = error
            queue_item.error_details = {
                "error": error,
                "failed_at": datetime.utcnow().isoformat(),
                "stage": queue_item.stage,
            }

            if queue_item.retry_count < queue_item.max_retries:
                # Schedule retry with exponential backoff
                queue_item.status = "pending"
                queue_item.next_retry_at = datetime.utcnow() + timedelta(minutes=5 * (2**queue_item.retry_count))
                log.info(f"Scheduled retry {queue_item.retry_count} for {queue_id}")
            else:
                # Max retries exceeded
                queue_item.status = "failed"
                log.error(f"Max retries exceeded for {queue_id}")

            await session.commit()

    def _calculate_priority(self, crawler_data: Dict) -> int:
        """Calculate processing priority based on various factors"""
        priority = 5  # Default medium priority

        # Higher priority for popular brands
        brand = crawler_data.get("brand", "")
        if isinstance(brand, str):
            brand = brand.lower()
            if any(b in brand for b in ["nestle", "hindustan unilever", "itc", "britannia"]):
                priority += 2

        # Higher priority for products with images
        if len(crawler_data.get("images", [])) > 2:
            priority += 1

        # Cap at 10
        return min(priority, 10)

    def _build_ingredient_tree(self, ingredients: List[str]) -> Dict:
        """Build hierarchical ingredient tree (simplified)"""
        return {
            "main_ingredients": ingredients[:3] if len(ingredients) > 3 else ingredients,
            "additives": [
                i
                for i in ingredients
                if isinstance(i, str) and any(marker in i.lower() for marker in ["e", "ins", "stabilizer", "emulsifier"])
            ],
            "allergens": [
                i for i in ingredients if isinstance(i, str) and any(allergen in i.lower() for allergen in ["milk", "wheat", "soy", "nuts"])
            ],
        }

    async def _get_retailer_id(self, retailer_code: str) -> Optional[UUID]:
        """Get retailer ID from code"""
        if not retailer_code:
            return None
            
        async with AsyncSessionLocal() as session:
            from app.models.retailer import Retailer
            stmt = select(Retailer).where(Retailer.code == retailer_code)
            result = await session.execute(stmt)
            retailer = result.scalar_one_or_none()
            return retailer.retailer_id if retailer else None

    def _get_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 80:
            return "A"
        elif score >= 60:
            return "B"
        elif score >= 40:
            return "C"
        elif score >= 20:
            return "D"
        else:
            return "F"

    async def _save_product_image(self, product_id: UUID, image_data: Dict):
        """Save product image record"""
        async with AsyncSessionLocal() as session:
            # Check if image already exists by URL
            stmt = select(ProductImage).where(
                ProductImage.product_id == product_id, ProductImage.url == image_data["url"]
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                product_image = ProductImage(
                    product_id=product_id,
                    url=image_data["url"],
                    role=image_data["role"],
                    width=image_data["width"],
                    height=image_data["height"],
                    created_at=datetime.utcnow(),
                )
                session.add(product_image)
                await session.commit()

    async def _save_claims(self, version_id: UUID, claims: List[str]):
        """Save raw product claims"""
        async with AsyncSessionLocal() as session:
            claims_v = ClaimsV(
                product_version_id=version_id, claims_json={"claims": claims}, source="ai_extraction", confidence=0.85
            )
            session.add(claims_v)
            await session.commit()

    async def _save_certifications(self, version_id: UUID, certs: List[str]):
        """Save product certifications"""
        async with AsyncSessionLocal() as session:
            for cert_name in certs:
                cert = CertificationsV(
                    product_version_id=version_id,
                    scheme=cert_name,
                    issuer="Unknown",  # Can be enhanced with proper parsing
                    valid_from=datetime.utcnow(),
                )
                session.add(cert)
            await session.commit()

    async def _save_claims_analysis(self, version_id: UUID, raw_data: Dict[str, Any]):
        """Save enhanced claims analysis with good/bad/misleading categorization"""
        claims_analysis = raw_data.get("claims_analysis", {})
        red_flags = raw_data.get("red_flags", [])
        green_flags = raw_data.get("green_flags", [])

        if not claims_analysis and not red_flags and not green_flags:
            return

        async with AsyncSessionLocal() as session:
            # Check if analysis already exists
            stmt = """
                INSERT INTO claim_analysis (
                    product_version_id,
                    good_claims,
                    bad_claims,
                    misleading_claims,
                    red_flags,
                    green_flags,
                    claims_summary,
                    confidence_score,
                    analyzer_version
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (product_version_id) 
                DO UPDATE SET
                    good_claims = EXCLUDED.good_claims,
                    bad_claims = EXCLUDED.bad_claims,
                    misleading_claims = EXCLUDED.misleading_claims,
                    red_flags = EXCLUDED.red_flags,
                    green_flags = EXCLUDED.green_flags,
                    analyzed_at = NOW()
            """

            # Generate summary
            num_good = len(claims_analysis.get("good_claims", []))
            num_bad = len(claims_analysis.get("bad_claims", []))
            num_misleading = len(claims_analysis.get("misleading_claims", []))

            summary = f"Analyzed {num_good + num_bad + num_misleading} claims: "
            summary += f"{num_good} valid, {num_bad} problematic, {num_misleading} misleading"

            await session.execute(
                stmt,
                version_id,
                json.dumps(claims_analysis.get("good_claims", [])),
                json.dumps(claims_analysis.get("bad_claims", [])),
                json.dumps(claims_analysis.get("misleading_claims", [])),
                red_flags,
                green_flags,
                summary,
                0.85,  # confidence score
                "ai_v1",  # analyzer version
            )


# Add missing import
from sqlalchemy import select, update
