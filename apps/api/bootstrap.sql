
-- Insert tenant
INSERT INTO tenants (tenant_id, name, description, is_active, created_at, updated_at)
VALUES ('t-dev', 'Development Tenant', 'Development tenant for workers', true, '2025-08-24T04:18:38.837237', '2025-08-24T04:18:38.837237')
ON CONFLICT (tenant_id) DO UPDATE SET
    name = EXCLUDED.name,
    updated_at = EXCLUDED.updated_at;

-- Insert API key
INSERT INTO api_keys (tenant_id, hashed_key, name, role, is_active, created_at)
VALUES ('t-dev', '298754db2dbab6ec62605ceb0379eb7ee376580359449efe0caa3aa06cd56736', 'worker-dev-key', 'worker', true, '2025-08-24T04:18:38.837237')
ON CONFLICT (tenant_id, hashed_key) DO NOTHING;

-- Verify
SELECT 'Tenant:', tenant_id, name FROM tenants WHERE tenant_id = 't-dev';
SELECT 'API Key:', name, role FROM api_keys WHERE tenant_id = 't-dev' AND hashed_key = '298754db2dbab6ec62605ceb0379eb7ee376580359449efe0caa3aa06cd56736';
