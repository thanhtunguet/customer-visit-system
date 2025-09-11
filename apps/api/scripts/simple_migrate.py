#!/usr/bin/env python3
"""
Simple migration script to add site_id to users table
"""
import asyncio
import os

import asyncpg
from dotenv import load_dotenv


async def run_migration():
    """Apply the site_id migration manually"""

    # Load environment variables
    load_dotenv()

    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not found in environment")
        return

    print("Connecting to database...")

    try:
        conn = await asyncpg.connect(db_url)

        # Check if column already exists
        check_sql = """
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'site_id';
        """

        result = await conn.fetchval(check_sql)

        if result > 0:
            print("✅ site_id column already exists in users table")
            return

        # Add site_id column
        migration_sql = """
        BEGIN;
        
        -- Add site_id column
        ALTER TABLE users ADD COLUMN site_id BIGINT;
        
        -- Add foreign key constraint
        ALTER TABLE users ADD CONSTRAINT fk_users_site_id 
        FOREIGN KEY (site_id) REFERENCES sites(site_id) ON DELETE CASCADE;
        
        -- Add index
        CREATE INDEX idx_users_site_id ON users(site_id);
        
        COMMIT;
        """

        await conn.execute(migration_sql)
        print("✅ Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        if "conn" in locals():
            await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
