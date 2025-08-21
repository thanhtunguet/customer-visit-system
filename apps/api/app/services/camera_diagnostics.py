import cv2
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CameraDiagnostics:
    """Diagnostic tools for camera detection and enumeration"""
    
    @staticmethod
    def enumerate_cameras(max_devices: int = 10) -> Dict[int, Dict]:
        """Enumerate all available cameras and test them"""
        available_cameras = {}
        
        for device_index in range(max_devices):
            try:
                # Try to open the camera
                cap = cv2.VideoCapture(device_index)
                
                if cap.isOpened():
                    # Try to read a frame to verify it's working
                    ret, frame = cap.read()
                    
                    if ret and frame is not None:
                        # Get camera properties
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        backend = cap.getBackendName()
                        
                        # Try to get unique identifiers
                        # Some systems provide device names or IDs
                        device_info = {
                            "device_index": device_index,
                            "width": width,
                            "height": height,
                            "fps": fps,
                            "backend": backend,
                            "is_working": True,
                            "frame_captured": True
                        }
                        
                        # Try to get device-specific properties
                        try:
                            # Attempt to get camera name/model (platform dependent)
                            brightness = cap.get(cv2.CAP_PROP_BRIGHTNESS)
                            contrast = cap.get(cv2.CAP_PROP_CONTRAST)
                            saturation = cap.get(cv2.CAP_PROP_SATURATION)
                            
                            device_info.update({
                                "brightness": brightness,
                                "contrast": contrast, 
                                "saturation": saturation
                            })
                        except Exception as e:
                            logger.debug(f"Could not get additional properties for device {device_index}: {e}")
                        
                        available_cameras[device_index] = device_info
                        logger.info(f"Found working camera at index {device_index}: {width}x{height} @ {fps}fps")
                    else:
                        logger.warning(f"Camera at index {device_index} opened but cannot capture frames")
                        available_cameras[device_index] = {
                            "device_index": device_index,
                            "is_working": False,
                            "frame_captured": False,
                            "error": "Cannot capture frames"
                        }
                else:
                    logger.debug(f"No camera found at index {device_index}")
                
                cap.release()
                
            except Exception as e:
                logger.debug(f"Error testing camera {device_index}: {e}")
        
        return available_cameras
    
    @staticmethod
    def test_simultaneous_access(device_indices: List[int]) -> Dict[str, any]:
        """Test if multiple cameras can be accessed simultaneously"""
        results = {
            "can_access_simultaneously": False,
            "successful_devices": [],
            "failed_devices": [],
            "details": {}
        }
        
        captures = {}
        
        try:
            # Try to open all devices simultaneously
            for device_index in device_indices:
                try:
                    cap = cv2.VideoCapture(device_index)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            captures[device_index] = cap
                            results["successful_devices"].append(device_index)
                            results["details"][device_index] = {
                                "opened": True,
                                "frame_captured": True,
                                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            }
                        else:
                            cap.release()
                            results["failed_devices"].append(device_index)
                            results["details"][device_index] = {
                                "opened": True,
                                "frame_captured": False,
                                "error": "Cannot capture frame"
                            }
                    else:
                        results["failed_devices"].append(device_index)
                        results["details"][device_index] = {
                            "opened": False,
                            "error": "Cannot open device"
                        }
                except Exception as e:
                    results["failed_devices"].append(device_index)
                    results["details"][device_index] = {
                        "opened": False,
                        "error": str(e)
                    }
            
            # Test if we can capture from all simultaneously
            if len(captures) > 1:
                # Try to capture frames from all devices at the same time
                frames_captured = {}
                for device_index, cap in captures.items():
                    ret, frame = cap.read()
                    frames_captured[device_index] = ret and frame is not None
                
                # Check if frames are actually different
                if len(frames_captured) >= 2:
                    frame_data = {}
                    for device_index, cap in captures.items():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            # Calculate a simple hash of the frame to detect if they're the same
                            frame_hash = hash(frame.tobytes())
                            frame_data[device_index] = frame_hash
                    
                    # Check if all frames are different
                    unique_hashes = set(frame_data.values())
                    results["unique_feeds"] = len(unique_hashes)
                    results["total_devices"] = len(frame_data)
                    results["feeds_are_different"] = len(unique_hashes) > 1
                    results["frame_hashes"] = frame_data
                
                results["can_access_simultaneously"] = len(captures) > 1
            
        finally:
            # Clean up all captures
            for cap in captures.values():
                try:
                    cap.release()
                except:
                    pass
        
        return results
    
    @staticmethod
    def generate_full_report() -> Dict:
        """Generate a comprehensive camera diagnostic report"""
        logger.info("Starting camera diagnostic scan...")
        
        report = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "available_cameras": {},
            "simultaneous_access_test": {},
            "recommendations": []
        }
        
        # Enumerate all cameras
        available_cameras = CameraDiagnostics.enumerate_cameras()
        report["available_cameras"] = available_cameras
        
        working_indices = [idx for idx, info in available_cameras.items() if info.get("is_working", False)]
        
        if len(working_indices) == 0:
            report["recommendations"].append("No working cameras found. Check camera connections.")
        elif len(working_indices) == 1:
            report["recommendations"].append(f"Only one working camera found at index {working_indices[0]}.")
        else:
            # Test simultaneous access
            simultaneous_test = CameraDiagnostics.test_simultaneous_access(working_indices)
            report["simultaneous_access_test"] = simultaneous_test
            
            if not simultaneous_test.get("can_access_simultaneously", False):
                report["recommendations"].append("Cannot access multiple cameras simultaneously.")
            elif not simultaneous_test.get("feeds_are_different", False):
                report["recommendations"].append("Multiple camera indices point to the same physical camera.")
                report["recommendations"].append("This is a common issue on some systems where device enumeration is incorrect.")
            else:
                report["recommendations"].append("Multiple cameras are working correctly with different feeds.")
        
        return report


# Global instance
camera_diagnostics = CameraDiagnostics()