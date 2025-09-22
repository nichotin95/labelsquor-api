#!/usr/bin/env python3
"""
Reset database - drop all tables and recreate from SQLModel definitions
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import db_manager, async_engine
from app.core.logging import log
from sqlmodel import SQLModel

# Import all models to ensure they're registered with SQLModel
# This will import all models through the __init__.py file
import app.models


async def drop_all_tables():
    """Drop all tables in the database"""
    async with db_manager.session() as session:
        try:
            # Get all table names
            result = await session.execute(
                text("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public' 
                    AND tablename NOT LIKE 'spatial_ref_sys'
                    ORDER BY tablename
                """)
            )
            tables = [row[0] for row in result]
            
            if not tables:
                log.info("No tables to drop")
                return
            
            log.info(f"Found {len(tables)} tables to drop")
            
            # Disable foreign key checks
            await session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
            
            # Drop all tables
            for table in tables:
                try:
                    await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    log.info(f"  ✓ Dropped table: {table}")
                except Exception as e:
                    log.warning(f"  ✗ Could not drop {table}: {e}")
            
            # Drop Alembic version table separately
            await session.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            log.info("  ✓ Dropped table: alembic_version")
            
            await session.commit()
            log.info("All tables dropped successfully")
            
        except Exception as e:
            await session.rollback()
            log.error(f"Error dropping tables: {e}")
            raise


async def create_all_tables():
    """Create all tables from SQLModel definitions"""
    try:
        log.info("Creating all tables from SQLModel definitions...")
        
        # Create all tables
        async with async_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
            
        log.info("✅ All tables created successfully")
        
        # List created tables
        async with db_manager.session() as session:
            result = await session.execute(
                text("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public' 
                    ORDER BY tablename
                """)
            )
            tables = [row[0] for row in result]
            
            log.info(f"\nCreated {len(tables)} tables:")
            for table in tables:
                log.info(f"  • {table}")
                
    except Exception as e:
        log.error(f"Error creating tables: {e}")
        raise


async def setup_initial_data():
    """Create initial master data"""
    async with db_manager.session() as session:
        try:
            log.info("\nSetting up initial data...")
            
            # Create categories
            categories = [
                ("beverages", "Beverages"),
                ("snacks", "Snacks & Branded Foods"),
                ("dairy", "Dairy Products"),
                ("staples", "Staples & Grains"),
                ("bakery", "Bakery & Confectionery"),
                ("personal-care", "Personal Care"),
                ("household", "Household & Cleaning"),
            ]
            
            for slug, name in categories:
                await session.execute(
                    text("""
                        INSERT INTO category (category_id, slug, name, locale, rank, is_active, created_at, updated_at)
                        VALUES (gen_random_uuid(), :slug, :name, 'en-IN', 1, true, NOW(), NOW())
                        ON CONFLICT DO NOTHING
                    """),
                    {"slug": slug, "name": name}
                )
            
            # Create retailers
            retailers = [
                ("bigbasket", "BigBasket", "bigbasket.com", "IN"),
                ("blinkit", "Blinkit", "blinkit.com", "IN"),
                ("zepto", "Zepto", "zeptonow.com", "IN"),
                ("amazon_in", "Amazon India", "amazon.in", "IN"),
                ("flipkart", "Flipkart", "flipkart.com", "IN"),
                ("jiomart", "JioMart", "jiomart.com", "IN"),
                ("swiggy_instamart", "Swiggy Instamart", "swiggy.com", "IN"),
                ("dunzo", "Dunzo", "dunzo.in", "IN"),
            ]
            
            for code, name, domain, country in retailers:
                await session.execute(
                    text("""
                        INSERT INTO retailer (
                            retailer_id, code, name, domain, country, is_active, 
                            rate_limit_rps, priority, crawl_frequency_hours, 
                            created_at, updated_at
                        )
                        VALUES (
                            gen_random_uuid(), :code, :name, :domain, :country, true,
                            2, 1, 24, NOW(), NOW()
                        )
                        ON CONFLICT DO NOTHING
                    """),
                    {"code": code, "name": name, "domain": domain, "country": country}
                )
            
            await session.commit()
            log.info("✅ Initial data created")
            
        except Exception as e:
            await session.rollback()
            log.error(f"Error creating initial data: {e}")
            raise


async def create_alembic_version_table():
    """Create Alembic version table and stamp it"""
    async with db_manager.session() as session:
        try:
            # Create alembic_version table
            await session.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS alembic_version (
                        version_num VARCHAR(32) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    )
                """)
            )
            
            # Stamp with latest revision (this marks the database as up-to-date)
            # We'll need to get the latest revision ID
            await session.execute(
                text("""
                    INSERT INTO alembic_version (version_num) 
                    VALUES ('3abc3b73b4a9')
                    ON CONFLICT DO NOTHING
                """)
            )
            
            await session.commit()
            log.info("✅ Alembic version table created and stamped")
            
        except Exception as e:
            await session.rollback()
            log.error(f"Error creating Alembic version table: {e}")


async def main():
    """Main function"""
    try:
        # Initialize database connection
        await db_manager.init()
        
        # Confirm before resetting
        print("\n⚠️  WARNING: This will DROP ALL TABLES and recreate them!")
        print("All data will be permanently lost.")
        response = input("\nAre you sure you want to continue? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        
        # Step 1: Drop all tables
        await drop_all_tables()
        
        # Step 2: Create all tables from SQLModel
        await create_all_tables()
        
        # Step 3: Create initial data
        await setup_initial_data()
        
        # Step 4: Setup Alembic
        await create_alembic_version_table()
        
        log.info("\n🎉 Database reset completed successfully!")
        
    except Exception as e:
        log.error(f"Database reset failed: {e}")
        sys.exit(1)
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
