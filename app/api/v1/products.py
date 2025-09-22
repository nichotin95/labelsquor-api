"""
Consumer-facing Products API
Provides UI-friendly endpoints for LabelSquor consumer application
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

from app.core.database import get_session, AsyncSessionLocal
from app.core.security import verify_consumer_access
from app.services.ai_analysis_service import AIAnalysisService

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(tags=["products"])


# Response Models for Consumer UI
class ProductSummary(BaseModel):
    """Lightweight product summary for lists and search results"""
    
    product_id: UUID
    name: str
    brand: str
    category: Optional[str] = None
    
    # SQUOR Overview
    squor_score: float = Field(description="Overall SQUOR score (0-100)")
    squor_grade: str = Field(description="Letter grade (A-F)")
    
    # Key highlights
    key_claims: List[str] = Field(default=[], description="Top 3 marketing claims")
    warnings: List[str] = Field(default=[], description="Important warnings/allergens")
    
    # Image for UI
    image_url: Optional[str] = Field(default=None, description="Primary product image")
    
    # Analysis metadata
    confidence: Optional[float] = Field(default=None, description="AI confidence (0-1)")
    analyzed_at: Optional[datetime] = Field(default=None)


class ProductDetail(BaseModel):
    """Complete product details for product page"""
    
    # Basic info
    product_id: UUID
    name: str
    brand: str
    category: Optional[str] = None
    
    # SQUOR Analysis
    squor_score: float
    squor_grade: str
    squor_components: Dict[str, float] = Field(description="Individual SQUOR component scores")
    squor_explanations: Dict[str, str] = Field(description="Why cards for each component")
    
    # Rich product data
    ingredients: List[Dict[str, Any]] = Field(default=[], description="Ingredient list with details")
    nutrition: Optional[Dict[str, Any]] = Field(default=None, description="Nutrition facts")
    claims: List[Dict[str, Any]] = Field(default=[], description="Marketing claims with verification")
    warnings: List[Dict[str, Any]] = Field(default=[], description="Warnings and allergens")
    
    # AI verdict
    verdict: Optional[Dict[str, Any]] = Field(default=None, description="AI recommendation and rating")
    
    # Images
    image_url: Optional[str] = Field(default=None, description="Primary product image")
    all_images: List[str] = Field(default=[], description="All available product images")
    
    # Analysis metadata
    confidence: Optional[float] = None
    analyzed_at: Optional[datetime] = None
    analysis_cost: Optional[float] = None
    model_used: Optional[str] = None


class ProductSearchResponse(BaseModel):
    """Paginated search response"""
    
    products: List[ProductSummary]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    
    # Search metadata
    query: Optional[str] = None
    filters_applied: Dict[str, Any] = Field(default_factory=dict)


class FilterOptions(BaseModel):
    """Available filter options for UI"""
    
    brands: List[Dict[str, Any]] = Field(description="Available brands with counts")
    categories: List[Dict[str, Any]] = Field(description="Available categories with counts") 
    score_ranges: List[Dict[str, Any]] = Field(description="Score ranges with counts")
    claim_types: List[Dict[str, Any]] = Field(description="Available claim types")


# Consumer-facing endpoints
@router.get("/search", response_model=ProductSearchResponse)
async def search_products(
    # Search parameters
    q: Optional[str] = Query(None, description="Search query (product name, brand, ingredients)"),
    
    # Filters
    brand: Optional[str] = Query(None, description="Filter by brand name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum SQUOR score"),
    max_score: Optional[float] = Query(None, ge=0, le=100, description="Maximum SQUOR score"),
    grade: Optional[str] = Query(None, description="Filter by SQUOR grade (A, B, C, D, F)"),
    
    # Sorting
    sort_by: str = Query("score", description="Sort by: score, name, brand, analyzed_at"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    
    db: AsyncSession = Depends(get_session)
):
    """Search and filter products with UI-friendly pagination and sorting"""
    
    # Build base query with comprehensive data
    query = """
        SELECT DISTINCT ON (p.product_id)
            p.product_id,
            p.name,
            b.name as brand_name,
            pa.ai_category,
            s.score as squor_score,
            s.grade as squor_grade,
            pa.confidence,
            pa.analyzed_at,
            pa.best_image_url,
            COUNT(*) OVER() as total_count
        FROM product p
        LEFT JOIN brand b ON p.brand_id = b.brand_id
        LEFT JOIN product_version pv ON p.product_id = pv.product_id
        LEFT JOIN squor_score s ON pv.product_version_id = s.product_version_id
        LEFT JOIN product_analysis pa ON pv.product_version_id = pa.product_version_id
        WHERE s.scheme = 'SQUOR_V2' AND s.score IS NOT NULL
    """
    
    params = {}
    conditions = []
    
    # Apply filters
    if q:
        conditions.append("(p.name ILIKE :search OR b.name ILIKE :search)")
        params["search"] = f"%{q}%"
    
    if brand:
        conditions.append("LOWER(b.name) = LOWER(:brand)")
        params["brand"] = brand
    
    if category:
        conditions.append("LOWER(pa.ai_category) = LOWER(:category)")
        params["category"] = category
        
    if min_score is not None:
        conditions.append("s.score >= :min_score")
        params["min_score"] = min_score
        
    if max_score is not None:
        conditions.append("s.score <= :max_score")
        params["max_score"] = max_score
        
    if grade:
        conditions.append("s.grade = :grade")
        params["grade"] = grade.upper()
    
    # Add conditions
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    # Add sorting
    sort_column = {
        "score": "s.score",
        "name": "p.name",
        "brand": "b.name", 
        "analyzed_at": "pa.analyzed_at"
    }.get(sort_by, "s.score")
    
    sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
    query += f" ORDER BY p.product_id, {sort_column} {sort_direction}"
    
    # Add pagination
    offset = (page - 1) * page_size
    query += f" LIMIT {page_size} OFFSET {offset}"
    
    # Execute query
    result = db.execute(text(query), params)
    rows = result.fetchall()
    
    total_count = rows[0].total_count if rows else 0
    total_pages = (total_count + page_size - 1) // page_size
    
    # Build response
    products = []
    for row in rows:
        # Get top claims
        claims_result = db.execute(text("""
            SELECT claim_text FROM product_claim pc
            JOIN product_analysis pa ON pc.analysis_id = pa.analysis_id
            WHERE pa.product_version_id = (
                SELECT product_version_id FROM product_version 
                WHERE product_id = :product_id ORDER BY version_seq DESC LIMIT 1
            ) LIMIT 3
        """), {"product_id": row.product_id})
        key_claims = [c[0] for c in claims_result.fetchall()]
        
        # Get warnings
        warnings_result = db.execute(text("""
            SELECT warning_text FROM product_warning pw
            JOIN product_analysis pa ON pw.analysis_id = pa.analysis_id
            WHERE pa.product_version_id = (
                SELECT product_version_id FROM product_version 
                WHERE product_id = :product_id ORDER BY version_seq DESC LIMIT 1
            )
        """), {"product_id": row.product_id})
        warnings = [w[0] for w in warnings_result.fetchall()]
        
        products.append(ProductSummary(
            product_id=row.product_id,
            name=row.name,
            brand=row.brand_name or "Unknown",
            category=row.ai_category,
            squor_score=float(row.squor_score or 0),
            squor_grade=row.squor_grade or "F",
            key_claims=key_claims,
            warnings=warnings,
            image_url=row.best_image_url,
            confidence=row.confidence,
            analyzed_at=row.analyzed_at
        ))
    
    return ProductSearchResponse(
        products=products,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        query=q,
        filters_applied={
            "brand": brand,
            "category": category,
            "min_score": min_score,
            "max_score": max_score,
            "grade": grade
        }
    )


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product_detail(
    product_id: UUID,
    db: AsyncSession = Depends(get_session)
):
    """Get complete product details for product page"""
    
    # Get product with comprehensive analysis
    query = """
        SELECT DISTINCT ON (p.product_id)
            p.product_id,
            p.name,
            b.name as brand_name,
            pa.ai_category,
            s.score as squor_score,
            s.grade as squor_grade,
            s.score_json,
            s.squor_id,
            pa.confidence,
            pa.analyzed_at,
            pa.analysis_cost,
            pa.model_used,
            pa.best_image_url,
            pa.overall_rating,
            pa.recommendation,
            pv.product_version_id
        FROM product p
        LEFT JOIN brand b ON p.brand_id = b.brand_id
        LEFT JOIN product_version pv ON p.product_id = pv.product_id
        LEFT JOIN squor_score s ON pv.product_version_id = s.product_version_id
        LEFT JOIN product_analysis pa ON pv.product_version_id = pa.product_version_id
        WHERE p.product_id = :product_id AND s.scheme = 'SQUOR_V2'
        ORDER BY p.product_id, s.computed_at DESC
        LIMIT 1
    """
    
    result = db.execute(text(query), {"product_id": product_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get SQUOR explanations
    explanations = {}
    if row.squor_id:
        comp_result = db.execute(
            text("SELECT component_key, explain_md FROM squor_component WHERE squor_id = :squor_id"),
            {"squor_id": row.squor_id}
        )
        explanations = {comp.component_key: comp.explain_md or "" for comp in comp_result.fetchall()}
    
    # Get comprehensive analysis
    comprehensive_data = None
    if row.product_version_id:
        async with AsyncSessionLocal() as ai_session:
            analysis_service = AIAnalysisService(ai_session)
            comprehensive_data = await analysis_service.get_comprehensive_analysis(row.product_version_id)
    
    return ProductDetail(
        product_id=row.product_id,
        name=row.name,
        brand=row.brand_name or "Unknown",
        category=row.ai_category,
        squor_score=float(row.squor_score or 0),
        squor_grade=row.squor_grade or "F",
        squor_components=(row.score_json or {}).get("components", {}),
        squor_explanations=explanations,
        
        # Comprehensive data
        ingredients=comprehensive_data.get("ingredients", []) if comprehensive_data else [],
        nutrition=comprehensive_data.get("nutrition") if comprehensive_data else None,
        claims=comprehensive_data.get("claims", []) if comprehensive_data else [],
        warnings=comprehensive_data.get("warnings", []) if comprehensive_data else [],
        
        verdict={
            "overall_rating": row.overall_rating,
            "recommendation": row.recommendation
        } if row.overall_rating or row.recommendation else None,
        
        image_url=row.best_image_url,
        all_images=[row.best_image_url] if row.best_image_url else [],
        
        confidence=row.confidence,
        analyzed_at=row.analyzed_at,
        analysis_cost=row.analysis_cost,
        model_used=row.model_used
    )


@router.get("/filters/options", response_model=FilterOptions)
async def get_filter_options(db: AsyncSession = Depends(get_session)):
    """Get available filter options for UI filter components"""
    
    # Get brands with counts
    brands_result = db.execute(text("""
        SELECT b.name, COUNT(DISTINCT p.product_id) as product_count
        FROM brand b
        JOIN product p ON b.brand_id = p.brand_id
        JOIN product_version pv ON p.product_id = pv.product_id
        JOIN squor_score s ON pv.product_version_id = s.product_version_id
        WHERE s.scheme = 'SQUOR_V2' AND s.score IS NOT NULL
        GROUP BY b.name
        ORDER BY product_count DESC, b.name
        LIMIT 50
    """))
    brands = [{"name": row[0], "count": row[1]} for row in brands_result.fetchall()]
    
    # Get categories with counts
    categories_result = db.execute(text("""
        SELECT pa.ai_category, COUNT(DISTINCT p.product_id) as product_count
        FROM product_analysis pa
        JOIN product_version pv ON pa.product_version_id = pv.product_version_id
        JOIN product p ON pv.product_id = p.product_id
        WHERE pa.ai_category IS NOT NULL
        GROUP BY pa.ai_category
        ORDER BY product_count DESC, pa.ai_category
    """))
    categories = [{"name": row[0], "count": row[1]} for row in categories_result.fetchall()]
    
    # Get score distribution
    score_ranges = [
        {"range": "90-100", "label": "Excellent (A)", "min": 90, "max": 100},
        {"range": "80-89", "label": "Good (B)", "min": 80, "max": 89},
        {"range": "70-79", "label": "Fair (C)", "min": 70, "max": 79},
        {"range": "60-69", "label": "Poor (D)", "min": 60, "max": 69},
        {"range": "0-59", "label": "Very Poor (F)", "min": 0, "max": 59}
    ]
    
    for score_range in score_ranges:
        count_result = db.execute(text("""
            SELECT COUNT(DISTINCT p.product_id)
            FROM product p
            JOIN product_version pv ON p.product_id = pv.product_id
            JOIN squor_score s ON pv.product_version_id = s.product_version_id
            WHERE s.scheme = 'SQUOR_V2' AND s.score BETWEEN :min_score AND :max_score
        """), {"min_score": score_range["min"], "max_score": score_range["max"]})
        score_range["count"] = count_result.scalar() or 0
    
    return FilterOptions(
        brands=brands,
        categories=categories,
        score_ranges=score_ranges,
        claim_types=[]
    )