"""
Scrapy items for LabelSquor crawlers
"""
import scrapy
from scrapy.item import Field


class ProductItem(scrapy.Item):
    """Product data structure"""
    # Source information
    retailer = Field()
    url = Field()
    crawled_at = Field()
    
    # Product basics
    name = Field()
    brand = Field()
    category = Field()
    subcategory = Field()
    breadcrumbs = Field()
    
    # Pricing
    price = Field()
    mrp = Field()
    discount = Field()
    currency = Field()
    
    # Availability
    in_stock = Field()
    seller = Field()
    
    # Images
    images = Field()  # List of image URLs
    primary_image = Field()
    
    # Product details
    description = Field()
    ingredients_text = Field()  # Raw ingredient text if found
    nutrition_text = Field()    # Raw nutrition text if found
    
    # Identifiers
    sku = Field()
    asin = Field()
    gtin = Field()
    
    # Ratings and reviews
    rating = Field()
    review_count = Field()
    
    # Additional metadata
    pack_size = Field()
    unit = Field()
    manufacturer = Field()
    country_of_origin = Field()
    
    # Certifications if visible
    certifications = Field()  # List of certification texts
    
    # HTML content (for detailed parsing later)
    page_html = Field()


class CategoryItem(scrapy.Item):
    """Category data for building taxonomy"""
    retailer = Field()
    category_id = Field()
    name = Field()
    parent_id = Field()
    url = Field()
    product_count = Field()
