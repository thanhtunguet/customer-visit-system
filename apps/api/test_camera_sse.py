#!/usr/bin/env python3
"""
Simple test script to verify camera SSE connection works
"""

import asyncio
import aiohttp
import json

async def test_camera_sse():
    # Replace with actual values
    BASE_URL = "http://localhost:8000"
    SITE_ID = 1
    ACCESS_TOKEN = "your_token_here"  # Get from browser
    
    url = f"{BASE_URL}/v1/sites/{SITE_ID}/cameras/status-stream"
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                print(f"SSE Response status: {response.status}")
                print(f"SSE Response headers: {dict(response.headers)}")
                
                if response.status == 200:
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            data_json = line_str[6:]  # Remove 'data: ' prefix
                            try:
                                data = json.loads(data_json)
                                print(f"SSE Message: {data}")
                                
                                # Stop after first few messages
                                if data.get('type') == 'keepalive':
                                    break
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e}")
                else:
                    print(f"SSE connection failed: {response.status}")
                    text = await response.text()
                    print(f"Response body: {text}")
                    
    except Exception as e:
        print(f"SSE test error: {e}")

if __name__ == "__main__":
    asyncio.run(test_camera_sse())