#!/usr/bin/env python3
"""Create API key for worker authentication"""
import asyncio
import hashlib
import os
import sys

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import get_db_session
from app.models.database import APIKey


async def create_worker_api_key():
    """Create or update API key for worker"""
    api_key_value = "dev-secret"
    key_name = "worker-dev-key"

    # Hash the API key
    key_hash = hashlib.sha256(api_key_value.encode()).hexdigest()

    async for db_session in get_db_session():
        try:
            # Check if API key already exists
            existing_key = await db_session.get(APIKey, key_name)

            if existing_key:
                # Update existing key
                existing_key.key_hash = key_hash
                existing_key.role = "worker"
                existing_key.is_active = True
                print(f"Updated existing API key: {key_name}")
            else:
                # Create new API key
                api_key = APIKey(
                    id=key_name,
                    name=key_name,
                    key_hash=key_hash,
                    role="worker",
                    is_active=True,
                )
                db_session.add(api_key)
                print(f"Created new API key: {key_name}")

            await db_session.commit()
            print(f"API key hash: {key_hash}")
            print("Worker API key setup complete!")

        except Exception as e:
            await db_session.rollback()
            print(f"Error creating API key: {e}")
            raise
        finally:
            break


if __name__ == "__main__":
    asyncio.run(create_worker_api_key())
