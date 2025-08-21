#!/usr/bin/env python3
"""
Emergency fix script for camera streaming conflicts.
This script directly accesses the streaming service to clear conflicts.
"""

import sys
import os

# Add the apps/api directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

def fix_camera_streaming():
    """Fix camera streaming conflicts by clearing all state"""
    try:
        from app.services.camera_streaming_service import streaming_service
        
        print("🔧 Emergency Camera Streaming Fix")
        print("=" * 50)
        
        # Show current state
        status = streaming_service.get_device_status()
        print(f"Current device locks: {status.get('device_locks', {})}")
        print(f"Current active streams: {len(status.get('active_streams', {}))}")
        
        # Force cleanup everything
        print("\n🧹 Forcing cleanup of all streams and device locks...")
        streaming_service.cleanup_all_streams()
        
        # Double-check by manually clearing locks
        with streaming_service.lock:
            streaming_service.device_locks.clear()
            streaming_service.streams.clear()
        
        print("✅ Manually cleared all internal state")
        
        # Verify cleanup
        status_after = streaming_service.get_device_status()
        print(f"\nAfter cleanup:")
        print(f"  Device locks: {status_after.get('device_locks', {})}")
        print(f"  Active streams: {len(status_after.get('active_streams', {}))}")
        
        if not status_after.get('device_locks') and not status_after.get('active_streams'):
            print("\n🎉 Camera streaming conflicts should now be resolved!")
            print("Try starting your camera streams again.")
        else:
            print("\n⚠️  Some state might still be present. API server restart recommended.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing camera streaming: {e}")
        return False

if __name__ == "__main__":
    success = fix_camera_streaming()
    sys.exit(0 if success else 1)