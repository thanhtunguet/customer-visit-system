#!/usr/bin/env python3
"""
Test script for worker shutdown functionality.
This script tests the graceful shutdown signaling between backend and workers.
"""

import asyncio
import logging
from datetime import datetime

import httpx

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8080"
TENANT_ID = "t-dev"


async def test_worker_shutdown():
    """Test worker shutdown functionality"""
    
    print("=" * 60)
    print("Testing Worker Shutdown System")
    print("=" * 60)
    
    # Authenticate
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First authenticate (using dev credentials)
            auth_response = await client.post(
                f"{API_BASE}/v1/auth/token",
                json={
                    "grant_type": "password",
                    "username": "admin",
                    "password": "admin123",
                    "tenant_id": TENANT_ID
                }
            )
            
            if auth_response.status_code != 200:
                print(f"❌ Authentication failed: {auth_response.status_code}")
                print("Make sure API server is running and admin user exists")
                return
            
            token = auth_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Test 1: List current workers
            print("\n1. Checking current workers...")
            workers_response = await client.get(
                f"{API_BASE}/v1/workers",
                headers=headers
            )
            
            if workers_response.status_code != 200:
                print(f"❌ Failed to get workers: {workers_response.status_code}")
                return
            
            workers_data = workers_response.json()
            active_workers = [w for w in workers_data['workers'] if w['is_healthy']]
            
            print(f"✅ Found {len(active_workers)} active workers")
            if not active_workers:
                print("💡 Start a worker first with: cd apps/worker && python app/main.py")
                return
            
            for worker in active_workers:
                print(f"   🟢 {worker['worker_name']} ({worker['hostname']}) - {worker['status']}")
            
            # Test 2: Test shutdown signal for first active worker
            test_worker = active_workers[0]
            worker_id = test_worker['worker_id']
            worker_name = test_worker['worker_name']
            
            print(f"\n2. Testing graceful shutdown for worker: {worker_name}")
            
            shutdown_response = await client.post(
                f"{API_BASE}/v1/workers/{worker_id}/shutdown",
                headers=headers,
                json={
                    "signal": "graceful",
                    "timeout": 30
                }
            )
            
            if shutdown_response.status_code == 200:
                shutdown_data = shutdown_response.json()
                print(f"✅ Shutdown requested successfully")
                print(f"   Message: {shutdown_data['message']}")
                print(f"   Timeout: {shutdown_data['timeout']}s")
            else:
                print(f"❌ Shutdown request failed: {shutdown_response.status_code}")
                print(shutdown_response.text)
                return
            
            # Test 3: Check shutdown status
            print(f"\n3. Monitoring shutdown progress...")
            
            for i in range(6):  # Check for 30 seconds
                await asyncio.sleep(5)
                
                # Check shutdown status
                status_response = await client.get(
                    f"{API_BASE}/v1/workers/shutdown-status",
                    headers=headers
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    pending_shutdowns = status_data['pending_shutdowns']
                    
                    worker_shutdown = None
                    for shutdown in pending_shutdowns:
                        if shutdown['worker_id'] == worker_id:
                            worker_shutdown = shutdown
                            break
                    
                    if worker_shutdown:
                        status = worker_shutdown['status']
                        print(f"   📊 Shutdown status: {status}")
                        
                        if status == "completed":
                            print(f"✅ Worker shutdown completed successfully!")
                            break
                        elif status == "timeout":
                            print(f"⚠️  Worker shutdown timed out")
                            break
                    else:
                        print(f"   ✅ Shutdown completed (no longer pending)")
                        break
                else:
                    print(f"   ⚠️  Could not check shutdown status: {status_response.status_code}")
            
            # Test 4: Check worker status after shutdown
            print(f"\n4. Checking worker status after shutdown...")
            
            workers_response = await client.get(
                f"{API_BASE}/v1/workers",
                headers=headers
            )
            
            if workers_response.status_code == 200:
                workers_data = workers_response.json()
                shutdown_worker = None
                
                for worker in workers_data['workers']:
                    if worker['worker_id'] == worker_id:
                        shutdown_worker = worker
                        break
                
                if shutdown_worker:
                    status = shutdown_worker['status']
                    is_healthy = shutdown_worker['is_healthy']
                    
                    if status == "offline" and not is_healthy:
                        print(f"✅ Worker correctly marked as offline")
                    else:
                        print(f"⚠️  Worker status: {status}, healthy: {is_healthy}")
                else:
                    print(f"✅ Worker has been removed from the list")
            
            # Test 5: Test delete with force flag
            print(f"\n5. Testing force deletion...")
            
            # Find another worker if available
            remaining_workers = [w for w in workers_data['workers'] if w['worker_id'] != worker_id and w['is_healthy']]
            
            if remaining_workers:
                force_test_worker = remaining_workers[0]
                force_worker_id = force_test_worker['worker_id']
                force_worker_name = force_test_worker['worker_name']
                
                print(f"   Testing force delete on: {force_worker_name}")
                
                delete_response = await client.delete(
                    f"{API_BASE}/v1/workers/{force_worker_id}?force=true",
                    headers=headers
                )
                
                if delete_response.status_code == 200:
                    delete_data = delete_response.json()
                    print(f"✅ Force deletion successful: {delete_data['message']}")
                else:
                    print(f"❌ Force deletion failed: {delete_response.status_code}")
            else:
                print("   No additional workers available for force delete test")
            
        except Exception as e:
            print(f"❌ Test error: {e}")
    
    print("\n✅ Worker shutdown test completed!")


async def simulate_shutdown_scenarios():
    """Show different shutdown scenarios"""
    print("\n" + "=" * 60)
    print("Shutdown Scenarios Overview")
    print("=" * 60)
    
    scenarios = [
        {
            "name": "Graceful Shutdown",
            "description": "Worker finishes current work and shuts down cleanly",
            "api_call": "POST /workers/{id}/shutdown",
            "payload": '{"signal": "graceful", "timeout": 30}'
        },
        {
            "name": "Immediate Shutdown", 
            "description": "Worker stops immediately without finishing work",
            "api_call": "POST /workers/{id}/shutdown",
            "payload": '{"signal": "immediate", "timeout": 10}'
        },
        {
            "name": "Restart Signal",
            "description": "Worker shuts down and should restart (if managed by supervisor)",
            "api_call": "POST /workers/{id}/shutdown", 
            "payload": '{"signal": "restart", "timeout": 30}'
        },
        {
            "name": "Delete Worker",
            "description": "Delete healthy worker (requests graceful shutdown first)",
            "api_call": "DELETE /workers/{id}",
            "payload": "No body - automatic graceful shutdown"
        },
        {
            "name": "Force Delete",
            "description": "Force delete worker without graceful shutdown",
            "api_call": "DELETE /workers/{id}?force=true",
            "payload": "No body - immediate deletion"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print(f"   Description: {scenario['description']}")
        print(f"   API Call: {scenario['api_call']}")
        print(f"   Payload: {scenario['payload']}")
    
    print(f"\n💡 Frontend Integration:")
    print(f"   - Delete button should call DELETE /workers/{{id}} (graceful by default)")
    print(f"   - Emergency stop button should call DELETE /workers/{{id}}?force=true") 
    print(f"   - Shutdown options can use POST /workers/{{id}}/shutdown with different signals")


if __name__ == "__main__":
    print("Worker Shutdown Test")
    print("Make sure the API server is running on http://localhost:8080")
    print("And at least one worker is running for testing")
    print("Press Ctrl+C to stop the test\n")
    
    try:
        asyncio.run(test_worker_shutdown())
        asyncio.run(simulate_shutdown_scenarios())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")