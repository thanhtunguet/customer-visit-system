#!/usr/bin/env python3
"""
Test script for worker monitoring and real-time status updates.
This script tests the worker monitoring service and WebSocket updates.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

import httpx
import websockets

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8080"
WS_BASE = "ws://localhost:8080"
TENANT_ID = "t-dev"


async def test_worker_monitoring():
    """Test worker monitoring and cleanup functionality"""
    
    print("=" * 60)
    print("Testing Worker Monitoring System")
    print("=" * 60)
    
    # Test 1: Check current worker status
    print("\n1. Checking current worker status...")
    async with httpx.AsyncClient() as client:
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
            
            # Get worker status
            workers_response = await client.get(
                f"{API_BASE}/v1/workers",
                headers=headers
            )
            
            if workers_response.status_code == 200:
                workers_data = workers_response.json()
                print(f"✅ Found {workers_data['total_count']} workers")
                print(f"   Online: {workers_data['online_count']}")
                print(f"   Offline: {workers_data['offline_count']}")
                print(f"   Errors: {workers_data['error_count']}")
                
                for worker in workers_data['workers']:
                    status_emoji = "🟢" if worker['is_healthy'] else "🔴"
                    print(f"   {status_emoji} {worker['worker_name']} ({worker['hostname']}) - {worker['status']}")
                    if worker['last_heartbeat']:
                        print(f"      Last heartbeat: {worker['last_heartbeat']}")
                    else:
                        print(f"      ⚠️  No heartbeat recorded")
            else:
                print(f"❌ Failed to get workers: {workers_response.status_code}")
                return
        
        except Exception as e:
            print(f"❌ Error checking worker status: {e}")
            return
    
    # Test 2: Force cleanup of stale workers
    print("\n2. Testing stale worker cleanup...")
    async with httpx.AsyncClient() as client:
        try:
            cleanup_response = await client.post(
                f"{API_BASE}/v1/workers/force-cleanup",
                headers=headers
            )
            
            if cleanup_response.status_code == 200:
                cleanup_data = cleanup_response.json()
                print(f"✅ Cleaned up {cleanup_data['updated_count']} stale workers")
            else:
                print(f"❌ Cleanup failed: {cleanup_response.status_code}")
                print(cleanup_response.text)
        
        except Exception as e:
            print(f"❌ Error testing cleanup: {e}")
    
    # Test 3: WebSocket real-time updates
    print("\n3. Testing WebSocket real-time updates...")
    try:
        ws_url = f"{WS_BASE}/v1/workers/ws/{TENANT_ID}"
        print(f"Connecting to WebSocket: {ws_url}")
        
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connected, listening for updates...")
            
            # Listen for messages for 10 seconds
            start_time = asyncio.get_event_loop().time()
            message_count = 0
            
            while asyncio.get_event_loop().time() - start_time < 10:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    message_count += 1
                    
                    if data.get("type") == "initial_data":
                        print(f"📋 Received initial data with {len(data.get('data', []))} workers")
                    elif data.get("type") == "worker_update":
                        worker_data = data.get("data", {})
                        print(f"🔄 Worker update: {worker_data.get('worker_name')} - {worker_data.get('status')}")
                    elif data.get("type") == "worker_list_refresh":
                        print("🔄 Worker list refresh requested")
                    elif data.get("type") == "ping":
                        print("🏓 Ping received")
                    else:
                        print(f"📨 Message: {data.get('type')}")
                
                except asyncio.TimeoutError:
                    # Send a ping to keep connection alive
                    await websocket.send("ping")
                
                except json.JSONDecodeError as e:
                    print(f"⚠️  Invalid JSON received: {e}")
                
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 WebSocket connection closed")
                    break
            
            print(f"✅ WebSocket test completed - received {message_count} messages")
    
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
    
    print("\n✅ Worker monitoring test completed!")


async def simulate_worker_activity():
    """Simulate worker activity for testing"""
    print("\n🤖 Simulating worker activity...")
    
    # This would require a real worker registration
    # For now, just mention what would happen
    print("💡 To see real-time updates:")
    print("   1. Start a worker with: cd apps/worker && python app/main.py")
    print("   2. Watch the WebSocket messages show status changes")
    print("   3. Stop the worker and see it marked offline after 2-5 minutes")


if __name__ == "__main__":
    print("Worker Monitoring Test")
    print("Make sure the API server is running on http://localhost:8080")
    print("Press Ctrl+C to stop the test\n")
    
    try:
        asyncio.run(test_worker_monitoring())
        asyncio.run(simulate_worker_activity())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")