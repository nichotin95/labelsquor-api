"""
SQLModel database models
"""

from .brand import Brand
from .category import Category, CategorySynonym, ProductCategoryMap
from .category_extended import CategoryAttributeSchema, CategoryPolicyOverride, CategoryVersion
from .claim_analysis import ClaimAnalysis
from .crawler_config import CategoryMapping, CrawlerConfig, CrawlPlan, SearchTerm
from .discovery import DiscoveryTask, TaskResult
from .facts import AllergensV, CertificationsV, ClaimsV, IngredientsV, NutritionV
from .ops import Issue, Job, JobRun, RefreshRequest
from .product import Product, ProductIdentifier, ProductVersion
from .retailer import CrawlRule, CrawlSession, ProcessingQueue, Retailer
from .score import PolicyCatalog, SquorComponent, SquorScore
from .source import Artifact, ProductImage, SourcePage
from .ai_analysis import ProductAnalysis, ProductIngredient, ProductNutrition, ProductClaim, ProductWarning

__all__ = [
    "Brand",
    "Product",
    "ProductIdentifier",
    "ProductVersion",
    "Category",
    "CategorySynonym",
    "ProductCategoryMap",
    "CategoryVersion",
    "CategoryAttributeSchema",
    "CategoryPolicyOverride",
    "Retailer",
    "CrawlSession",
    "ProcessingQueue",
    "CrawlRule",
    "SearchTerm",
    "CategoryMapping",
    "CrawlerConfig",
    "CrawlPlan",
    "DiscoveryTask",
    "TaskResult",
    "SourcePage",
    "ProductImage",
    "Artifact",
    "IngredientsV",
    "NutritionV",
    "AllergensV",
    "ClaimsV",
    "CertificationsV",
    "SquorScore",
    "SquorComponent",
    "PolicyCatalog",
    "Job",
    "JobRun",
    "RefreshRequest",
    "Issue",
    "ClaimAnalysis",
    "ProductAnalysis",
    "ProductIngredient", 
    "ProductNutrition",
    "ProductClaim",
    "ProductWarning",
]
