#!/usr/bin/env python3
"""
Test script for camera proxy service
"""
import asyncio
import os
import sys
import logging

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.camera_proxy_service import camera_proxy_service
from app.services.camera_delegation_service import camera_delegation_service
from app.services.worker_registry import worker_registry

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_proxy_service():
    """Test camera proxy service functionality"""
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize proxy service
        await camera_proxy_service.initialize()
        logger.info("Proxy service initialized")
        
        # Test debug info
        debug_info = await camera_proxy_service.get_streaming_debug_info()
        logger.info(f"Debug info: {debug_info}")
        
        # Test camera status (should show no cameras assigned)
        status = await camera_proxy_service.get_camera_stream_status(1)
        logger.info(f"Camera 1 status: {status}")
        
        # Test delegation service status
        assignments = camera_delegation_service.list_assignments()
        logger.info(f"Current assignments: {assignments}")
        
        # Test worker registry status
        workers = worker_registry.list_workers()
        logger.info(f"Registered workers: {len(workers)}")
        for worker in workers:
            logger.info(f"  Worker {worker.worker_id}: {worker.status.value} (camera: {worker.camera_id})")
        
        logger.info("Proxy service tests completed successfully")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
    finally:
        await camera_proxy_service.shutdown()

if __name__ == "__main__":
    print("Testing camera proxy service...")
    
    try:
        asyncio.run(test_proxy_service())
        print("✓ All tests passed")
    except Exception as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)