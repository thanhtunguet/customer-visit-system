-- Migration: Add site_id column to users table for site manager role restrictions
-- This script can be run directly on PostgreSQL

BEGIN;

-- Check if column already exists and add it if it doesn't
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
        
        -- Add index for better performance
        CREATE INDEX idx_users_site_id ON users(site_id);
        
        RAISE NOTICE 'Successfully added site_id column to users table';
    ELSE
        RAISE NOTICE 'site_id column already exists in users table';
    END IF;
END $$;

COMMIT;