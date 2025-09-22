"""
API Schemas (Pydantic models for request/response)
"""

from .brand import BrandCreate, BrandRead, BrandReadWithProducts, BrandUpdate
from .category import (
    CategoryCreate,
    CategoryRead,
    CategoryTree,
    CategoryUpdate,
    ProductCategoryMapCreate,
    ProductCategoryMapRead,
)
from .common import PaginationParams, SearchParams
from .facts import (
    AllergensCreate,
    AllergensRead,
    CertificationCreate,
    CertificationRead,
    ClaimsCreate,
    ClaimsRead,
    IngredientsCreate,
    IngredientsRead,
    NutritionCreate,
    NutritionRead,
)
from .product import (
    ProductCreate,
    ProductIdentifierCreate,
    ProductIdentifierRead,
    ProductRead,
    ProductReadDetailed,
    ProductUpdate,
    ProductVersionRead,
)
from .score import SquorComponentRead, SquorScoreRead

__all__ = [
    # Brand
    "BrandCreate",
    "BrandUpdate",
    "BrandRead",
    "BrandReadWithProducts",
    # Product
    "ProductCreate",
    "ProductUpdate",
    "ProductRead",
    "ProductReadDetailed",
    "ProductIdentifierCreate",
    "ProductIdentifierRead",
    "ProductVersionRead",
    # Category
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryRead",
    "CategoryTree",
    "ProductCategoryMapCreate",
    "ProductCategoryMapRead",
    # Facts
    "IngredientsCreate",
    "IngredientsRead",
    "NutritionCreate",
    "NutritionRead",
    "AllergensCreate",
    "AllergensRead",
    "ClaimsCreate",
    "ClaimsRead",
    "CertificationCreate",
    "CertificationRead",
    # Score
    "SquorScoreRead",
    "SquorComponentRead",
    # Common
    "PaginationParams",
    "SearchParams",
]
