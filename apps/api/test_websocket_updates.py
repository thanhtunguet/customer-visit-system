#!/usr/bin/env python3
"""
Test script for WebSocket real-time worker updates.
This script connects to the WebSocket and monitors for real-time worker status updates.
"""

import asyncio
import json
import logging
from datetime import datetime

import httpx
import websockets

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8080"
WS_BASE = "ws://localhost:8080"
TENANT_ID = "t-dev"


async def test_websocket_updates():
    """Test WebSocket real-time updates"""
    
    print("=" * 60)
    print("Testing WebSocket Real-Time Worker Updates")
    print("=" * 60)
    
    # Authenticate first
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
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
                return
            
            token = auth_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Connect to WebSocket
            ws_url = f"{WS_BASE}/v1/workers/ws/{TENANT_ID}"
            print(f"🔌 Connecting to WebSocket: {ws_url}")
            
            async with websockets.connect(ws_url) as websocket:
                print("✅ WebSocket connected!")
                print("📡 Listening for worker updates...")
                print("💡 Now perform actions in another terminal:")
                print("   - Start a worker: cd apps/worker && python app/main.py")
                print("   - Stop a worker: Ctrl+C or delete from frontend")
                print("   - Or use API calls to trigger updates")
                print()
                
                # Listen for messages
                message_count = 0
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        data = json.loads(message)
                        message_count += 1
                        
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        
                        if data.get("type") == "initial_data":
                            workers = data.get('data', [])
                            print(f"[{timestamp}] 📋 Initial data received:")
                            for worker in workers:
                                status_emoji = "🟢" if worker.get('is_healthy') else "🔴"
                                print(f"   {status_emoji} {worker.get('worker_name')} - {worker.get('status')}")
                            print()
                        
                        elif data.get("type") == "worker_update":
                            worker_data = data.get("data", {})
                            status_emoji = "🟢" if worker_data.get('is_healthy') else "🔴"
                            print(f"[{timestamp}] 🔄 Worker Update:")
                            print(f"   {status_emoji} {worker_data.get('worker_name')} ({worker_data.get('hostname')})")
                            print(f"   Status: {worker_data.get('status')}")
                            print(f"   Camera: {worker_data.get('camera_id', 'None')}")
                            print(f"   Last Heartbeat: {worker_data.get('last_heartbeat', 'Never')}")
                            print(f"   Healthy: {worker_data.get('is_healthy')}")
                            print()
                        
                        elif data.get("type") == "worker_list_refresh":
                            print(f"[{timestamp}] 🔄 Worker list refresh requested")
                            print("   Frontend should refetch complete worker list")
                            print()
                        
                        elif data.get("type") == "ping":
                            print(f"[{timestamp}] 🏓 Ping")
                            await websocket.send("pong")
                        
                        else:
                            print(f"[{timestamp}] 📨 Unknown message type: {data.get('type')}")
                            print(f"   Data: {json.dumps(data, indent=2)}")
                            print()
                    
                    except asyncio.TimeoutError:
                        # Send periodic ping to keep connection alive
                        await websocket.send("ping")
                        
                        # Show periodic status
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if int(elapsed) % 30 == 0 and elapsed > 0:  # Every 30 seconds
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏰ Still listening... ({message_count} messages received)")
                    
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Invalid JSON received: {e}")
                    
                    except websockets.exceptions.ConnectionClosed:
                        print("🔌 WebSocket connection closed")
                        break
            
        except Exception as e:
            print(f"❌ Error: {e}")


async def trigger_test_updates():
    """Trigger test updates to verify WebSocket functionality"""
    print("\n" + "=" * 60)
    print("Triggering Test Updates")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Authenticate
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
                print("❌ Authentication failed")
                return
            
            token = auth_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get current workers
            workers_response = await client.get(f"{API_BASE}/v1/workers", headers=headers)
            if workers_response.status_code != 200:
                print("❌ Failed to get workers")
                return
            
            workers_data = workers_response.json()
            active_workers = [w for w in workers_data['workers'] if w['is_healthy']]
            
            if active_workers:
                # Test force cleanup to trigger updates
                print("🧹 Triggering force cleanup to test WebSocket updates...")
                
                cleanup_response = await client.post(
                    f"{API_BASE}/v1/workers/force-cleanup",
                    headers=headers
                )
                
                if cleanup_response.status_code == 200:
                    result = cleanup_response.json()
                    print(f"✅ Force cleanup triggered: {result['message']}")
                else:
                    print(f"❌ Force cleanup failed: {cleanup_response.status_code}")
            else:
                print("💡 No active workers found to test with")
                print("   Start a worker to see real-time updates")
        
        except Exception as e:
            print(f"❌ Error triggering updates: {e}")


if __name__ == "__main__":
    print("WebSocket Real-Time Updates Test")
    print("This script will monitor WebSocket connections for worker status updates")
    print("Make sure the API server is running on http://localhost:8080")
    print("Press Ctrl+C to stop monitoring\n")
    
    try:
        # Run WebSocket monitoring
        asyncio.run(test_websocket_updates())
    except KeyboardInterrupt:
        print("\n👋 WebSocket monitoring stopped by user")
        
        # Offer to run test updates
        try:
            response = input("\nRun test updates? (y/n): ").lower().strip()
            if response == 'y':
                asyncio.run(trigger_test_updates())
        except (KeyboardInterrupt, EOFError):
            pass
        
        print("Test completed!")
    except Exception as e:
        print(f"Test failed: {e}")