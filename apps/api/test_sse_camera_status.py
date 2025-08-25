#!/usr/bin/env python3
"""
Simple test script to verify SSE camera status updates work
"""

import asyncio
import aiohttp
import json
from datetime import datetime

async def test_sse_connection():
    """Test SSE connection for camera status updates"""
    
    # Test configuration
    API_BASE = "http://localhost:8000/v1"
    SITE_ID = 1
    
    # This would normally come from login
    TEST_TOKEN = "your-test-token-here"
    
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE}/sites/{SITE_ID}/cameras/status-stream"
            
            print(f"Connecting to SSE endpoint: {url}")
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    print(f"Failed to connect: {response.status}")
                    return
                
                print("Connected to SSE stream. Waiting for messages...")
                
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if line.startswith('data: '):
                        data_str = line[6:]  # Remove 'data: ' prefix
                        try:
                            data = json.loads(data_str)
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            print(f"[{timestamp}] Received: {data.get('type', 'unknown')} - {data}")
                            
                            if data.get('type') == 'camera_status_update':
                                camera_id = data.get('camera_id')
                                status = data.get('data', {}).get('stream_active', False)
                                print(f"  -> Camera {camera_id} is {'streaming' if status else 'stopped'}")
                                
                        except json.JSONDecodeError as e:
                            print(f"Failed to parse JSON: {e}")
                            print(f"Raw data: {data_str}")
                            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("SSE Camera Status Test")
    print("=" * 40)
    print("This script tests the Server-Sent Events endpoint for camera status updates.")
    print("Make sure the API server is running and update the TEST_TOKEN above.")
    print()
    
    asyncio.run(test_sse_connection())