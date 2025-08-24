#!/usr/bin/env python3
"""
Quick test script to diagnose the 404 endpoint issues
"""
import asyncio
import httpx
import json

API_BASE = "http://localhost:8080"
WORKER_BASE = "http://localhost:8090"

async def test_endpoints():
    print("Testing API and Worker endpoints...")
    
    async with httpx.AsyncClient() as client:
        # Test 1: Check if API is running
        try:
            response = await client.get(f"{API_BASE}/health")
            if response.status_code == 200:
                print("✅ API is running")
            else:
                print(f"⚠️ API health check returned {response.status_code}")
        except Exception as e:
            print(f"❌ API is not accessible: {e}")
            return
        
        # Test 2: Check if worker is running  
        try:
            response = await client.get(f"{WORKER_BASE}/health")
            if response.status_code == 200:
                print("✅ Worker is running")
                worker_health = response.json()
                print(f"   Worker ID: {worker_health.get('worker_id')}")
                print(f"   Active cameras: {worker_health.get('active_cameras')}")
            else:
                print(f"⚠️ Worker health check returned {response.status_code}")
        except Exception as e:
            print(f"❌ Worker is not accessible: {e}")
        
        # Test 3: Test API worker registry endpoints
        print("\n🔍 Testing API worker registry endpoints...")
        
        # List workers
        try:
            response = await client.get(f"{API_BASE}/v1/registry/workers")
            if response.status_code == 200:
                workers = response.json()
                print(f"✅ Worker registry accessible - found {workers.get('total_count', 0)} workers")
                if workers.get('workers'):
                    for worker in workers['workers']:
                        print(f"   - {worker['worker_name']} ({worker['worker_id'][:8]}...) - {worker['status']}")
            else:
                print(f"❌ Worker registry returned {response.status_code}")
        except Exception as e:
            print(f"❌ Worker registry error: {e}")
        
        # Test 4: Test worker shutdown endpoints
        print("\n🔍 Testing API worker management endpoints...")
        test_worker_id = "test-worker-id"
        
        endpoints_to_test = [
            f"/v1/workers/{test_worker_id}/shutdown-signal",
            f"/v1/workers/{test_worker_id}/complete-shutdown", 
            f"/v1/worker-management/commands/{test_worker_id}/pending?limit=5"
        ]
        
        for endpoint in endpoints_to_test:
            try:
                response = await client.post(f"{API_BASE}{endpoint}")
                if response.status_code in [401, 403]:
                    print(f"✅ {endpoint} - endpoint exists (auth required)")
                elif response.status_code == 404:
                    print(f"❌ {endpoint} - endpoint not found")
                else:
                    print(f"⚠️ {endpoint} - returned {response.status_code}")
            except Exception as e:
                print(f"❌ {endpoint} - error: {e}")
        
        # Test 5: Test worker streaming endpoints
        print("\n🔍 Testing worker streaming endpoints...")
        test_camera_id = "1"
        
        worker_endpoints_to_test = [
            f"/cameras/{test_camera_id}/stream/status",
            f"/cameras/{test_camera_id}/stream/feed",
            "/streaming/debug"
        ]
        
        for endpoint in worker_endpoints_to_test:
            try:
                response = await client.get(f"{WORKER_BASE}{endpoint}")
                if response.status_code in [401, 403, 422]:
                    print(f"✅ {endpoint} - endpoint exists")
                elif response.status_code == 404:
                    print(f"❌ {endpoint} - endpoint not found")
                else:
                    print(f"⚠️ {endpoint} - returned {response.status_code}")
            except Exception as e:
                print(f"❌ {endpoint} - error: {e}")

if __name__ == "__main__":
    asyncio.run(test_endpoints())