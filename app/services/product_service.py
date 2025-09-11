"""
Product service with business logic
"""
from typing import Optional, List, Dict, Any
from uuid import UUID

from app.repositories import ProductRepository, BrandRepository, CategoryRepository
from app.schemas.product import ProductCreate, ProductUpdate, ProductRead
from app.core.exceptions import NotFoundError, BusinessLogicError
from app.core.logging import log
from app.utils.normalization import normalize_product_name, parse_gtin


class ProductService:
    """Service layer for product operations"""
    
    def __init__(
        self,
        product_repo: ProductRepository,
        brand_repo: BrandRepository,
        category_repo: CategoryRepository
    ):
        self.product_repo = product_repo
        self.brand_repo = brand_repo
        self.category_repo = category_repo
    
    async def create_product(self, product_data: ProductCreate) -> ProductRead:
        """Create new product with validation"""
        # Verify brand exists
        brand = await self.brand_repo.get_or_404(id=product_data.brand_id)
        
        # Validate GTIN if provided
        if product_data.gtin_primary:
            gtin = parse_gtin(product_data.gtin_primary)
            if not gtin:
                raise BusinessLogicError("Invalid GTIN format")
            
            # Check for duplicate GTIN
            existing = await self.product_repo.get_by_gtin(gtin)
            if existing:
                raise BusinessLogicError(
                    f"Product with GTIN {gtin} already exists",
                    existing_product_id=str(existing.product_id)
                )
        
        # Create product
        normalized_name = normalize_product_name(product_data.name, brand.name)
        canonical_key = f"{brand.normalized_name}:{normalized_name}:{product_data.pack_size or 'default'}"
        
        product = await self.product_repo.create(
            obj_in=product_data,
            normalized_name=normalized_name,
            canonical_key=canonical_key
        )
        
        # Create initial version
        await self.product_repo.create_version(product.product_id)
        
        log.info("Created product", product_id=str(product.product_id), name=product.name)
        
        return ProductRead.model_validate(product)
    
    async def get_product(self, product_id: UUID) -> ProductRead:
        """Get product by ID"""
        product = await self.product_repo.get_or_404(id=product_id)
        return ProductRead.model_validate(product)
