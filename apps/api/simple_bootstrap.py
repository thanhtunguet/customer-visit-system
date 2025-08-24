#!/usr/bin/env python3
"""Simple bootstrap using sqlite3-style approach"""
import hashlib
import os
import sys
import subprocess
from datetime import datetime

def run_sql_via_backend():
    """Run SQL commands through database connection"""
    
    # Generate the SQL commands
    tenant_id = 't-dev'
    tenant_name = 'Development Tenant'
    api_key_value = 'dev-secret'
    key_hash = hashlib.sha256(api_key_value.encode()).hexdigest()
    key_name = 'worker-dev-key'
    now = datetime.utcnow().isoformat()
    
    sql_commands = f"""
-- Insert tenant
INSERT INTO tenants (tenant_id, name, description, is_active, created_at, updated_at)
VALUES ('{tenant_id}', '{tenant_name}', 'Development tenant for workers', true, '{now}', '{now}')
ON CONFLICT (tenant_id) DO UPDATE SET
    name = EXCLUDED.name,
    updated_at = EXCLUDED.updated_at;

-- Insert API key
INSERT INTO api_keys (tenant_id, hashed_key, name, role, is_active, created_at)
VALUES ('{tenant_id}', '{key_hash}', '{key_name}', 'worker', true, '{now}')
ON CONFLICT (tenant_id, hashed_key) DO NOTHING;

-- Verify
SELECT 'Tenant:', tenant_id, name FROM tenants WHERE tenant_id = '{tenant_id}';
SELECT 'API Key:', name, role FROM api_keys WHERE tenant_id = '{tenant_id}' AND hashed_key = '{key_hash}';
"""
    
    print("Generated SQL commands:")
    print(sql_commands)
    print("\n" + "="*50)
    print("API Key Details:")
    print(f"Tenant ID: {tenant_id}")
    print(f"API Key: {api_key_value}")
    print(f"Key Hash: {key_hash}")
    print("="*50)
    
    # Write SQL to file for manual execution
    with open('bootstrap.sql', 'w') as f:
        f.write(sql_commands)
    
    print("\nSQL commands written to bootstrap.sql")
    print("\nTo execute manually, run:")
    print("  psql postgresql://tungpt:@localhost:5432/facedb < bootstrap.sql")
    print("\nOr try using the database connection from your database tool.")
    
    return True

if __name__ == "__main__":
    success = run_sql_via_backend()
    sys.exit(0 if success else 1)