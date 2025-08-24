#!/usr/bin/env python3
"""Bootstrap script to set up tenant and API key for worker"""
import asyncio
import hashlib
import os
import sys
from datetime import datetime

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

# Use raw SQL to avoid dependency issues
import psycopg2

def setup_worker_data():
    """Setup tenant and API key for worker using raw SQL"""
    try:
        # Database connection from environment
        db_url = os.getenv('DATABASE_URL', 'postgresql://tungpt:@localhost:5432/facedb')
        
        # Parse the URL to get connection parameters
        if db_url.startswith('postgresql://'):
            # Remove postgresql:// prefix
            db_url = db_url[13:]
        elif db_url.startswith('postgresql+asyncpg://'):
            # Remove postgresql+asyncpg:// prefix  
            db_url = db_url[21:]
            
        # Split user:pass@host:port/db
        parts = db_url.split('@')
        if len(parts) == 2:
            user_pass = parts[0]
            host_port_db = parts[1]
            
            # Parse user:pass
            if ':' in user_pass:
                user, password = user_pass.split(':', 1)
            else:
                user = user_pass
                password = ''
            
            # Parse host:port/db
            host_port, database = host_port_db.split('/', 1)
            if ':' in host_port:
                host, port = host_port.split(':', 1)
                port = int(port)
            else:
                host = host_port
                port = 5432
        else:
            # Default values
            host = 'localhost'
            port = 5432
            user = 'tungpt'
            password = ''
            database = 'facedb'
        
        print(f"Connecting to PostgreSQL: host={host}, port={port}, user={user}, database={database}")
        
        # Connect to database
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        cur = conn.cursor()
        
        # 1. Create tenant t-dev if it doesn't exist
        tenant_id = 't-dev'
        tenant_name = 'Development Tenant'
        
        print(f"Creating tenant: {tenant_id}")
        
        cur.execute("""
            INSERT INTO tenants (tenant_id, name, description, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id) DO UPDATE SET
                name = EXCLUDED.name,
                updated_at = EXCLUDED.updated_at
        """, (tenant_id, tenant_name, 'Development tenant for workers', True, datetime.utcnow(), datetime.utcnow()))
        
        # 2. Create API key for worker
        api_key_value = 'dev-secret'
        key_hash = hashlib.sha256(api_key_value.encode()).hexdigest()
        key_name = 'worker-dev-key'
        
        print(f"Creating API key: {key_name}")
        print(f"API key hash: {key_hash}")
        
        cur.execute("""
            INSERT INTO api_keys (tenant_id, hashed_key, name, role, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, hashed_key) DO UPDATE SET
                name = EXCLUDED.name,
                role = EXCLUDED.role,
                is_active = EXCLUDED.is_active
        """, (tenant_id, key_hash, key_name, 'worker', True, datetime.utcnow()))
        
        # Commit changes
        conn.commit()
        print("✅ Successfully created tenant and API key")
        
        # Verify the setup
        cur.execute("SELECT tenant_id, name FROM tenants WHERE tenant_id = %s", (tenant_id,))
        tenant_row = cur.fetchone()
        print(f"✅ Tenant verified: {tenant_row}")
        
        cur.execute("SELECT name, role FROM api_keys WHERE tenant_id = %s AND hashed_key = %s", (tenant_id, key_hash))
        api_key_row = cur.fetchone()
        print(f"✅ API key verified: {api_key_row}")
        
        cur.close()
        conn.close()
        
        print("\n🎉 Worker setup complete!")
        print(f"Tenant ID: {tenant_id}")
        print(f"API Key: {api_key_value}")
        print("Workers can now authenticate using this API key.")
        
        return True
        
    except ImportError:
        print("❌ psycopg2 not available. Please install: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Error setting up worker data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = setup_worker_data()
    sys.exit(0 if success else 1)