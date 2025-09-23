"""
Discovery Orchestrator - Manages product discovery across all retailers
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crawler_config import crawler_config
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.core.taxonomy import TaxonomyManager
from app.models.crawler_config import CategoryMapping, CrawlerConfig, CrawlPlan, SearchTerm
from app.models.discovery import DiscoveryTask, TaskResult
from app.models.retailer import ProcessingQueue, Retailer


class DiscoveryOrchestrator:
    """Orchestrates product discovery across retailers"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.taxonomy = TaxonomyManager()

    async def initialize_seed_data(self):
        """Initialize search terms and categories if not present"""
        # Check if we have search terms
        term_count = await self.db.scalar(select(func.count(SearchTerm.id)))

        if term_count == 0:
            logger.info("Initializing seed data...")

            # Add universal search terms
            await self._add_search_terms()

            # Add category mappings
            await self._add_category_mappings()

            # Add retailer configs
            await self._add_retailer_configs()

            await self.db.commit()
            logger.info("Seed data initialized")

    async def _add_search_terms(self):
        """Add search terms from configuration to database"""
        # Load all search terms from config
        all_terms = crawler_config.get_all_search_terms_with_priority()

        logger.info(f"Loading {len(all_terms)} search terms from configuration")

        # Add each term to database
        for term_data in all_terms:
            # Check if term already exists
            existing = await self.db.execute(select(SearchTerm).where(SearchTerm.term == term_data["term"]))
            if existing.scalar_one_or_none():
                continue

            term = SearchTerm(
                term=term_data["term"],
                category=term_data["category"],
                priority=term_data["priority"],
                metadata=term_data.get("metadata", {}),
            )
            self.db.add(term)

        logger.info("Search terms loaded from configuration files")

    async def _add_category_mappings(self):
        """Add category mappings from configuration"""
        categories_config = crawler_config.load_categories()
        categories = categories_config.get("categories", {})

        # Get list of retailers from config
        retailers = set()
        for main_cat, sub_cats in categories.items():
            for sub_cat_data in sub_cats.values():
                retailers.update(sub_cat_data.get("retailers", {}).keys())

        logger.info(f"Loading category mappings for retailers: {retailers}")

        # Process each category
        for main_cat, sub_cats in categories.items():
            for sub_cat_key, sub_cat_data in sub_cats.items():
                display_name = sub_cat_data.get("display_name", sub_cat_key)

                # Internal category
                internal_path = f"{main_cat}/{sub_cat_key}"
                internal = CategoryMapping(
                    retailer="internal",
                    internal_category=internal_path,
                    retailer_category_path=f"/{internal_path}",
                    retailer_category_name=display_name,
                    parent_category=main_cat,
                    level=2,
                    metadata={
                        "keywords": sub_cat_data.get("keywords", []),
                        "popular_brands": sub_cat_data.get("popular_brands", []),
                    },
                )
                self.db.add(internal)

                # Retailer-specific mappings
                retailer_mappings = sub_cat_data.get("retailers", {})
                for retailer, path in retailer_mappings.items():
                    cat_map = CategoryMapping(
                        retailer=retailer,
                        internal_category=internal_path,
                        retailer_category_path=path,
                        retailer_category_name=display_name,
                        parent_category=main_cat,
                        level=2,
                    )
                    self.db.add(cat_map)

        logger.info("Category mappings loaded from configuration")

    async def _add_retailer_configs(self):
        """Add retailer configurations"""
        configs = [
            {
                "retailer": "bigbasket",
                "base_url": "https://www.bigbasket.com",
                "search_url_template": "/ps/?q={term}&page={page}",
                "category_url_template": "{path}?page={page}",
                "product_url_pattern": r"/pd/\d+/[^/]+/",
                "api_endpoints": {"search": "/custompage/getsearchdata/", "autocomplete": "/product/get-search-data/"},
            },
            {
                "retailer": "blinkit",
                "base_url": "https://blinkit.com",
                "search_url_template": "/s/?q={term}",
                "category_url_template": "{path}",
                "product_url_pattern": r"/p/[^/]+/[^/]+",
                "crawl_rules": {"use_playwright": True, "delay": 2.0},  # Blinkit needs JS rendering
            },
        ]

        for config_data in configs:
            config = CrawlerConfig(**config_data)
            self.db.add(config)

    async def plan_discovery_tasks(
        self, retailers: Optional[List[str]] = None, strategies: Optional[List[str]] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Generate discovery tasks for crawlers

        Args:
            retailers: List of retailers to include (all if None)
            strategies: List of strategies to use (all if None)
            limit: Maximum number of tasks to generate

        Returns:
            List of discovery tasks
        """
        tasks = []

        # Get active retailers
        if retailers:
            retailer_filter = Retailer.name.in_(retailers)
        else:
            retailer_filter = Retailer.is_active == True

        result = await self.db.execute(select(Retailer).where(retailer_filter))
        active_retailers = result.scalars().all()

        if not strategies:
            strategies = ["search", "category", "trending", "sitemap"]

        for retailer in active_retailers:
            # Get retailer config
            config_result = await self.db.execute(select(CrawlerConfig).where(CrawlerConfig.retailer == retailer.name))
            config = config_result.scalar_one_or_none()

            if not config:
                continue

            # Generate tasks based on strategies
            if "search" in strategies:
                tasks.extend(await self._generate_search_tasks(retailer, config))

            if "category" in strategies:
                tasks.extend(await self._generate_category_tasks(retailer, config))

            if "trending" in strategies and config.discovery_config.get("use_trending"):
                tasks.append(
                    {
                        "retailer": retailer.name,
                        "strategy": "trending",
                        "priority": 8,
                        "scheduled_at": datetime.utcnow(),
                    }
                )

            if "sitemap" in strategies and config.discovery_config.get("use_sitemap"):
                tasks.append(
                    {"retailer": retailer.name, "strategy": "sitemap", "priority": 5, "scheduled_at": datetime.utcnow()}
                )

        # Sort by priority and limit
        tasks.sort(key=lambda x: x["priority"], reverse=True)
        return tasks[:limit]

    async def _generate_search_tasks(self, retailer: Retailer, config: CrawlerConfig) -> List[Dict[str, Any]]:
        """Generate search-based discovery tasks"""
        tasks = []

        # Get high-priority search terms that haven't been used recently
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        result = await self.db.execute(
            select(SearchTerm)
            .where(
                and_(
                    SearchTerm.is_active == True,
                    SearchTerm.priority >= 7,
                    or_(SearchTerm.last_used == None, SearchTerm.last_used < cutoff_time),
                )
            )
            .order_by(SearchTerm.priority.desc(), SearchTerm.use_count)
            .limit(20)
        )
        search_terms = result.scalars().all()

        for term in search_terms:
            tasks.append(
                {
                    "retailer": retailer.name,
                    "strategy": "search",
                    "target": term.term,
                    "priority": term.priority,
                    "scheduled_at": datetime.utcnow(),
                    "metadata": {"term_id": term.id, "term_category": term.category},
                }
            )

        return tasks

    async def _generate_category_tasks(self, retailer: Retailer, config: CrawlerConfig) -> List[Dict[str, Any]]:
        """Generate category-based discovery tasks"""
        tasks = []

        # Get category mappings for this retailer
        result = await self.db.execute(
            select(CategoryMapping)
            .where(and_(CategoryMapping.retailer == retailer.name, CategoryMapping.is_active == True))
            .order_by(CategoryMapping.level, CategoryMapping.internal_category)
        )
        categories = result.scalars().all()

        # Prioritize categories that haven't been crawled recently
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        for category in categories:
            if not category.last_crawled or category.last_crawled < cutoff_time:
                priority = 7
            else:
                priority = 5

            tasks.append(
                {
                    "retailer": retailer.name,
                    "strategy": "category",
                    "target": category.retailer_category_path,
                    "priority": priority,
                    "scheduled_at": datetime.utcnow(),
                    "metadata": {
                        "category_id": category.id,
                        "internal_category": category.internal_category,
                        "level": category.level,
                    },
                }
            )

        return tasks

    async def create_crawl_plan(self, tasks: List[Dict[str, Any]]) -> List[CrawlPlan]:
        """Create crawl plan entries from tasks"""
        plans = []

        for task in tasks:
            plan = CrawlPlan(
                retailer=task["retailer"],
                strategy=task["strategy"],
                target_type=task["strategy"],  # search, category, etc.
                target_value=task.get("target", ""),
                priority=task["priority"],
                scheduled_for=task.get("scheduled_at"),
                status="pending",
            )
            self.db.add(plan)
            plans.append(plan)

        await self.db.commit()
        return plans

    async def get_next_tasks(self, retailer: Optional[str] = None, limit: int = 10) -> List[CrawlPlan]:
        """Get next tasks to execute"""
        query = select(CrawlPlan).where(
            and_(
                CrawlPlan.status == "pending",
                CrawlPlan.is_active == True,
                or_(CrawlPlan.scheduled_for == None, CrawlPlan.scheduled_for <= datetime.utcnow()),
            )
        )

        if retailer:
            query = query.where(CrawlPlan.retailer == retailer)

        query = query.order_by(CrawlPlan.priority.desc(), CrawlPlan.created_at).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def mark_task_started(self, task_id: int):
        """Mark a task as started"""
        result = await self.db.execute(select(CrawlPlan).where(CrawlPlan.id == task_id))
        task = result.scalar_one()

        task.status = "running"
        task.last_executed = datetime.utcnow()
        task.execution_count += 1

        await self.db.commit()

    async def mark_task_completed(self, task_id: int, result: Dict[str, Any]):
        """Mark a task as completed with results"""
        task_result = await self.db.execute(select(CrawlPlan).where(CrawlPlan.id == task_id))
        task = task_result.scalar_one()

        task.status = "completed"
        task.last_result = result

        # Update related search term or category
        if task.target_type == "search":
            await self._update_search_term_stats(task.target_value, result)
        elif task.target_type == "category":
            await self._update_category_stats(task.retailer, task.target_value)

        await self.db.commit()

    async def _update_search_term_stats(self, term: str, result: Dict[str, Any]):
        """Update search term usage statistics"""
        term_result = await self.db.execute(select(SearchTerm).where(SearchTerm.term == term))
        search_term = term_result.scalar_one_or_none()

        if search_term:
            search_term.last_used = datetime.utcnow()
            search_term.use_count += 1

            # Calculate success rate
            products_found = result.get("products_found", 0)
            if products_found > 0:
                if search_term.success_rate is None:
                    search_term.success_rate = 1.0
                else:
                    # Moving average
                    search_term.success_rate = search_term.success_rate * 0.9 + 0.1
            else:
                if search_term.success_rate is None:
                    search_term.success_rate = 0.0
                else:
                    search_term.success_rate *= 0.9

    async def _update_category_stats(self, retailer: str, category_path: str):
        """Update category crawl statistics"""
        cat_result = await self.db.execute(
            select(CategoryMapping).where(
                and_(CategoryMapping.retailer == retailer, CategoryMapping.retailer_category_path == category_path)
            )
        )
        category = cat_result.scalar_one_or_none()

        if category:
            category.last_crawled = datetime.utcnow()

    async def generate_category_tasks(
        self, category: str, retailer: str, max_products: int = 10
    ) -> List[DiscoveryTask]:
        """Generate discovery tasks for a specific category and retailer"""
        tasks = []

        async with AsyncSessionLocal() as db:
            # Get category mapping for this retailer
            mapping = await db.execute(
                select(CategoryMapping).where(
                    CategoryMapping.internal_category.like(f"%{category}%"), CategoryMapping.retailer == retailer
                )
            )
            category_mapping = mapping.scalar_one_or_none()

            if not category_mapping:
                logger.warning(f"No category mapping found for {category} on {retailer}")
                return tasks

            # Create category discovery task
            task = DiscoveryTask(
                task_type="category_discovery",
                retailer_slug=retailer,
                priority=7,
                category=category,
                max_products=max_products,
                config={
                    "category": category,
                    "category_path": category_mapping.retailer_category_path,
                    "max_products": max_products,
                    "page": 1,
                    "internal_category": category_mapping.internal_category,
                    "requested_category": category,
                },
            )
            tasks.append(task)

            # If we need more pages, add pagination tasks
            if max_products > 50:  # Assuming 50 products per page
                pages_needed = (max_products // 50) + 1
                for page in range(2, pages_needed + 1):
                    page_task = DiscoveryTask(
                        task_type="category_discovery",
                        retailer_slug=retailer,
                        priority=6,
                        category=category,
                        max_products=50,
                        config={
                            "category": category,
                            "category_path": category_mapping.retailer_category_path,
                            "max_products": 50,
                            "page": page,
                            "internal_category": category_mapping.internal_category,
                            "requested_category": category,
                        },
                    )
                    tasks.append(page_task)

        return tasks

    async def execute_task(self, task: DiscoveryTask) -> List[Dict[str, Any]]:
        """Execute a discovery task and return product data"""
        logger.info(f"Executing task: {task.task_type} for {task.retailer_slug}")

        # Import the crawler parser
        from app.services.simple_bigbasket_parser import SimpleBigBasketParser

        products = []

        if task.task_type == "category_discovery" and task.retailer_slug == "bigbasket":
            # Use actual BigBasket parser
            parser = SimpleBigBasketParser()

            # For category, we'll search using the category name
            category_name = task.config.get("category", "snacks")
            search_results = parser.search_products(category_name)

            # Get detailed data for each product
            for result in search_results[: task.config.get("max_products", 10)]:
                try:
                    # Get additional details from product page
                    detailed = parser.get_product_details(result["url"])
                    
                    # Merge search result with detailed data
                    # Reduced logging for production
                    if os.getenv("DEBUG_DISCOVERY", "false").lower() == "true":
                        logger.info(f"Processing product: {result.get('name', 'Unknown')}")
                    products.append(
                        {
                            "url": result["url"],
                            "name": result.get("name", ""),
                            "brand": result.get("brand", ""),
                            "retailer": task.retailer_slug,
                            "category": category_name,
                            "images": result.get("images", []),
                            "price": result.get("price", 0),
                            "mrp": result.get("mrp", 0),
                            "extracted_data": {
                                "usp_text": result.get("usp", ""),
                                "description": detailed.get("description", "") if detailed else "",
                                "ingredients": detailed.get("ingredients", "") if detailed else "",
                                "nutrition": detailed.get("nutrition", "") if detailed else "",
                                "manufacturer": detailed.get("manufacturer", "") if detailed else "",
                                "country_of_origin": detailed.get("country_of_origin", "") if detailed else "",
                                "shelf_life": detailed.get("shelf_life", "") if detailed else "",
                                "pack_size": result.get("pack_size", ""),
                                "in_stock": result.get("in_stock", True),
                                "rating": result.get("rating", 0),
                                "review_count": result.get("review_count", 0),
                                "crawled_at": datetime.utcnow().isoformat(),
                            },
                        }
                    )
                except Exception as e:
                    logger.error(f"Error processing product: {str(e)}")
                    continue

        elif task.task_type == "category_discovery":
            # Mock data for other retailers
            products = [
                {
                    "url": f"https://{task.retailer_slug}.com/product/{i}",
                    "name": f"Product {i} from {task.config['category']}",
                    "brand": "Test Brand",
                    "retailer": task.retailer_slug,
                    "category": task.config["category"],
                    "images": ["image1.jpg", "image2.jpg"],
                    "price": 100.0 + i,
                    "extracted_data": {
                        "description": "Product description",
                        "crawled_at": datetime.utcnow().isoformat(),
                    },
                }
                for i in range(min(task.config.get("max_products", 10), 5))
            ]

        logger.info(f"Returning {len(products)} products from execute_task")
        return products


from sqlalchemy import func  # Add this import at the top
