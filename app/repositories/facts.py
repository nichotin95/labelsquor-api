"""
Facts repository implementation for nutrition, ingredients, allergens, etc.
"""

from typing import List, Optional
from uuid import UUID

from sqlmodel import select

from app.models import IngredientsV, NutritionV, AllergensV, ClaimsV, CertificationsV
from app.repositories.base import BaseRepository


class FactsRepository:
    """Repository for product facts (nutrition, ingredients, allergens, claims, certifications)"""

    def __init__(self):
        pass

    async def get_current_ingredients(self, product_version_id: UUID) -> Optional[IngredientsV]:
        """Get current ingredients for a product version"""
        from app.core.database import get_session
        
        async with get_session() as session:
            statement = select(IngredientsV).where(
                IngredientsV.product_version_id == product_version_id,
                IngredientsV.is_current == True
            )
            result = await session.exec(statement)
            return result.first()

    async def get_current_nutrition(self, product_version_id: UUID) -> Optional[NutritionV]:
        """Get current nutrition for a product version"""
        from app.core.database import get_session
        
        async with get_session() as session:
            statement = select(NutritionV).where(
                NutritionV.product_version_id == product_version_id,
                NutritionV.is_current == True
            )
            result = await session.exec(statement)
            return result.first()

    async def get_current_allergens(self, product_version_id: UUID) -> Optional[AllergensV]:
        """Get current allergens for a product version"""
        from app.core.database import get_session
        
        async with get_session() as session:
            statement = select(AllergensV).where(
                AllergensV.product_version_id == product_version_id,
                AllergensV.is_current == True
            )
            result = await session.exec(statement)
            return result.first()

    async def get_current_claims(self, product_version_id: UUID) -> Optional[ClaimsV]:
        """Get current claims for a product version"""
        from app.core.database import get_session
        
        async with get_session() as session:
            statement = select(ClaimsV).where(
                ClaimsV.product_version_id == product_version_id,
                ClaimsV.is_current == True
            )
            result = await session.exec(statement)
            return result.first()

    async def get_current_certifications(self, product_version_id: UUID) -> Optional[CertificationsV]:
        """Get current certifications for a product version"""
        from app.core.database import get_session
        
        async with get_session() as session:
            statement = select(CertificationsV).where(
                CertificationsV.product_version_id == product_version_id,
                CertificationsV.is_current == True
            )
            result = await session.exec(statement)
            return result.first()

    async def create_ingredients(self, ingredients_data: dict) -> IngredientsV:
        """Create new ingredients record"""
        from app.core.database import get_session
        
        async with get_session() as session:
            ingredients = IngredientsV(**ingredients_data)
            session.add(ingredients)
            await session.commit()
            await session.refresh(ingredients)
            return ingredients

    async def create_nutrition(self, nutrition_data: dict) -> NutritionV:
        """Create new nutrition record"""
        from app.core.database import get_session
        
        async with get_session() as session:
            nutrition = NutritionV(**nutrition_data)
            session.add(nutrition)
            await session.commit()
            await session.refresh(nutrition)
            return nutrition

    async def create_allergens(self, allergens_data: dict) -> AllergensV:
        """Create new allergens record"""
        from app.core.database import get_session
        
        async with get_session() as session:
            allergens = AllergensV(**allergens_data)
            session.add(allergens)
            await session.commit()
            await session.refresh(allergens)
            return allergens

    async def create_claims(self, claims_data: dict) -> ClaimsV:
        """Create new claims record"""
        from app.core.database import get_session
        
        async with get_session() as session:
            claims = ClaimsV(**claims_data)
            session.add(claims)
            await session.commit()
            await session.refresh(claims)
            return claims

    async def create_certifications(self, certifications_data: dict) -> CertificationsV:
        """Create new certifications record"""
        from app.core.database import get_session
        
        async with get_session() as session:
            certifications = CertificationsV(**certifications_data)
            session.add(certifications)
            await session.commit()
            await session.refresh(certifications)
            return certifications
