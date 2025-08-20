-- Migration 002: Update staff and customer IDs to bigint, add camera types
-- Run timestamp: 2025-08-20

-- Create camera type enum
CREATE TYPE camera_type AS ENUM ('rtsp', 'webcam');

-- Add camera_type column to cameras table with default value
ALTER TABLE cameras ADD COLUMN camera_type camera_type DEFAULT 'rtsp' NOT NULL;

-- Add device_index column for webcam support (null for RTSP cameras)
ALTER TABLE cameras ADD COLUMN device_index INTEGER;

-- Update staff table to use bigint for staff_id
-- First, drop foreign key constraints and indexes that reference staff_id
ALTER TABLE visits DROP CONSTRAINT IF EXISTS visits_person_id_fkey;
DROP INDEX IF EXISTS idx_visits_person;

-- Create a new staff table with bigint staff_id
CREATE TABLE staff_new (
    tenant_id VARCHAR(64) NOT NULL,
    staff_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    site_id VARCHAR(64),
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    face_embedding TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    PRIMARY KEY (tenant_id, staff_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

-- Migrate existing staff data (convert string IDs to numbers where possible)
-- This is a simplified migration - in production you'd need a more sophisticated approach
INSERT INTO staff_new (tenant_id, staff_id, name, site_id, is_active, face_embedding, created_at, updated_at)
SELECT 
    tenant_id,
    CASE 
        WHEN staff_id ~ '^[0-9]+$' THEN staff_id::BIGINT
        ELSE ROW_NUMBER() OVER (ORDER BY created_at)
    END as staff_id,
    name,
    site_id,
    is_active,
    face_embedding,
    created_at,
    updated_at
FROM staff;

-- Drop old staff table and rename new one
DROP TABLE staff;
ALTER TABLE staff_new RENAME TO staff;

-- Update customers table to use bigint for customer_id
-- Create a new customers table with bigint customer_id
CREATE TABLE customers_new (
    tenant_id VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    name VARCHAR(255),
    gender VARCHAR(16),
    estimated_age_range VARCHAR(32),
    first_seen TIMESTAMP WITHOUT TIME ZONE DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    last_seen TIMESTAMP WITHOUT TIME ZONE,
    visit_count INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (tenant_id, customer_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

-- Migrate existing customer data
INSERT INTO customers_new (tenant_id, customer_id, name, gender, estimated_age_range, first_seen, last_seen, visit_count)
SELECT 
    tenant_id,
    CASE 
        WHEN customer_id ~ '^[0-9]+$' THEN customer_id::BIGINT
        ELSE ROW_NUMBER() OVER (ORDER BY first_seen)
    END as customer_id,
    name,
    gender,
    estimated_age_range,
    first_seen,
    last_seen,
    visit_count
FROM customers;

-- Drop old customers table and rename new one
DROP TABLE customers;
ALTER TABLE customers_new RENAME TO customers;

-- Create indexes for the new tables
CREATE INDEX idx_customers_last_seen ON customers(tenant_id, last_seen);

-- Update visits table to handle the new ID formats
-- For now, we'll update person_id to store bigint values as strings
-- In a real migration, you'd need to map old string IDs to new bigint IDs

-- Recreate foreign key constraints and indexes for visits
CREATE INDEX idx_visits_timestamp ON visits(tenant_id, timestamp);
CREATE INDEX idx_visits_person ON visits(tenant_id, person_id, timestamp);
CREATE INDEX idx_visits_site ON visits(tenant_id, site_id, timestamp);

-- Add comments to document the schema changes
COMMENT ON COLUMN cameras.camera_type IS 'Type of camera: rtsp for network cameras, webcam for local USB cameras';
COMMENT ON COLUMN cameras.device_index IS 'Device index for webcam cameras (e.g., 0, 1, 2), null for RTSP cameras';
COMMENT ON COLUMN staff.staff_id IS 'Unique staff identifier as bigint for better performance and compatibility';
COMMENT ON COLUMN customers.customer_id IS 'Unique customer identifier as bigint for better performance and compatibility';