"""
API Schemas (Pydantic models for request/response)
"""
from .brand import BrandCreate, BrandUpdate, BrandRead, BrandReadWithProducts
from .product import (
    ProductCreate, ProductUpdate, ProductRead, ProductReadDetailed,
    ProductIdentifierCreate, ProductIdentifierRead,
    ProductVersionRead
)
from .category import (
    CategoryCreate, CategoryUpdate, CategoryRead, CategoryTree,
    ProductCategoryMapCreate, ProductCategoryMapRead
)
from .facts import (
    IngredientsCreate, IngredientsRead,
    NutritionCreate, NutritionRead,
    AllergensCreate, AllergensRead,
    ClaimsCreate, ClaimsRead,
    CertificationCreate, CertificationRead
)
from .score import SquorScoreRead, SquorComponentRead
from .common import PaginationParams, SearchParams

__all__ = [
    # Brand
    "BrandCreate", "BrandUpdate", "BrandRead", "BrandReadWithProducts",
    # Product
    "ProductCreate", "ProductUpdate", "ProductRead", "ProductReadDetailed",
    "ProductIdentifierCreate", "ProductIdentifierRead", "ProductVersionRead",
    # Category
    "CategoryCreate", "CategoryUpdate", "CategoryRead", "CategoryTree",
    "ProductCategoryMapCreate", "ProductCategoryMapRead",
    # Facts
    "IngredientsCreate", "IngredientsRead",
    "NutritionCreate", "NutritionRead",
    "AllergensCreate", "AllergensRead",
    "ClaimsCreate", "ClaimsRead",
    "CertificationCreate", "CertificationRead",
    # Score
    "SquorScoreRead", "SquorComponentRead",
    # Common
    "PaginationParams", "SearchParams"
]
