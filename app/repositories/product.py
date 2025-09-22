"""
Product repository implementation
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlmodel import and_, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import log
from app.models.product import Product, ProductIdentifier, ProductVersion
from app.models.brand import Brand
from app.repositories.base import BaseRepository
from app.schemas.product import ProductCreate, ProductUpdate


class ProductRepository(BaseRepository[Product, ProductCreate, ProductUpdate]):
    """Repository for product operations"""

    def __init__(self, session: AsyncSession):
        super().__init__(Product, session)

    async def get_by_canonical_key(self, canonical_key: str) -> Optional[Product]:
        """Get product by canonical key"""
        statement = select(Product).where(Product.canonical_key == canonical_key, Product.status == "active")
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_gtin(self, gtin: str) -> Optional[Product]:
        """Get product by GTIN"""
        statement = select(Product).where(Product.gtin_primary == gtin)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def search(
        self, query: str, skip: int = 0, limit: int = 20, filters: Optional[Dict[str, Any]] = None
    ) -> List[Product]:
        """Search products by name or brand"""
        search_term = f"%{query}%"

        statement = select(Product).where(
            or_(Product.name.ilike(search_term), Product.normalized_name.ilike(search_term))
        )

        # Apply additional filters
        if filters:
            if filters.get("brand_id"):
                statement = statement.where(Product.brand_id == filters["brand_id"])
            if filters.get("category"):
                statement = statement.where(Product.category == filters["category"])
            if filters.get("status"):
                statement = statement.where(Product.status == filters["status"])

        statement = statement.offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_latest_version(self, product_id: UUID) -> Optional[ProductVersion]:
        """Get latest product version"""
        statement = (
            select(ProductVersion)
            .where(ProductVersion.product_id == product_id)
            .order_by(ProductVersion.version_seq.desc())
            .limit(1)
        )

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create_version(self, product_id: UUID, job_run_id: Optional[UUID] = None) -> ProductVersion:
        """Create new product version"""
        # Get next version number
        count_stmt = select(func.count()).select_from(ProductVersion).where(ProductVersion.product_id == product_id)
        result = await self.session.execute(count_stmt)
        count = result.scalar_one()
        next_version = count + 1

        # Create version
        version = ProductVersion(product_id=product_id, version_seq=next_version, derived_from_job_run_id=job_run_id)

        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)

        return version

    async def find_or_create_brand(self, brand_name: str) -> Optional[Brand]:
        """Find or create a brand by name"""
        if not brand_name:
            return None
            
        # Normalize the brand name for searching
        normalized_name = brand_name.lower().strip()
        
        # Try to find existing brand
        statement = select(Brand).where(
            or_(
                Brand.name.ilike(f"%{brand_name}%"),
                Brand.normalized_name == normalized_name
            )
        )
        result = await self.session.execute(statement)
        brand = result.scalar_one_or_none()
        
        if brand:
            return brand
            
        # Create new brand
        new_brand = Brand(
            name=brand_name,
            normalized_name=normalized_name
        )
        
        self.session.add(new_brand)
        await self.session.commit()
        await self.session.refresh(new_brand)
        
        log.info(f"Created new brand: {brand_name}")
        return new_brand
    
    async def find_or_create_product(
        self, brand_id: UUID, name: str, metadata: Optional[dict] = None,
        retailer_product_id: Optional[str] = None, product_hash: Optional[str] = None
    ) -> Product:
        """Find or create a product using proper identification"""
        # Normalize the product name
        normalized_name = name.lower().strip()
        
        # Priority 1: Try to find by EAN/GTIN (most reliable)
        from app.utils.product_identification import extract_ean_code
        ean_code = extract_ean_code(metadata or {})
        if ean_code:
            stmt = select(Product).where(Product.gtin_primary == ean_code)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                log.info(f"Found existing product by EAN: {ean_code}")
                return existing
        
        # Priority 2: Try to find by retailer ID
        if retailer_product_id:
            stmt = select(Product).where(Product.retailer_product_id == retailer_product_id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                log.info(f"Found existing product by retailer ID: {retailer_product_id}")
                return existing
        
        # Priority 3: Try to find by product hash
        if product_hash:
            stmt = select(Product).where(Product.product_hash == product_hash)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                log.info(f"Found existing product by hash: {product_hash[:16]}...")
                return existing
        
        # Fallback: try to find existing product by brand and normalized name
        statement = select(Product).where(
            and_(
                Product.brand_id == brand_id,
                or_(
                    Product.name.ilike(f"%{name}%"),
                    Product.normalized_name == normalized_name
                )
            )
        )
        result = await self.session.execute(statement)
        product = result.scalar_one_or_none()
        
        if product:
            return product
            
        # Create new product
        # Generate canonical key from brand and normalized name
        canonical_key = f"{brand_id}_{normalized_name}".replace(" ", "_").lower()
        
        new_product = Product(
            brand_id=brand_id,
            name=name,
            normalized_name=normalized_name,
            canonical_key=canonical_key,
            status="active",
            gtin_primary=ean_code,  # Store EAN code in GTIN field
            retailer_product_id=retailer_product_id,
            product_hash=product_hash,
            metadata=metadata or {}
        )
        
        self.session.add(new_product)
        await self.session.commit()
        await self.session.refresh(new_product)
        
        log.info(f"Created new product: {name}")
        return new_product
    
    async def create_product_version(self, product_id: UUID, source: str = "crawler") -> ProductVersion:
        """Create a new product version"""
        # Get next version number
        count_stmt = select(func.count()).select_from(ProductVersion).where(
            ProductVersion.product_id == product_id
        )
        result = await self.session.execute(count_stmt)
        count = result.scalar_one()
        next_version = count + 1
        
        # Create version
        version = ProductVersion(
            product_id=product_id,
            version_seq=next_version,
            source=source
        )
        
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)
        
        log.info(f"Created product version {next_version} for product {product_id}")
        return version

    async def create_product_version_with_content_hash(
        self, 
        product_id: UUID, 
        content_hash: str,
        source: str = "crawler"
    ) -> ProductVersion:
        """Create a new product version with content hash"""
        # Get next version number
        count_stmt = select(func.count()).select_from(ProductVersion).where(
            ProductVersion.product_id == product_id
        )
        result = await self.session.execute(count_stmt)
        count = result.scalar_one()
        next_version = count + 1
        
        # Create version
        version = ProductVersion(
            product_id=product_id,
            version_seq=next_version,
            content_hash=content_hash,
            source=source
        )
        
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)
        
        log.info(f"Created product version {next_version} for product {product_id} with hash {content_hash[:8]}...")
        return version

    async def get_latest_version_hash(self, product_id: UUID) -> Optional[str]:
        """Get the content hash of the most recent product version"""
        stmt = (
            select(ProductVersion.content_hash)
            .where(ProductVersion.product_id == product_id)
            .order_by(ProductVersion.version_seq.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def should_create_new_version(self, product_id: UUID, new_content_hash: str) -> tuple[bool, str]:
        """Check if a new version should be created based on content hash"""
        latest_hash = await self.get_latest_version_hash(product_id)
        
        if not latest_hash:
            return True, "No previous version exists"
        
        if latest_hash != new_content_hash:
            return True, f"Content changed (new: {new_content_hash[:8]}..., old: {latest_hash[:8]}...)"
        
        return False, f"Content identical (hash: {new_content_hash[:8]}...)"
