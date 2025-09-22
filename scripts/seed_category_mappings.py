#!/usr/bin/env python3
"""
Seed category mappings for retailers
"""

import asyncio
from app.core.database import db_manager
from app.models.crawler_config import CategoryMapping
from sqlalchemy import text

async def seed_category_mappings():
    """Add basic category mappings for testing"""
    await db_manager.init()
    
    # Basic BigBasket category mappings
    mappings = [
        {
            "retailer": "bigbasket",
            "internal_category": "snacks",
            "retailer_category_name": "Snacks & Branded Foods",
            "retailer_category_path": "/pc/Snacks-Branded-Foods/",
            "level": 1,
            "is_active": True
        },
        {
            "retailer": "bigbasket", 
            "internal_category": "beverages",
            "retailer_category_name": "Beverages",
            "retailer_category_path": "/pc/Beverages/",
            "level": 1,
            "is_active": True
        },
        {
            "retailer": "bigbasket",
            "internal_category": "dairy",
            "retailer_category_name": "Eggs, Meat & Fish",
            "retailer_category_path": "/pc/Eggs-Meat-Fish/",
            "level": 1,
            "is_active": True
        },
        {
            "retailer": "bigbasket",
            "internal_category": "staples",
            "retailer_category_name": "Foodgrains, Oil & Masala",
            "retailer_category_path": "/pc/Foodgrains-Oil-Masala/",
            "level": 1,
            "is_active": True
        }
    ]
    
    async with db_manager.session() as session:
        # Clear existing mappings
        await session.execute(text("DELETE FROM category_mapping WHERE retailer = 'bigbasket'"))
        
        # Add new mappings
        for mapping_data in mappings:
            mapping = CategoryMapping(**mapping_data)
            session.add(mapping)
        
        await session.commit()
        print(f"✅ Added {len(mappings)} category mappings for BigBasket")
        
        # Verify
        result = await session.execute(text("SELECT COUNT(*) FROM category_mapping"))
        count = result.scalar()
        print(f"✅ Total category mappings in database: {count}")
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(seed_category_mappings())
