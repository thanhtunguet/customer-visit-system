#!/usr/bin/env python3
"""
Manual migration script to add site_id to users table
Run this if alembic migrations aren't working
"""
import asyncio
import sys
import os
from sqlalchemy import text

# Add the parent directory to the path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_session

async def run_migration():
    """Apply the site_id migration manually"""
    
    migration_sql = """
    -- Check if column already exists
    DO $$ 
    BEGIN 
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'site_id'
        ) THEN
            -- Add site_id column
            ALTER TABLE users ADD COLUMN site_id BIGINT;
            
            -- Add foreign key constraint
            ALTER TABLE users ADD CONSTRAINT fk_users_site_id 
            FOREIGN KEY (site_id) REFERENCES sites(site_id) ON DELETE CASCADE;
            
            -- Add index
            CREATE INDEX idx_users_site_id ON users(site_id);
            
            RAISE NOTICE 'Successfully added site_id column to users table';
        ELSE
            RAISE NOTICE 'site_id column already exists in users table';
        END IF;
    END $$;
    """
    
    async for db in get_db_session():
        try:
            await db.execute(text(migration_sql))
            await db.commit()
            print("✅ Migration completed successfully!")
            break
        except Exception as e:
            await db.rollback()
            print(f"❌ Migration failed: {e}")
            raise
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(run_migration())