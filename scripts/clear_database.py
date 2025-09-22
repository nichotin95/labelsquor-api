#!/usr/bin/env python3
"""
Clear all data from database tables (for development)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import db_manager
from app.core.logging import log


async def clear_all_data():
    """Clear all data from tables while preserving schema"""
    
    # Tables to clear in order (respecting foreign key constraints)
    tables_to_clear = [
        # Clear workflow tables first (if they exist)
        "workflow_transitions",
        "workflow_metrics", 
        "workflow_events",
        "workflow_deadletter",
        "quota_usage_log",
        
        # Clear processing and analysis tables
        "processing_queue",
        "claim_analysis",
        "squor_score",
        "squor_component",
        
        # Clear version tables
        "allergens_v",
        "certifications_v",
        "claims_v",
        "ingredients_v",
        "nutrition_v",
        "product_version",
        
        # Clear product-related tables
        "product_image",
        "product_identifier",
        "product_category_map",
        "source_page",
        "product",
        
        # Clear master data tables
        "brand",
        "crawl_session",
        "crawl_rule",
        "job_run",
        "job",
        "refresh_request",
        "issue",
        
        # Keep these tables but clear non-essential data
        "category_attribute_schema",
        "category_policy_override",
        "category_synonym",
        "category_version",
    ]
    
    log.info("Starting database cleanup...")
    cleared_count = 0
    
    for table in tables_to_clear:
        async with db_manager.session() as session:
            try:
                # Check if table exists first
                result = await session.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = :table_name
                        )
                    """),
                    {"table_name": table}
                )
                exists = result.scalar()
                
                if not exists:
                    log.info(f"  {table} - table does not exist, skipping")
                    continue
                
                # Clear the table
                result = await session.execute(text(f"DELETE FROM {table}"))
                count = result.rowcount
                
                if count > 0:
                    log.info(f"✓ Cleared {count} rows from {table}")
                    cleared_count += 1
                else:
                    log.info(f"  {table} was already empty")
                    
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                log.warning(f"  Could not clear {table}: {e}")
    
    # Show summary
    log.info(f"\n✅ Database cleanup completed! Cleared data from {cleared_count} tables.")
    
    # Show remaining data counts
    async with db_manager.session() as session:
        log.info("\nRemaining data in master tables:")
        master_tables = ["category", "retailer", "quota_limits"]
        for table in master_tables:
            try:
                result = await session.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = :table_name
                        )
                    """),
                    {"table_name": table}
                )
                exists = result.scalar()
                
                if exists:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    log.info(f"  {table}: {count} rows")
                else:
                    log.info(f"  {table}: table does not exist")
            except Exception as e:
                log.warning(f"  Could not count {table}: {e}")


async def main():
    """Main function"""
    try:
        # Initialize database connection
        await db_manager.init()
        
        # Confirm before clearing
        print("\n⚠️  WARNING: This will DELETE all data from the database!")
        print("Master tables (category, retailer, quota_limits) will be preserved.")
        response = input("\nAre you sure you want to continue? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        
        # Clear data
        await clear_all_data()
        
    except Exception as e:
        log.error(f"Error: {e}")
        sys.exit(1)
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())