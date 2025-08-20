-- Migration to convert IDs back to auto-incrementing integers
-- This provides simpler, automatically generated IDs for cameras, staff, and customers

-- First, let's handle visits table references
-- We'll need to update visits to use integer references

-- Create new sequence for customers
CREATE SEQUENCE IF NOT EXISTS customers_id_seq;

-- Create new sequence for staff  
CREATE SEQUENCE IF NOT EXISTS staff_id_seq;

-- Create new sequence for cameras
CREATE SEQUENCE IF NOT EXISTS cameras_id_seq;

-- Convert customers table
-- 1. Add new integer column
ALTER TABLE customers ADD COLUMN new_customer_id INTEGER;

-- 2. Populate with sequence values for existing records
UPDATE customers SET new_customer_id = nextval('customers_id_seq');

-- 3. Update visits table to reference new IDs (if exists)
-- First add new column to visits
ALTER TABLE visits ADD COLUMN new_person_id INTEGER;

-- Update visits that reference customers
UPDATE visits 
SET new_person_id = c.new_customer_id 
FROM customers c 
WHERE visits.person_id = c.customer_id 
AND visits.person_type = 'customer';

-- 4. Drop old constraints and rename columns
ALTER TABLE customers DROP CONSTRAINT customers_pkey;
ALTER TABLE customers DROP COLUMN customer_id;
ALTER TABLE customers RENAME COLUMN new_customer_id TO customer_id;
ALTER TABLE customers ALTER COLUMN customer_id SET NOT NULL;
ALTER TABLE customers ALTER COLUMN customer_id SET DEFAULT nextval('customers_id_seq');
ALTER TABLE customers ADD PRIMARY KEY (tenant_id, customer_id);

-- Convert staff table
-- 1. Add new integer column  
ALTER TABLE staff ADD COLUMN new_staff_id INTEGER;

-- 2. Populate with sequence values for existing records
UPDATE staff SET new_staff_id = nextval('staff_id_seq');

-- 3. Update visits that reference staff
UPDATE visits 
SET new_person_id = s.new_staff_id 
FROM staff s 
WHERE visits.person_id = s.staff_id 
AND visits.person_type = 'staff';

-- 4. Drop old constraints and rename columns
ALTER TABLE staff DROP CONSTRAINT staff_pkey;
ALTER TABLE staff DROP COLUMN staff_id;
ALTER TABLE staff RENAME COLUMN new_staff_id TO staff_id;
ALTER TABLE staff ALTER COLUMN staff_id SET NOT NULL;
ALTER TABLE staff ALTER COLUMN staff_id SET DEFAULT nextval('staff_id_seq');
ALTER TABLE staff ADD PRIMARY KEY (tenant_id, staff_id);

-- Convert cameras table
-- 1. Add new integer column
ALTER TABLE cameras ADD COLUMN new_camera_id INTEGER;

-- 2. Populate with sequence values for existing records
UPDATE cameras SET new_camera_id = nextval('cameras_id_seq');

-- 3. Update visits that reference cameras
UPDATE visits 
SET camera_id = c.new_camera_id::TEXT
FROM cameras c 
WHERE visits.camera_id = c.camera_id;

-- 4. Drop old constraints and rename columns
ALTER TABLE cameras DROP CONSTRAINT cameras_pkey;
ALTER TABLE cameras DROP COLUMN camera_id;
ALTER TABLE cameras RENAME COLUMN new_camera_id TO camera_id;
ALTER TABLE cameras ALTER COLUMN camera_id SET NOT NULL;
ALTER TABLE cameras ALTER COLUMN camera_id SET DEFAULT nextval('cameras_id_seq');
ALTER TABLE cameras ADD PRIMARY KEY (tenant_id, site_id, camera_id);

-- Update visits table to use new integer person_id
ALTER TABLE visits DROP COLUMN person_id;
ALTER TABLE visits RENAME COLUMN new_person_id TO person_id;
ALTER TABLE visits ALTER COLUMN person_id SET NOT NULL;

-- Update visits camera_id to integer if needed
ALTER TABLE visits ALTER COLUMN camera_id TYPE INTEGER USING camera_id::INTEGER;

-- Set sequence values to current max + 1 to avoid conflicts
SELECT setval('customers_id_seq', COALESCE((SELECT MAX(customer_id) FROM customers), 0) + 1, false);
SELECT setval('staff_id_seq', COALESCE((SELECT MAX(staff_id) FROM staff), 0) + 1, false);
SELECT setval('cameras_id_seq', COALESCE((SELECT MAX(camera_id) FROM cameras), 0) + 1, false);