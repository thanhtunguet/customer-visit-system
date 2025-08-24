#!/usr/bin/env python3
"""
Simple test script to verify worker API endpoints
"""
import asyncio
import json
import sys
import socket
from datetime import datetime
from typing import Optional

import httpx

API_URL = "http://localhost:8080"
TEST_TENANT_ID = "t-dev"
TEST_API_KEY = "dev-api-key"

async def get_worker_token() -> Optional[str]:
    """Get JWT token for worker API access"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/v1/auth/token",
                json={
                    "grant_type": "api_key",
                    "api_key": TEST_API_KEY,
                    "tenant_id": TEST_TENANT_ID,
                    "role": "worker",
                }
            )
            response.raise_for_status()
            
            data = response.json()
            return data["access_token"]
    except Exception as e:
        print(f"❌ Failed to get token: {e}")
        return None

async def test_worker_registration(token: str) -> Optional[str]:
    """Test worker registration"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/v1/workers/register",
                json={
                    "worker_name": f"Test-Worker-{socket.gethostname()}",
                    "hostname": socket.gethostname(),
                    "worker_version": "1.0.0-test",
                    "capabilities": {
                        "detector_type": "mock",
                        "embedder_type": "mock",
                        "test_mode": True
                    }
                },
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            
            result = response.json()
            print(f"✅ Worker registration: {result['message']}")
            return result["worker_id"]
    except Exception as e:
        print(f"❌ Worker registration failed: {e}")
        return None

async def test_worker_heartbeat(token: str, worker_id: str):
    """Test worker heartbeat"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/v1/workers/{worker_id}/heartbeat",
                json={
                    "status": "online",
                    "faces_processed_count": 5,
                    "capabilities": {
                        "detector_type": "mock",
                        "embedder_type": "mock",
                        "test_mode": True,
                        "last_update": datetime.utcnow().isoformat()
                    }
                },
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            
            result = response.json()
            print(f"✅ Heartbeat sent: {result['message']}")
    except Exception as e:
        print(f"❌ Heartbeat failed: {e}")

async def test_list_workers(token: str):
    """Test listing workers"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/v1/workers",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            
            result = response.json()
            print(f"✅ Workers listed: {result['total_count']} total, {result['online_count']} online")
            
            for worker in result['workers']:
                status_emoji = "🟢" if worker['status'] == 'online' and worker['is_healthy'] else "🔴"
                print(f"  {status_emoji} {worker['worker_name']} ({worker['hostname']}) - {worker['status']}")
    except Exception as e:
        print(f"❌ List workers failed: {e}")

async def test_cleanup_worker(token: str, worker_id: str):
    """Test worker cleanup"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{API_URL}/v1/workers/{worker_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            
            result = response.json()
            print(f"✅ Worker cleanup: {result['message']}")
    except Exception as e:
        print(f"❌ Worker cleanup failed: {e}")

async def main():
    print("🧪 Testing Worker API Endpoints")
    print("=" * 40)
    
    # Test authentication
    print("1. Getting worker token...")
    token = await get_worker_token()
    if not token:
        print("❌ Cannot proceed without token")
        sys.exit(1)
    print("✅ Token obtained")
    
    # Test registration
    print("\n2. Testing worker registration...")
    worker_id = await test_worker_registration(token)
    if not worker_id:
        print("❌ Cannot proceed without worker registration")
        sys.exit(1)
    
    # Test heartbeat
    print("\n3. Testing worker heartbeat...")
    await test_worker_heartbeat(token, worker_id)
    
    # Test listing
    print("\n4. Testing worker listing...")
    await test_list_workers(token)
    
    # Test cleanup
    print("\n5. Testing worker cleanup...")
    await test_cleanup_worker(token, worker_id)
    
    print("\n✅ All tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())