#!/usr/bin/env python3
"""Bootstrap API key for development"""
import hashlib
import os
from datetime import datetime

# Set up environment
os.chdir("/Users/tungpt/Development/thanhtunguet/face-recognition/apps/api")

# Import after changing directory
from app.core.database import SessionLocal
from app.models.database import ApiKey, Tenant


def main():
    """Create tenant and API key"""
    db = SessionLocal()

    try:
        # Create tenant
        tenant_id = "t-dev"
        tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            tenant = Tenant(
                tenant_id=tenant_id,
                name="Development Tenant",
                description="Development tenant for workers",
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(tenant)
            print(f"Created tenant: {tenant_id}")
        else:
            print(f"Tenant already exists: {tenant_id}")

        # Create API key
        api_key_value = "dev-secret"
        key_hash = hashlib.sha256(api_key_value.encode()).hexdigest()

        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.tenant_id == tenant_id, ApiKey.hashed_key == key_hash)
            .first()
        )

        if not api_key:
            api_key = ApiKey(
                tenant_id=tenant_id,
                hashed_key=key_hash,
                name="worker-dev-key",
                role="worker",
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db.add(api_key)
            print(f"Created API key: {key_hash}")
        else:
            print(f"API key already exists: {key_hash}")

        db.commit()

        # Verify
        tenant_check = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        api_key_check = (
            db.query(ApiKey)
            .filter(ApiKey.tenant_id == tenant_id, ApiKey.hashed_key == key_hash)
            .first()
        )

        print("\nVerification:")
        print(
            f"Tenant: {tenant_check.tenant_id} - {tenant_check.name}"
            if tenant_check
            else "Tenant not found"
        )
        print(
            f"API Key: {api_key_check.name} - {api_key_check.role}"
            if api_key_check
            else "API key not found"
        )
        print(f"API Key Value: {api_key_value}")
        print(f"Hash: {key_hash}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
