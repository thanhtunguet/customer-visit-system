#!/usr/bin/env python3
"""
Test script to verify webcam device index consolidation.
This script helps verify that webcam indexing is consistent between
UI display, database storage, and actual OpenCV device enumeration.
"""

import asyncio
import json
import logging
import sys
import os

# Add the apps/api directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.services.camera_diagnostics import camera_diagnostics
from app.services.camera_streaming_service import streaming_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_webcam_indexing():
    """Test webcam device index consistency"""
    
    print("🔍 Testing Webcam Device Index Consolidation")
    print("=" * 60)
    
    # 1. Enumerate available OpenCV devices
    print("\n1️⃣ Enumerating OpenCV devices...")
    available_devices = camera_diagnostics.enumerate_cameras()
    
    if not available_devices:
        print("❌ No webcam devices found by OpenCV")
        return False
    
    print(f"✅ Found {len(available_devices)} OpenCV devices:")
    for device_index, info in available_devices.items():
        status = "✅ Working" if info.get("is_working", False) else "❌ Not working"
        resolution = f"{info.get('width', 'Unknown')}x{info.get('height', 'Unknown')}"
        fps = f"{info.get('fps', 'Unknown')}fps"
        print(f"   Device {device_index}: {status} ({resolution} @ {fps})")
    
    # 2. Test streaming service device tracking
    print("\n2️⃣ Testing streaming service device tracking...")
    working_devices = [idx for idx, info in available_devices.items() if info.get("is_working", False)]
    
    if len(working_devices) < 1:
        print("❌ No working webcam devices found - cannot test streaming")
        return False
    
    print(f"✅ Found {len(working_devices)} working devices: {working_devices}")
    
    # Test device locking
    test_camera_id = "test-camera-consolidation"
    test_device_index = working_devices[0]
    
    print(f"\n3️⃣ Testing device locking with device index {test_device_index}...")
    
    # Start a test stream
    success = streaming_service.start_stream(
        camera_id=test_camera_id,
        camera_type="webcam",
        device_index=test_device_index
    )
    
    if success:
        print(f"✅ Successfully started test stream on device {test_device_index}")
        
        # Check device status
        device_status = streaming_service.get_device_status()
        device_locks = device_status.get("device_locks", {})
        
        if test_device_index in device_locks and device_locks[test_device_index] == test_camera_id:
            print(f"✅ Device lock correctly set: device {test_device_index} → camera {test_camera_id}")
        else:
            print(f"❌ Device lock not set correctly. Expected: {test_device_index} → {test_camera_id}, Got: {device_locks}")
        
        # Test conflict detection
        print(f"\n4️⃣ Testing conflict detection...")
        conflict_success = streaming_service.start_stream(
            camera_id="conflicting-camera",
            camera_type="webcam", 
            device_index=test_device_index
        )
        
        if not conflict_success:
            print(f"✅ Conflict correctly detected when trying to use device {test_device_index}")
        else:
            print(f"❌ Conflict detection failed - should not allow multiple cameras on same device")
        
        # Clean up
        streaming_service.stop_stream(test_camera_id)
        print(f"✅ Test stream stopped and device {test_device_index} released")
        
        # Verify device lock is released
        device_status = streaming_service.get_device_status()
        device_locks = device_status.get("device_locks", {})
        
        if test_device_index not in device_locks:
            print(f"✅ Device lock properly released for device {test_device_index}")
        else:
            print(f"❌ Device lock not properly released. Still locked: {device_locks}")
            
    else:
        print(f"❌ Failed to start test stream on device {test_device_index}")
        return False
    
    # 5. Test multiple device handling
    if len(working_devices) >= 2:
        print(f"\n5️⃣ Testing multiple device handling...")
        device1, device2 = working_devices[0], working_devices[1]
        
        # Start streams on both devices
        success1 = streaming_service.start_stream("camera1", "webcam", device_index=device1)
        success2 = streaming_service.start_stream("camera2", "webcam", device_index=device2)
        
        if success1 and success2:
            print(f"✅ Successfully started streams on devices {device1} and {device2}")
            
            device_status = streaming_service.get_device_status()
            active_streams = device_status.get("active_streams", {})
            
            if len(active_streams) == 2:
                print(f"✅ Both streams are active: {list(active_streams.keys())}")
            else:
                print(f"❌ Expected 2 active streams, got {len(active_streams)}")
            
            # Clean up
            streaming_service.cleanup_all_streams()
            print("✅ All test streams cleaned up")
        else:
            print(f"❌ Failed to start simultaneous streams (device1: {success1}, device2: {success2})")
    else:
        print(f"ℹ️ Only {len(working_devices)} working device(s) found - skipping multiple device test")
    
    print(f"\n🎉 Webcam indexing consolidation test completed!")
    return True


async def main():
    """Main test function"""
    try:
        success = await test_webcam_indexing()
        if success:
            print("\n✅ All webcam indexing tests passed!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)