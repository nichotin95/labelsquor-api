"""
SQLModel for crawler configuration and search terms
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import JSON, Column, Field, SQLModel


class SearchTerm(SQLModel, table=True):
    """Search terms for product discovery"""

    __tablename__ = "search_term"

    id: Optional[int] = Field(default=None, primary_key=True)
    term: str = Field(index=True, description="Search term or keyword")
    category: str = Field(index=True, description="Category: brand, product, ingredient, etc.")
    retailer: Optional[str] = Field(default=None, index=True, description="Specific retailer or null for all")
    priority: int = Field(default=5, ge=1, le=10, description="Priority 1-10, higher = more important")
    language: str = Field(default="en", description="Language code")
    meta_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    # Usage tracking
    last_used: Optional[datetime] = Field(default=None)
    use_count: int = Field(default=0)
    success_rate: Optional[float] = Field(default=None, ge=0, le=1)

    # Status
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CategoryMapping(SQLModel, table=True):
    """Category mappings for different retailers"""

    __tablename__ = "category_mapping"

    id: Optional[int] = Field(default=None, primary_key=True)
    retailer: str = Field(index=True)
    internal_category: str = Field(index=True, description="Our internal category taxonomy")
    retailer_category_path: str = Field(description="Retailer's category path/URL")
    retailer_category_name: str = Field(description="Retailer's category display name")

    # Hierarchy
    parent_category: Optional[str] = Field(default=None)
    level: int = Field(default=1, description="Category depth level")

    # Metadata
    meta_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    expected_product_count: Optional[int] = Field(default=None)
    last_crawled: Optional[datetime] = Field(default=None)

    # Status
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CrawlerConfig(SQLModel, table=True):
    """Dynamic crawler configuration"""

    __tablename__ = "crawler_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    retailer: str = Field(unique=True, index=True)

    # URLs and endpoints
    base_url: str
    search_url_template: Optional[str] = Field(default=None, description="Template for search URLs")
    category_url_template: Optional[str] = Field(default=None, description="Template for category URLs")
    product_url_pattern: str = Field(description="Regex pattern to identify product URLs")

    # API endpoints (if discovered)
    api_endpoints: Dict[str, str] = Field(default_factory=dict, sa_column=Column(JSONB))

    # Crawling rules
    crawl_rules: Dict[str, Any] = Field(
        default_factory=lambda: {
            "delay": 1.0,
            "concurrent_requests": 2,
            "retry_times": 3,
            "download_timeout": 30,
            "user_agents": ["LabelSquor Bot (+https://labelsquor.com/bot)"],
            "respect_robots_txt": True,
            "use_playwright": False,
        },
        sa_column=Column(JSONB),
    )

    # Selectors for data extraction
    selectors: Dict[str, Any] = Field(
        default_factory=lambda: {
            "product_name": ["h1::text", "[class*='product-name']::text"],
            "brand": ["[class*='brand']::text", "[itemprop='brand']::text"],
            "price": ["[class*='price']::text", "[itemprop='price']::text"],
            "image": ["img[class*='product']::attr(src)", "[itemprop='image']::attr(src)"],
            "ingredients": ["[class*='ingredient']", "div:contains('Ingredients')"],
            "nutrition": ["[class*='nutrition']", "div:contains('Nutrition')"],
        },
        sa_column=Column(JSONB),
    )

    # Discovery strategies
    discovery_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "use_sitemap": True,
            "sitemap_urls": ["/sitemap.xml"],
            "use_search": True,
            "use_categories": True,
            "use_pagination": True,
            "max_pages_per_category": 10,
        },
        sa_column=Column(JSONB),
    )

    # Status
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CrawlPlan(SQLModel, table=True):
    """Planned crawl tasks"""

    __tablename__ = "crawl_plan"

    id: Optional[int] = Field(default=None, primary_key=True)
    retailer: str = Field(index=True)
    strategy: str = Field(index=True, description="discovery, update, deep_crawl, etc.")

    # What to crawl
    target_type: str = Field(description="search, category, product, brand")
    target_value: str = Field(description="The search term, category path, or URL")
    priority: int = Field(default=5, ge=1, le=10)

    # Scheduling
    scheduled_for: Optional[datetime] = Field(default=None, index=True)
    frequency: Optional[str] = Field(default=None, description="daily, weekly, monthly")

    # Execution tracking
    last_executed: Optional[datetime] = Field(default=None)
    execution_count: int = Field(default=0)
    last_result: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))

    # Status
    status: str = Field(default="pending", index=True)  # pending, running, completed, failed
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
