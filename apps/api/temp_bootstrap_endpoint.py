#!/usr/bin/env python3
"""Temporary bootstrap endpoint - DO NOT USE IN PRODUCTION"""
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import hashlib
import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import get_db

router = APIRouter()

@router.post("/bootstrap/setup-worker")
async def setup_worker(db: Session = Depends(get_db)):
    """Bootstrap tenant and API key for worker - DEVELOPMENT ONLY"""
    try:
        tenant_id = 't-dev'
        tenant_name = 'Development Tenant'
        api_key_value = 'dev-secret'
        key_hash = hashlib.sha256(api_key_value.encode()).hexdigest()
        key_name = 'worker-dev-key'
        now = datetime.utcnow()
        
        # Insert tenant
        db.execute(text("""
            INSERT INTO tenants (tenant_id, name, description, is_active, created_at, updated_at)
            VALUES (:tenant_id, :name, :description, :is_active, :created_at, :updated_at)
            ON CONFLICT (tenant_id) DO UPDATE SET
                name = EXCLUDED.name,
                updated_at = EXCLUDED.updated_at
        """), {
            'tenant_id': tenant_id,
            'name': tenant_name, 
            'description': 'Development tenant for workers',
            'is_active': True,
            'created_at': now,
            'updated_at': now
        })
        
        # Insert API key
        db.execute(text("""
            INSERT INTO api_keys (tenant_id, hashed_key, name, role, is_active, created_at)
            VALUES (:tenant_id, :hashed_key, :name, :role, :is_active, :created_at)
            ON CONFLICT (tenant_id, hashed_key) DO NOTHING
        """), {
            'tenant_id': tenant_id,
            'hashed_key': key_hash,
            'name': key_name,
            'role': 'worker',
            'is_active': True,
            'created_at': now
        })
        
        db.commit()
        
        return {
            "message": "Worker setup complete",
            "tenant_id": tenant_id,
            "api_key": api_key_value,
            "key_hash": key_hash
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")

# Test it directly
if __name__ == "__main__":
    print("This would set up the worker data if added to the main app")