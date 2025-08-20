-- Migration to convert customer_id and staff_id from BigInteger to String
-- This fixes the data type mismatch where the system expects string IDs like "cust-001"

-- Convert customers table
ALTER TABLE customers DROP CONSTRAINT customers_pkey;
ALTER TABLE customers ALTER COLUMN customer_id TYPE VARCHAR(64);
ALTER TABLE customers ADD PRIMARY KEY (tenant_id, customer_id);

-- Convert staff table  
ALTER TABLE staff DROP CONSTRAINT staff_pkey;
ALTER TABLE staff ALTER COLUMN staff_id TYPE VARCHAR(64);
ALTER TABLE staff ADD PRIMARY KEY (tenant_id, staff_id);

-- Update any existing numeric IDs to string format
UPDATE customers SET customer_id = 'cust-' || LPAD(customer_id, 6, '0') WHERE customer_id ~ '^[0-9]+$';
UPDATE staff SET staff_id = 'staff-' || LPAD(staff_id, 6, '0') WHERE staff_id ~ '^[0-9]+$';