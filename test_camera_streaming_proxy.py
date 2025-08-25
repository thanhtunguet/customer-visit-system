#!/usr/bin/env python3
"""
Test script to verify camera streaming proxy functionality
Tests the complete flow: Frontend -> API -> Worker -> Camera
"""
import asyncio
import httpx
import logging
import os
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8080")
TENANT_ID = os.getenv("TENANT_ID", "t-dev")
SITE_ID = int(os.getenv("SITE_ID", "1"))
CAMERA_ID = int(os.getenv("CAMERA_ID", "1"))
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "dev-api-key")

async def get_auth_token(client: httpx.AsyncClient) -> str:
    """Get authentication token"""
    logger.info("Getting authentication token...")
    
    response = await client.post(
        f"{API_URL}/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": WORKER_API_KEY,
            "tenant_id": TENANT_ID,
            "role": "system_admin",
        },
        timeout=10.0
    )
    response.raise_for_status()
    
    token = response.json()["access_token"]
    logger.info("✅ Authentication successful")
    return token

async def test_camera_operations(client: httpx.AsyncClient, token: str):
    """Test camera streaming operations"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Start camera stream
    logger.info(f"🎬 Starting camera stream for camera {CAMERA_ID}...")
    try:
        response = await client.post(
            f"{API_URL}/v1/sites/{SITE_ID}/cameras/{CAMERA_ID}/stream/start",
            headers=headers,
            timeout=30.0
        )
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Camera stream started: {result.get('message')}")
            if 'worker_id' in result:
                logger.info(f"   Assigned to worker: {result['worker_id']}")
        else:
            logger.error(f"❌ Failed to start stream: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error starting stream: {e}")
        return False
    
    # 2. Wait for stream to initialize
    await asyncio.sleep(3)
    
    # 3. Check stream status
    logger.info("🔍 Checking camera stream status...")
    try:
        response = await client.get(
            f"{API_URL}/v1/sites/{SITE_ID}/cameras/{CAMERA_ID}/stream/status",
            headers=headers,
            timeout=10.0
        )
        if response.status_code == 200:
            status = response.json()
            logger.info(f"✅ Stream status: {status}")
            if status.get('stream_active'):
                logger.info("   🟢 Stream is active!")
            else:
                logger.warning("   🟡 Stream not yet active")
        else:
            logger.error(f"❌ Failed to get status: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error getting status: {e}")
    
    # 4. Test stream feed URL (just check if endpoint responds)
    logger.info("📹 Testing stream feed endpoint...")
    try:
        stream_url = f"{API_URL}/v1/sites/{SITE_ID}/cameras/{CAMERA_ID}/stream/feed?access_token={token}"
        response = await client.get(stream_url, timeout=10.0)
        
        if response.status_code == 200:
            # Check if we're getting MJPEG stream
            content_type = response.headers.get('content-type', '')
            if 'multipart/x-mixed-replace' in content_type:
                logger.info("✅ Stream feed endpoint responding with MJPEG stream")
            else:
                logger.info(f"✅ Stream feed endpoint responding (content-type: {content_type})")
        elif response.status_code == 404:
            logger.warning("🟡 Stream feed not found (camera may not be streaming yet)")
        else:
            logger.error(f"❌ Stream feed error: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error testing stream feed: {e}")
    
    # 5. Stop camera stream
    logger.info("🛑 Stopping camera stream...")
    try:
        response = await client.post(
            f"{API_URL}/v1/sites/{SITE_ID}/cameras/{CAMERA_ID}/stream/stop",
            headers=headers,
            timeout=10.0
        )
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Camera stream stopped: {result.get('message')}")
        else:
            logger.error(f"❌ Failed to stop stream: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error stopping stream: {e}")
    
    return True

async def test_streaming_overview(client: httpx.AsyncClient, token: str):
    """Test streaming overview endpoints"""
    headers = {"Authorization": f"Bearer {token}"}
    
    logger.info("📊 Getting streaming overview...")
    try:
        response = await client.get(
            f"{API_URL}/v1/streaming/status-overview",
            headers=headers,
            timeout=10.0
        )
        if response.status_code == 200:
            overview = response.json()
            logger.info(f"✅ Streaming overview retrieved:")
            logger.info(f"   Total workers: {overview.get('total_workers', 0)}")
            logger.info(f"   Active streams: {overview.get('summary', {}).get('total_active_streams', 0)}")
            logger.info(f"   Healthy workers: {overview.get('summary', {}).get('healthy_workers', 0)}")
        else:
            logger.error(f"❌ Failed to get overview: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error getting overview: {e}")

async def main():
    """Main test function"""
    logger.info("🚀 Starting camera streaming proxy test...")
    logger.info(f"   API URL: {API_URL}")
    logger.info(f"   Tenant: {TENANT_ID}")
    logger.info(f"   Site ID: {SITE_ID}")
    logger.info(f"   Camera ID: {CAMERA_ID}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Get authentication token
            token = await get_auth_token(client)
            
            # Test streaming overview
            await test_streaming_overview(client, token)
            
            # Test camera operations
            success = await test_camera_operations(client, token)
            
            if success:
                logger.info("🎉 Camera streaming proxy test completed successfully!")
                return 0
            else:
                logger.error("❌ Camera streaming proxy test failed!")
                return 1
                
        except Exception as e:
            logger.error(f"❌ Test failed with error: {e}")
            return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))