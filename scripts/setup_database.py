#!/usr/bin/env python3
"""
Enhanced database setup script with migration support
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_engine, db_manager, init_db
from app.core.logging import log


async def check_database_exists() -> bool:
    """Check if database exists"""
    try:
        async with db_manager.session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def create_database():
    """Create database if it doesn't exist"""
    # Parse database name from URL
    db_url = str(settings.database_url)
    db_name = db_url.split("/")[-1].split("?")[0]
    
    # Connect to postgres database to create our database
    postgres_url = db_url.replace(f"/{db_name}", "/postgres")
    
    try:
        # For PostgreSQL
        if "postgresql" in db_url:
            import asyncpg
            
            # Parse connection details
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            
            conn = await asyncpg.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database="postgres"
            )
            
            # Check if database exists
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
                db_name
            )
            
            if not exists:
                # Create database
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                log.info(f"Created database: {db_name}")
            else:
                log.info(f"Database already exists: {db_name}")
                
            await conn.close()
            
    except Exception as e:
        log.error(f"Error creating database: {e}")
        raise


async def setup_extensions():
    """Setup PostgreSQL extensions"""
    async with db_manager.session() as session:
        try:
            # Enable UUID extension
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            
            # Enable pgcrypto for better UUID generation
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            
            # Enable pg_trgm for text search
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            
            log.info("PostgreSQL extensions enabled")
            
        except Exception as e:
            log.warning(f"Could not create extensions (may already exist): {e}")


async def run_migrations():
    """Run Alembic migrations"""
    try:
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", str(settings.database_url))
        
        # Run migrations
        command.upgrade(config, "head")
        log.info("Database migrations completed")
        
    except Exception as e:
        log.error(f"Migration error: {e}")
        # If migrations fail, try creating tables directly
        log.info("Falling back to direct table creation...")
        await init_db()


async def create_initial_data():
    """Create initial data (categories, retailers, etc.)"""
    async with db_manager.session() as session:
        try:
            # Check if we have any brands
            result = await session.execute(text("SELECT COUNT(*) FROM brand"))
            count = result.scalar()
            
            if count == 0:
                log.info("Creating initial data...")
                
                # Create some initial categories
                categories = [
                    ("beverages", "Beverages"),
                    ("snacks", "Snacks & Branded Foods"),
                    ("dairy", "Dairy Products"),
                    ("staples", "Staples & Grains"),
                    ("bakery", "Bakery & Confectionery"),
                ]
                
                for code, name in categories:
                    await session.execute(
                        text("""
                            INSERT INTO category (category_id, code, name, level, created_at, updated_at)
                            VALUES (gen_random_uuid(), :code, :name, 1, NOW(), NOW())
                            ON CONFLICT DO NOTHING
                        """),
                        {"code": code, "name": name}
                    )
                
                # Create initial retailers
                retailers = [
                    ("bigbasket", "BigBasket", "bigbasket.com"),
                    ("blinkit", "Blinkit", "blinkit.com"),
                    ("zepto", "Zepto", "zeptonow.com"),
                    ("amazon_in", "Amazon India", "amazon.in"),
                ]
                
                for code, name, domain in retailers:
                    await session.execute(
                        text("""
                            INSERT INTO retailer (retailer_id, code, name, domain, country, is_active, created_at, updated_at)
                            VALUES (gen_random_uuid(), :code, :name, :domain, 'IN', true, NOW(), NOW())
                            ON CONFLICT DO NOTHING
                        """),
                        {"code": code, "name": name, "domain": domain}
                    )
                
                log.info("Initial data created")
                
        except Exception as e:
            log.warning(f"Could not create initial data: {e}")


async def verify_setup():
    """Verify database setup"""
    async with db_manager.session() as session:
        try:
            # Check core tables
            tables = [
                "brand",
                "product",
                "product_version",
                "category",
                "retailer",
                "processing_queue"
            ]
            
            for table in tables:
                result = await session.execute(
                    text(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'")
                )
                exists = result.scalar() > 0
                
                if exists:
                    log.info(f"✓ Table '{table}' exists")
                else:
                    log.error(f"✗ Table '{table}' missing")
                    
            # Check database health
            health = await check_database_health()
            log.info(f"Database health: {health}")
            
        except Exception as e:
            log.error(f"Verification error: {e}")


async def main():
    """Main setup function"""
    log.info("Starting database setup...")
    
    try:
        # Step 1: Create database if needed
        await create_database()
        
        # Step 2: Initialize connection
        await db_manager.init()
        
        # Step 3: Setup extensions
        await setup_extensions()
        
        # Step 4: Run migrations or create tables
        await run_migrations()
        
        # Step 5: Create initial data
        await create_initial_data()
        
        # Step 6: Verify setup
        await verify_setup()
        
        log.info("✅ Database setup completed successfully!")
        
    except Exception as e:
        log.error(f"❌ Database setup failed: {e}")
        sys.exit(1)
        
    finally:
        await db_manager.close()


if __name__ == "__main__":
    # Import this here to avoid circular imports
    from app.core.database import check_database_health
    
    asyncio.run(main())
