#!/usr/bin/env python3
"""
Test worker authentication
"""
import asyncio
import os
import sys

import httpx

# Configuration
API_URL = "http://localhost:8080"
TENANT_ID = "t-dev"
API_KEY = "dev-api-key"

async def test_worker_auth():
    """Test worker authentication"""
    try:
        async with httpx.AsyncClient() as client:
            # Test authentication
            response = await client.post(
                f"{API_URL}/v1/auth/token",
                json={
                    "grant_type": "api_key",
                    "api_key": API_KEY,
                    "tenant_id": TENANT_ID,
                    "role": "worker",
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Authentication successful!")
                print(f"Token received: {data['access_token'][:50]}...")
                
                # Test worker registration with the token
                token = data["access_token"]
                reg_response = await client.post(
                    f"{API_URL}/v1/workers/register",
                    json={
                        "worker_name": "Test Worker",
                        "hostname": "test-host",
                        "worker_version": "1.0.0",
                        "capabilities": {"test": True}
                    },
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if reg_response.status_code == 200:
                    reg_data = reg_response.json()
                    print(f"✅ Worker registration successful!")
                    print(f"Worker ID: {reg_data['worker_id']}")
                    return True
                else:
                    print(f"❌ Worker registration failed: {reg_response.status_code}")
                    print(f"Response: {reg_response.text}")
                    return False
            else:
                print(f"❌ Authentication failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

async def main():
    print("🧪 Testing Worker Authentication")
    print("=" * 40)
    
    success = await test_worker_auth()
    
    if success:
        print("\n✅ All authentication tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Authentication tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())