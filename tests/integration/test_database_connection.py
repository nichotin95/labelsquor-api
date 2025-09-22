#!/usr/bin/env python3
"""
Quick test to verify database connection and basic operations
"""

import asyncio
import asyncpg
import os
from datetime import datetime
from uuid import uuid4

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


async def test_database():
    """Run basic database tests"""
    print("🔄 Testing Database Connection...")
    
    try:
        # Connect
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to database")
        
        # Test 1: Check version
        version = await conn.fetchval("SELECT version()")
        print(f"📊 PostgreSQL version: {version.split(',')[0]}")
        
        # Test 2: Count tables
        table_count = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        print(f"📋 Total tables: {table_count}")
        
        # Test 3: Insert test brand
        brand_id = uuid4()
        test_suffix = datetime.now().strftime("%Y%m%d%H%M%S")
        brand_name = f"Test Brand {test_suffix}"
        normalized_name = f"test-brand-{test_suffix}"
        
        await conn.execute("""
            INSERT INTO brand (brand_id, name, normalized_name)
            VALUES ($1, $2, $3)
        """, brand_id, brand_name, normalized_name)
        print(f"✅ Inserted test brand: {brand_name}")
        
        # Test 4: Insert test product
        product_id = uuid4()
        canonical_key = f"{brand_id}:test-product"
        await conn.execute("""
            INSERT INTO product (product_id, brand_id, canonical_key, name, normalized_name)
            VALUES ($1, $2, $3, $4, $5)
        """, product_id, brand_id, canonical_key, "Test Product", "test-product")
        print("✅ Inserted test product")
        
        # Test 5: Create product version
        version_id = uuid4()
        await conn.execute("""
            INSERT INTO product_version (product_version_id, product_id, version_seq)
            VALUES ($1, $2, 
                (SELECT COALESCE(MAX(version_seq), 0) + 1 
                 FROM product_version 
                 WHERE product_id = $2)
            )
        """, version_id, product_id)
        print("✅ Created product version")
        
        # Test 6: Insert ingredients (SCD Type-2)
        ingredients_id = uuid4()
        await conn.execute("""
            INSERT INTO ingredients_v (
                ingredients_id, 
                product_version_id,
                raw_text,
                normalized_list_json,
                confidence,
                is_current
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """, 
            ingredients_id, 
            version_id,
            "Test ingredients: wheat, sugar, salt",
            '["wheat", "sugar", "salt"]',
            0.95,
            True
        )
        print("✅ Inserted ingredients with SCD Type-2")
        
        # Test 7: Query the data
        result = await conn.fetchrow("""
            SELECT 
                p.name as product_name,
                b.name as brand_name,
                pv.version_seq,
                i.raw_text as ingredients
            FROM product p
            JOIN brand b ON p.brand_id = b.brand_id
            JOIN product_version pv ON p.product_id = pv.product_id
            JOIN ingredients_v i ON pv.product_version_id = i.product_version_id
            WHERE p.name = 'Test Product'
            AND i.is_current = true
        """)
        
        if result:
            print("\n📊 Query Result:")
            print(f"   Product: {result['product_name']}")
            print(f"   Brand: {result['brand_name']}")
            print(f"   Version: {result['version_seq']}")
            print(f"   Ingredients: {result['ingredients']}")
        
        # Clean up
        await conn.execute("DELETE FROM ingredients_v WHERE ingredients_id = $1", ingredients_id)
        await conn.execute("DELETE FROM product_version WHERE product_version_id = $1", version_id)
        await conn.execute("DELETE FROM product WHERE product_id = $1", product_id)
        await conn.execute("DELETE FROM brand WHERE brand_id = $1", brand_id)
        print("\n🧹 Cleaned up test data")
        
        await conn.close()
        print("\n✅ ALL TESTS PASSED!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_database())
