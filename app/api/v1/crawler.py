"""
Crawler API endpoints for triggering product discovery and analysis
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_session, AsyncSessionLocal
from app.core.logging import log
from app.models import CrawlSession, Product, Retailer, SourcePage
from app.services.ai_pipeline_service import AIPipelineService
from app.services.discovery_orchestrator import DiscoveryOrchestrator
from app.services.product_consolidator import ProductConsolidator

router = APIRouter(prefix="/crawler", tags=["crawler"])


# Request/Response schemas
class CategoryCrawlRequest(BaseModel):
    """Request to crawl a category across retailers"""

    category: str = Field(..., description="Category to crawl (e.g., 'snacks', 'beverages')")
    retailers: Optional[List[str]] = Field(default=["bigbasket", "blinkit", "zepto"], description="Retailers to crawl")
    max_products: int = Field(default=10, ge=1, le=100, description="Maximum products to process")
    skip_existing: bool = Field(default=True, description="Skip products already analyzed")
    consolidate_variants: bool = Field(default=True, description="Consolidate product variants")
    force_reanalysis: bool = Field(default=False, description="Force re-analysis even if content is identical")


class ProductSearchRequest(BaseModel):
    """Request to search for a specific product across retailers"""

    product_name: str = Field(..., description="Product name to search")
    brand: Optional[str] = Field(None, description="Brand name for better matching")
    retailers: Optional[List[str]] = Field(
        default=["bigbasket", "blinkit", "zepto", "amazon_in"], description="Retailers to search"
    )
    analyze_immediately: bool = Field(default=True, description="Run AI analysis immediately")


class CrawlStatusResponse(BaseModel):
    """Response for crawl status"""

    session_id: UUID
    status: str
    started_at: Optional[str] = None
    products_found: int
    products_analyzed: int
    products_skipped: int
    errors: List[Dict[str, Any]]
    message: str


class ComprehensiveProductAnalysis(BaseModel):
    """Comprehensive product analysis with all AI-extracted data"""
    
    # Product identification
    product_id: UUID
    name: str
    brand: str
    ai_category: Optional[str] = None
    
    # SQUOR Analysis
    squor_score: float
    squor_components: Dict[str, float]
    squor_explanations: Optional[Dict[str, str]] = None
    
    # AI-Extracted Data
    ingredients: Optional[List[Dict[str, Any]]] = None  # name, order, percentage
    nutrition: Optional[Dict[str, Any]] = None
    claims: Optional[List[Dict[str, Any]]] = None  # text, type, verified
    warnings: Optional[List[Dict[str, Any]]] = None  # text, type, severity
    
    # AI Analysis Metadata
    verdict: Optional[Dict[str, Any]] = None  # overall_rating, recommendation
    best_image: Optional[Dict[str, Any]] = None  # index, url, reason, hosted_url
    confidence: Optional[float] = None
    analysis_cost: Optional[float] = None
    analyzed_at: Optional[str] = None
    model_used: Optional[str] = None
    
    # System Data
    sources: List[str] = []
    analysis_status: str
    consolidated_from: int = 0


# Remove the old response model - we'll use only the comprehensive one


# Dependency injection
async def get_orchestrator(db: AsyncSession = Depends(get_session)) -> DiscoveryOrchestrator:
    """Get discovery orchestrator instance"""
    return DiscoveryOrchestrator(db)


async def get_consolidator(db: AsyncSession = Depends(get_session)) -> ProductConsolidator:
    """Get product consolidator instance"""
    return ProductConsolidator(db)


async def get_pipeline(google_api_key: str = Depends(lambda: settings.google_api_key)) -> AIPipelineService:
    """Get AI pipeline service"""
    if not google_api_key:
        raise HTTPException(status_code=500, detail="Google API key not configured")
    return AIPipelineService(google_api_key)


@router.post("/crawl/category", response_model=CrawlStatusResponse)
async def crawl_category(
    request: CategoryCrawlRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    orchestrator: DiscoveryOrchestrator = Depends(get_orchestrator),
    consolidator: ProductConsolidator = Depends(get_consolidator),
    pipeline: AIPipelineService = Depends(get_pipeline),
):
    """
    Crawl a category across multiple retailers and analyze products

    This endpoint:
    1. Triggers crawling for the category on all specified retailers
    2. Consolidates duplicate products across retailers
    3. Checks if products are already analyzed
    4. Queues new products for AI analysis
    5. Returns immediately with a session ID for tracking
    """

    # Create crawl sessions for each retailer
    sessions = []
    for retailer_code in request.retailers:
        # Find or create retailer
        retailer_query = select(Retailer).where(Retailer.code == retailer_code)
        result = db.execute(retailer_query)
        retailer = result.scalar_one_or_none()
        
        if not retailer:
            # Create retailer if it doesn't exist
            retailer = Retailer(
                code=retailer_code,
                name=retailer_code.title(),
                domain=f"{retailer_code}.com",
                country="IN"
            )
            db.add(retailer)
            db.commit()
            db.refresh(retailer)
        
        # Create session for this retailer
        session = CrawlSession(
            retailer_id=retailer.retailer_id,
            status="running",
            metadata={"category": request.category, "max_products": request.max_products},
        )
        db.add(session)
        sessions.append(session)
    
    db.commit()
    
    # Use the first session as the primary one for response
    primary_session = sessions[0] if sessions else None
    if primary_session:
        db.refresh(primary_session)

    # Start background processing (pass all session IDs)
    session_ids = [s.session_id for s in sessions]
    background_tasks.add_task(
        _process_category_crawl,
        session_ids=session_ids,
        request=request,
        orchestrator=orchestrator,
        consolidator=consolidator,
        pipeline=pipeline,
    )

    return CrawlStatusResponse(
        session_id=primary_session.session_id if primary_session else UUID("00000000-0000-0000-0000-000000000000"),
        status="started",
        started_at=primary_session.started_at.isoformat() if primary_session and primary_session.started_at else datetime.utcnow().isoformat(),
        products_found=0,
        products_analyzed=0,
        products_skipped=0,
        errors=[],
        message=f"Started crawling '{request.category}' across {len(request.retailers)} retailers",
    )


@router.post("/search/product", response_model=ComprehensiveProductAnalysis)
async def search_and_analyze_product(
    request: ProductSearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    consolidator: ProductConsolidator = Depends(get_consolidator),
    pipeline: AIPipelineService = Depends(get_pipeline),
):
    """
    Search for a specific product across retailers and analyze it

    This endpoint:
    1. Searches for the product on all specified retailers
    2. Consolidates data from multiple sources
    3. Checks if already analyzed
    4. Runs AI analysis if needed
    5. Returns the analysis results
    """

    # Check if product already exists
    existing = await _check_existing_product(db, request.product_name, request.brand)
    if existing and not request.analyze_immediately:
        return ComprehensiveProductAnalysis(
            product_id=existing.product_id,
            name=existing.name,
            brand=existing.brand.name if existing.brand else "Unknown",
            squor_score=existing.latest_score or 0,
            squor_components=existing.score_components or {},
            sources=existing.sources or [],
            analysis_status="completed",
            consolidated_from=len(existing.sources or []),
        )

    # Search across retailers
    log.info(f"Searching for '{request.product_name}' across {len(request.retailers)} retailers")

    # Queue for processing
    background_tasks.add_task(_process_product_search, request=request, consolidator=consolidator, pipeline=pipeline)

    return ComprehensiveProductAnalysis(
        product_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
        name=request.product_name,
        brand=request.brand or "Unknown",
        squor_score=0,
        squor_components={},
        sources=[],
        analysis_status="processing",
        consolidated_from=0,
    )


@router.post("/products")
async def receive_crawler_product(
    product_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    pipeline: AIPipelineService = Depends(get_pipeline),
):
    """
    Receive product data from Scrapy crawlers
    
    This endpoint is called by the Scrapy pipeline to submit crawled products.
    The anti-blocking strategies work transparently - the crawlers handle all
    the proxy rotation, user agent switching, etc. before sending clean data here.
    """
    try:
        # Extract source page data
        source_page_data = product_data.get("source_page", {})
        
        # Create or update source page
        source_page = SourcePage(
            url=source_page_data.get("url"),
            retailer_code=source_page_data.get("retailer"),
            title=source_page_data.get("title"),
            content_hash=source_page_data.get("content_hash"),
            extracted_data=source_page_data.get("extracted_data", {}),
            crawl_session_id=source_page_data.get("crawl_session_id"),
            crawled_at=datetime.utcnow()
        )
        
        db.add(source_page)
        await db.commit()
        await db.refresh(source_page)
        
        # Queue for AI processing
        queue_id = await pipeline.process_crawler_result(
            crawler_data=source_page_data.get("extracted_data", {}),
            force_reanalysis=False
        )
        
        return {
            "product_id": source_page.source_page_id,
            "queue_id": queue_id,
            "status": "queued",
            "message": "Product queued for analysis"
        }
        
    except Exception as e:
        log.error(f"Failed to process crawler product: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions")
async def create_crawler_session(
    session_data: Dict[str, Any],
    db: AsyncSession = Depends(get_session),
):
    """Create a new crawler session"""
    retailer_code = session_data.get("retailer")
    
    # Get retailer
    result = await db.execute(
        select(Retailer).where(Retailer.code == retailer_code)
    )
    retailer = result.scalar_one_or_none()
    
    if not retailer:
        raise HTTPException(status_code=404, detail=f"Retailer {retailer_code} not found")
    
    # Create session
    session = CrawlSession(
        retailer_id=retailer.retailer_id,
        status="running",
        metadata=session_data
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return {
        "session_id": session.session_id,
        "status": "created"
    }


@router.patch("/sessions/{session_id}")
async def update_crawler_session(
    session_id: UUID,
    update_data: Dict[str, Any],
    db: AsyncSession = Depends(get_session),
):
    """Update crawler session status"""
    result = await db.execute(
        select(CrawlSession).where(CrawlSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update status
    if "status" in update_data:
        session.status = update_data["status"]
        if update_data["status"] == "completed":
            session.completed_at = datetime.utcnow()
    
    if "error" in update_data:
        session.error_message = update_data["error"]
    
    await db.commit()
    
    return {"status": "updated"}


@router.get("/status/{session_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(session_id: UUID, db: AsyncSession = Depends(get_session)):
    """Get the status of a crawl session"""

    # Get session from database
    from sqlalchemy import select
    result = db.execute(select(CrawlSession).where(CrawlSession.session_id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Crawl session not found")

    # Calculate metrics
    metrics = session.session_metadata or {}

    return CrawlStatusResponse(
        session_id=session.session_id,
        status=session.status,
        started_at=session.started_at.isoformat() if session.started_at else None,
        products_found=session.pages_discovered or 0,
        products_analyzed=session.products_found or 0,
        products_skipped=metrics.get("skipped", 0),
        errors=metrics.get("errors", []),
        message=_get_status_message(session),
    )


@router.get("/products/recent", response_model=List[ComprehensiveProductAnalysis])
async def get_recent_products(
    limit: int = Query(default=10, ge=1, le=50),
    skip_unanalyzed: bool = Query(default=True),
    include_comprehensive: bool = Query(default=True, description="Include comprehensive AI analysis data"),
    db: AsyncSession = Depends(get_session),
):
    """Get recently analyzed products with optional comprehensive AI data"""
    from app.services.ai_analysis_service import AIAnalysisService
    
    # Query recent products with SQUOR scores
    query = """
        SELECT DISTINCT ON (p.product_id)
            p.product_id,
            p.name,
            b.name as brand_name,
            s.score as squor_score,
            s.score_json,
            s.squor_id,
            pv.product_version_id,
            s.computed_at
        FROM product p
        LEFT JOIN brand b ON p.brand_id = b.brand_id
        LEFT JOIN product_version pv ON p.product_id = pv.product_id
        LEFT JOIN squor_score s ON pv.product_version_id = s.product_version_id
        WHERE s.scheme = 'SQUOR_V2'
        ORDER BY p.product_id, s.computed_at DESC
        LIMIT :limit
    """

    if skip_unanalyzed:
        query = query.replace("WHERE s.scheme", "WHERE s.score IS NOT NULL AND s.scheme")

    result = db.execute(text(query), {"limit": limit})
    products = []

    # Initialize AI analysis service if needed
    analysis_service = None
    if include_comprehensive:
        async with AsyncSessionLocal() as ai_session:
            analysis_service = AIAnalysisService(ai_session)
            
            for row in result.fetchall():
                score_data = row.score_json or {}
                
                # Fetch SQUOR component explanations
                explanations = {}
                if row.squor_id:
                    comp_result = db.execute(
                        text("SELECT component_key, explain_md FROM squor_component WHERE squor_id = :squor_id"),
                        {"squor_id": row.squor_id}
                    )
                    for comp_row in comp_result.fetchall():
                        explanations[comp_row.component_key] = comp_row.explain_md or ""
                
                # Get comprehensive AI analysis data
                comprehensive_data = await analysis_service.get_comprehensive_analysis(row.product_version_id)
                
                product = ComprehensiveProductAnalysis(
                    product_id=row.product_id,
                    name=row.name,
                    brand=row.brand_name or "Unknown",
                    squor_score=float(row.squor_score or 0),
                    squor_components=score_data.get("components", {}),
                    squor_explanations=explanations if explanations else None,
                    analysis_status="completed",
                    consolidated_from=len(score_data.get("sources", [])),
                    sources=score_data.get("sources", []),
                    
                    # Comprehensive AI data
                    ai_category=comprehensive_data.get("ai_category") if comprehensive_data else None,
                    ingredients=comprehensive_data.get("ingredients") if comprehensive_data else None,
                    nutrition=comprehensive_data.get("nutrition") if comprehensive_data else None,
                    claims=comprehensive_data.get("claims") if comprehensive_data else None,
                    warnings=comprehensive_data.get("warnings") if comprehensive_data else None,
                    verdict=comprehensive_data.get("verdict") if comprehensive_data else None,
                    best_image=comprehensive_data.get("best_image") if comprehensive_data else None,
                    confidence=comprehensive_data.get("confidence") if comprehensive_data else None,
                    analysis_cost=comprehensive_data.get("analysis_cost") if comprehensive_data else None,
                    analyzed_at=comprehensive_data.get("analyzed_at") if comprehensive_data else None,
                    model_used=comprehensive_data.get("model_used") if comprehensive_data else None,
                )
                
                products.append(product)
    else:
        # Basic data only
        for row in result.fetchall():
            score_data = row.score_json or {}
            
            # Fetch SQUOR component explanations
            explanations = {}
            if row.squor_id:
                comp_result = db.execute(
                    text("SELECT component_key, explain_md FROM squor_component WHERE squor_id = :squor_id"),
                    {"squor_id": row.squor_id}
                )
                for comp_row in comp_result.fetchall():
                    explanations[comp_row.component_key] = comp_row.explain_md or ""
            
            product = ComprehensiveProductAnalysis(
                product_id=row.product_id,
                name=row.name,
                brand=row.brand_name or "Unknown",
                squor_score=float(row.squor_score or 0),
                squor_components=score_data.get("components", {}),
                squor_explanations=explanations if explanations else None,
                analysis_status="completed",
                consolidated_from=len(score_data.get("sources", [])),
                sources=score_data.get("sources", []),
            )
            
            products.append(product)

    return products


# Background processing functions
async def _process_category_crawl(
    session_ids: List[UUID],
    request: CategoryCrawlRequest,
    orchestrator: DiscoveryOrchestrator,
    consolidator: ProductConsolidator,
    pipeline: AIPipelineService,
):
    """Process category crawl in background"""
    try:
        log.info(f"Starting category crawl for '{request.category}'")

        # Generate discovery tasks for each retailer
        tasks = []
        for retailer in request.retailers:
            task = await orchestrator.generate_category_tasks(
                category=request.category, retailer=retailer, max_products=request.max_products
            )
            tasks.extend(task)

        log.info(f"Generated {len(tasks)} discovery tasks")

        # Process tasks and collect products
        all_products = []
        for task in tasks:
            products = await orchestrator.execute_task(task)
            log.info(f"Task returned {len(products)} products")
            all_products.extend(products)

        log.info(f"Total products collected: {len(all_products)}")

        # Consolidate duplicates across retailers (create fresh instance to avoid DI caching issues)
        async with AsyncSessionLocal() as fresh_db:
            fresh_consolidator = ProductConsolidator(fresh_db)
            consolidated = await fresh_consolidator.consolidate_products(
                products=all_products, group_variants=request.consolidate_variants
            )

        log.info(f"Consolidated to {len(consolidated)} unique products")

        # Process each unique product
        analyzed = 0
        skipped = 0

        for product_group in consolidated:
            # Check if already analyzed
            # Skip existing check - now handled by duplicate detection in AI pipeline

            # Create processing queue item
            queue_id = await pipeline.process_crawler_result(product_group, force_reanalysis=request.force_reanalysis)

            # Process through pipeline
            await pipeline.process_queue_item(queue_id)
            analyzed += 1

        # Update all session statuses
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            for session_id in session_ids:
                result = await db.execute(select(CrawlSession).where(CrawlSession.session_id == session_id))
                session = result.scalar_one_or_none()
                if session:
                    session.status = "completed"
                    session.products_found = len(all_products)
                    session.products_new = analyzed
                    if session.session_metadata:
                        session.session_metadata["skipped"] = skipped
                    else:
                        session.session_metadata = {"skipped": skipped}
                    session.finished_at = datetime.utcnow()
            await db.commit()

        log.info(f"Category crawl completed: {analyzed} analyzed, {skipped} skipped")

    except Exception as e:
        log.error(f"Category crawl failed: {str(e)}")

        # Update all sessions with error
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            for session_id in session_ids:
                result = await db.execute(select(CrawlSession).where(CrawlSession.session_id == session_id))
                session = result.scalar_one_or_none()
                if session:
                    session.status = "failed"
                    session.error_details = {"error": str(e)}
            await db.commit()


async def _process_product_search(
    request: ProductSearchRequest, consolidator: ProductConsolidator, pipeline: AIPipelineService
):
    """Process product search in background"""
    try:
        # Search across all retailers
        search_results = []
        for retailer in request.retailers:
            results = await consolidator.search_product(
                product_name=request.product_name, brand=request.brand, retailer=retailer
            )
            search_results.extend(results)

        if not search_results:
            log.warning(f"No results found for '{request.product_name}'")
            return

        # Consolidate results
        consolidated = await consolidator.consolidate_products(products=search_results, group_variants=True)

        if consolidated:
            # Process the first/best match
            best_match = consolidated[0]

            # Create processing queue item  
            queue_id = await pipeline.process_crawler_result(best_match, force_reanalysis=request.force_reanalysis)

            # Process through pipeline
            await pipeline.process_queue_item(queue_id)

            log.info(f"Product '{request.product_name}' analyzed successfully")

    except Exception as e:
        log.error(f"Product search failed: {str(e)}")


async def _check_existing_product(db: AsyncSession, name: str, brand: Optional[str]) -> Optional[Any]:
    """Check if product already exists in database"""
    query = """
        SELECT p.*, s.score as latest_score, s.score_json
        FROM product p
        LEFT JOIN brand b ON p.brand_id = b.brand_id
        LEFT JOIN product_version pv ON p.product_id = pv.product_id
        LEFT JOIN squor_score s ON pv.product_version_id = s.product_version_id
        WHERE LOWER(p.name) = LOWER($1)
    """

    params = [name]
    if brand:
        query += " AND LOWER(b.name) = LOWER($2)"
        params.append(brand)

    query += " ORDER BY pv.created_at DESC LIMIT 1"

    result = await db.execute(text(query), params)
    return result.first()


# Removed unused function _check_existing_product_by_data


def _get_status_message(session: CrawlSession) -> str:
    """Generate status message for session"""
    if session.status == "running":
        return "Crawl in progress..."
    elif session.status == "completed":
        return f"Completed: {session.products_found} products found, {session.products_new} analyzed"
    elif session.status == "failed":
        return f"Failed: {session.error_details.get('error', 'Unknown error')}"
    else:
        return f"Status: {session.status}"
