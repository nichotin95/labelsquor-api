"""
Brand service with business logic
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.core.cache import cache_key, cached
from app.core.exceptions import BusinessLogicError, ConflictError, NotFoundError
from app.core.logging import log
from app.repositories.brand import BrandRepository
from app.schemas.brand import BrandCreate, BrandRead, BrandReadWithProducts, BrandUpdate
from app.utils.normalization import normalize_brand_name


class BrandService:
    """Service layer for brand operations"""

    def __init__(self, brand_repo: BrandRepository):
        self.brand_repo = brand_repo

    @cached(ttl=300)  # Cache for 5 minutes
    async def get_brand(self, brand_id: UUID) -> BrandRead:
        """Get brand by ID with caching"""
        brand = await self.brand_repo.get_or_404(id=brand_id)
        return BrandRead.model_validate(brand)

    async def create_brand(self, brand_data: BrandCreate) -> BrandRead:
        """Create new brand with validation and normalization"""
        # Normalize brand name
        normalized_name = normalize_brand_name(brand_data.name)

        # Check for existing brand
        existing = await self.brand_repo.get_by_normalized_name(normalized_name, brand_data.country)

        if existing:
            raise ConflictError(f"Brand '{brand_data.name}' already exists", existing_id=str(existing.brand_id))

        # Create brand
        brand = await self.brand_repo.create(obj_in=brand_data, normalized_name=normalized_name)

        log.info("Created brand", brand_id=str(brand.brand_id), name=brand.name)

        return BrandRead.model_validate(brand)

    async def update_brand(self, brand_id: UUID, brand_update: BrandUpdate) -> BrandRead:
        """Update brand with validation"""
        # Get existing brand
        brand = await self.brand_repo.get_or_404(id=brand_id)

        # If name is being updated, check for conflicts
        if brand_update.name and brand_update.name != brand.name:
            normalized_name = normalize_brand_name(brand_update.name)

            existing = await self.brand_repo.get_by_normalized_name(normalized_name, brand.country)

            if existing and existing.brand_id != brand_id:
                raise ConflictError(f"Brand name '{brand_update.name}' already exists")

            # Add normalized name to update
            brand_update.normalized_name = normalized_name

        # Update brand
        updated_brand = await self.brand_repo.update(id=brand_id, obj_in=brand_update)

        # Invalidate cache
        await cache_key(f"brand:{brand_id}").delete()

        return BrandRead.model_validate(updated_brand)

    async def delete_brand(self, brand_id: UUID) -> bool:
        """Delete brand with validation"""
        # Check if brand has products
        brand_with_count = await self.brand_repo.get_with_product_count(brand_id)

        if not brand_with_count:
            raise NotFoundError("Brand not found")

        if brand_with_count["product_count"] > 0:
            raise BusinessLogicError(
                "Cannot delete brand with existing products", product_count=brand_with_count["product_count"]
            )

        # Delete brand
        result = await self.brand_repo.delete(id=brand_id)

        # Invalidate cache
        await cache_key(f"brand:{brand_id}").delete()

        return result

    async def search_brands(self, query: str, skip: int = 0, limit: int = 20) -> List[BrandRead]:
        """Search brands"""
        brands = await self.brand_repo.search(query, skip, limit)
        return [BrandRead.model_validate(brand) for brand in brands]

    @cached(ttl=600)  # Cache for 10 minutes
    async def get_top_brands(self, limit: int = 10, country: Optional[str] = None) -> List[dict]:
        """Get top brands by product count"""
        return await self.brand_repo.get_top_brands(limit, country)

    async def merge_brands(self, source_brand_id: UUID, target_brand_id: UUID) -> BrandRead:
        """Merge two brands"""
        if source_brand_id == target_brand_id:
            raise BusinessLogicError("Cannot merge brand with itself")

        # Verify both brands exist
        source = await self.brand_repo.get_or_404(id=source_brand_id)
        target = await self.brand_repo.get_or_404(id=target_brand_id)

        # Perform merge
        await self.brand_repo.merge_brands(source_brand_id, target_brand_id)

        # Invalidate caches
        await cache_key(f"brand:{source_brand_id}").delete()
        await cache_key(f"brand:{target_brand_id}").delete()

        # Return updated target brand
        return await self.get_brand(target_brand_id)
