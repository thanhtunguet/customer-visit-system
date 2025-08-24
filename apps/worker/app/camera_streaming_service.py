"""
Camera streaming service for worker - moved from API
Handles OpenCV camera capture, device management, and MJPEG streaming
"""
import asyncio
import cv2
import logging
import threading
import time
from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import Dict, Optional, AsyncGenerator, Any
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StreamInfo:
    camera_id: str
    camera_type: str
    rtsp_url: Optional[str]
    device_index: Optional[int]
    is_active: bool = False
    cap: Optional[cv2.VideoCapture] = field(default=None, init=False)
    frame_queue: Queue = field(default_factory=lambda: Queue(maxsize=5), init=False)
    thread: Optional[threading.Thread] = field(default=None, init=False)
    last_frame_time: float = field(default_factory=time.time, init=False)
    error_count: int = field(default=0, init=False)
    max_retries: int = field(default=5, init=False)


class WorkerCameraStreamingService:
    """Camera streaming service for workers with face recognition integration"""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.streams: Dict[str, StreamInfo] = {}
        self.lock = threading.Lock()
        self.device_locks: Dict[int, str] = {}  # Track which camera_id is using each device index
        
        # Face processing callback
        self.face_processor_callback: Optional[callable] = None
        
    def set_face_processor(self, callback: callable):
        """Set callback for face processing on each frame"""
        self.face_processor_callback = callback
        
    def _capture_frames(self, stream_info: StreamInfo) -> None:
        """Capture frames in a separate thread with face processing"""
        thread_name = f"CaptureThread-{stream_info.camera_id}-{self.worker_id}"
        logger.info(f"Starting {thread_name} for device index {stream_info.device_index}")
        
        try:
            frame_count = 0
            while stream_info.is_active and stream_info.cap:
                ret, frame = stream_info.cap.read()
                
                if not ret:
                    logger.warning(f"Failed to read frame from camera {stream_info.camera_id} (device {stream_info.device_index})")
                    stream_info.error_count += 1
                    
                    if stream_info.error_count >= stream_info.max_retries:
                        logger.error(f"Max retries exceeded for camera {stream_info.camera_id}")
                        break
                        
                    time.sleep(1)  # Wait before retry
                    continue
                
                stream_info.error_count = 0  # Reset error count on successful read
                stream_info.last_frame_time = time.time()
                frame_count += 1
                
                # Add debug info every 100 frames
                if frame_count % 100 == 0:
                    logger.debug(f"Camera {stream_info.camera_id} (device {stream_info.device_index}): captured {frame_count} frames")
                
                # Add worker ID and camera ID as metadata to frame (for debugging)
                if frame is not None:
                    # Add small text overlay to identify the worker and camera
                    cv2.putText(frame, f"Worker: {self.worker_id[:8]}", 
                              (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(frame, f"Cam: {stream_info.camera_id} (Dev: {stream_info.device_index})", 
                              (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Process frame for face recognition if callback is set
                if self.face_processor_callback and frame is not None:
                    try:
                        # Process face detection in background (don't block streaming)
                        asyncio.create_task(self.face_processor_callback(frame.copy()))
                    except Exception as face_error:
                        logger.debug(f"Face processing error: {face_error}")
                
                # Encode frame as JPEG for streaming
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    # Put frame in queue, drop oldest if queue is full
                    if stream_info.frame_queue.full():
                        try:
                            stream_info.frame_queue.get_nowait()
                        except Empty:
                            pass
                    
                    try:
                        stream_info.frame_queue.put(buffer.tobytes(), block=False)
                    except:
                        pass  # Queue full, skip frame
                
                # Control frame rate (~30 FPS max)
                time.sleep(1/30)
                
        except Exception as e:
            logger.error(f"Error in capture thread for camera {stream_info.camera_id}: {e}")
        finally:
            stream_info.is_active = False
            logger.info(f"Stopped {thread_name}")

    def start_stream(self, camera_id: str, camera_type: str, rtsp_url: Optional[str] = None, device_index: Optional[int] = None) -> bool:
        """Start streaming for a camera"""
        # Ensure camera_id is string for consistent internal handling
        camera_id = str(camera_id)
        logger.info(f"Worker {self.worker_id} start_stream called: camera_id={camera_id}, device_index={device_index}, camera_type={camera_type}")
        
        with self.lock:
            if camera_id in self.streams and self.streams[camera_id].is_active:
                logger.info(f"Stream for camera {camera_id} is already active")
                return True
            elif camera_id in self.streams:
                logger.info(f"Camera {camera_id} exists in streams but is_active={self.streams[camera_id].is_active}")
            
            # For webcam cameras, clean up any existing locks for this camera first
            if camera_type.lower() == 'webcam' and device_index is not None:
                # Remove any existing locks for this camera (handles restart case)
                locks_to_remove = []
                logger.info(f"Checking for existing locks for camera {camera_id}. Current locks: {self.device_locks}")
                for dev_idx, locked_camera in self.device_locks.items():
                    if str(locked_camera) == camera_id:  # Ensure string comparison
                        locks_to_remove.append(dev_idx)
                        logger.info(f"Found existing lock for camera {camera_id} on device {dev_idx}")
                
                for dev_idx in locks_to_remove:
                    del self.device_locks[dev_idx]
                    logger.info(f"Removed existing device lock for camera {camera_id} on device {dev_idx}")
                
                # Stop any existing stream for this camera
                if camera_id in self.streams:
                    logger.info(f"Stopping existing stream for camera {camera_id} before starting new one")
                    self.stop_stream(camera_id)
                
                # Now check for conflicts with other cameras
                if device_index in self.device_locks:
                    existing_camera = self.device_locks[device_index]
                    logger.error(f"Device index {device_index} is already in use by camera {existing_camera}. Cannot start camera {camera_id}")
                    return False
                
                logger.info(f"Device conflict check passed for camera {camera_id} on device {device_index}. Current locks: {self.device_locks}")
            
            # Create stream info
            stream_info = StreamInfo(
                camera_id=camera_id,
                camera_type=camera_type,
                rtsp_url=rtsp_url,
                device_index=device_index
            )
            
            # Initialize video capture
            try:
                if camera_type.lower() == 'rtsp' and rtsp_url:
                    stream_info.cap = cv2.VideoCapture(rtsp_url)
                    logger.info(f"Attempting to open RTSP camera {camera_id} with URL: {rtsp_url}")
                elif camera_type.lower() == 'webcam' and device_index is not None:
                    logger.info(f"Attempting to open webcam camera {camera_id} with device index: {device_index}")
                    stream_info.cap = cv2.VideoCapture(device_index)
                else:
                    logger.error(f"Invalid camera configuration for camera {camera_id}: type={camera_type}, rtsp_url={rtsp_url}, device_index={device_index}")
                    return False
                
                if not stream_info.cap or not stream_info.cap.isOpened():
                    logger.error(f"Failed to open camera {camera_id} - OpenCV could not initialize the camera")
                    if stream_info.cap:
                        stream_info.cap.release()
                    return False
                
                # Test if we can read a frame
                ret, test_frame = stream_info.cap.read()
                if not ret:
                    logger.error(f"Failed to read test frame from camera {camera_id}")
                    stream_info.cap.release()
                    return False
                
                # Set some properties for better performance and uniqueness
                stream_info.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                stream_info.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                stream_info.cap.set(cv2.CAP_PROP_FPS, 30)
                stream_info.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # For webcam, try to set additional properties to ensure unique streams
                if camera_type.lower() == 'webcam':
                    # Flush any existing buffers
                    for _ in range(5):
                        stream_info.cap.read()
                    
                    logger.info(f"Camera {camera_id}: Final resolution {int(stream_info.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(stream_info.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
                
                stream_info.is_active = True
                
                # Lock the device index if it's a webcam
                if camera_type.lower() == 'webcam' and device_index is not None:
                    self.device_locks[device_index] = camera_id
                    logger.info(f"Locked device index {device_index} for camera {camera_id}. Current locks: {self.device_locks}")
                
                # Start capture thread
                stream_info.thread = threading.Thread(
                    target=self._capture_frames,
                    args=(stream_info,),
                    daemon=True
                )
                stream_info.thread.start()
                
                self.streams[camera_id] = stream_info
                logger.info(f"Worker {self.worker_id} successfully started stream for camera {camera_id} (type: {camera_type}, device_index: {device_index})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start stream for camera {camera_id}: {e}")
                if stream_info.cap:
                    stream_info.cap.release()
                return False

    def stop_stream(self, camera_id: str) -> bool:
        """Stop streaming for a camera"""
        # Ensure camera_id is string for consistent internal handling
        camera_id = str(camera_id)
        with self.lock:
            if camera_id not in self.streams:
                return True
            
            stream_info = self.streams[camera_id]
            stream_info.is_active = False
            
            # Release device lock if it's a webcam
            if (stream_info.camera_type.lower() == 'webcam' and 
                stream_info.device_index is not None and 
                stream_info.device_index in self.device_locks):
                del self.device_locks[stream_info.device_index]
                logger.info(f"Released device lock for index {stream_info.device_index} from camera {camera_id}. Remaining locks: {self.device_locks}")
            
            # Wait for thread to finish with shorter timeout to prevent hanging
            if stream_info.thread and stream_info.thread.is_alive():
                stream_info.thread.join(timeout=1.0)  # Reduced from 5 to 1 second
                if stream_info.thread.is_alive():
                    logger.warning(f"Thread for camera {camera_id} did not stop gracefully within timeout")
            
            # Release resources
            try:
                if stream_info.cap:
                    stream_info.cap.release()
            except Exception as e:
                logger.warning(f"Error releasing camera {camera_id}: {e}")
            
            # Clear frame queue without blocking
            try:
                while not stream_info.frame_queue.empty():
                    stream_info.frame_queue.get_nowait()
            except Exception:
                pass  # Queue might be closed or empty
            
            del self.streams[camera_id]
            logger.info(f"Worker {self.worker_id} stopped stream for camera {camera_id}")
            return True

    def get_frame(self, camera_id: str) -> Optional[bytes]:
        """Get the latest frame for a camera"""
        camera_id = str(camera_id)
        with self.lock:
            if camera_id not in self.streams or not self.streams[camera_id].is_active:
                return None
            
            stream_info = self.streams[camera_id]
            
            try:
                # Get the latest frame (non-blocking)
                return stream_info.frame_queue.get_nowait()
            except Empty:
                return None

    def is_stream_active(self, camera_id: str) -> bool:
        """Check if stream is active"""
        camera_id = str(camera_id)
        with self.lock:
            return camera_id in self.streams and self.streams[camera_id].is_active

    def get_stream_info(self, camera_id: str) -> Optional[Dict]:
        """Get stream information"""
        camera_id = str(camera_id)
        with self.lock:
            if camera_id not in self.streams:
                return None
            
            stream_info = self.streams[camera_id]
            return {
                "camera_id": camera_id,
                "worker_id": self.worker_id,
                "is_active": stream_info.is_active,
                "camera_type": stream_info.camera_type,
                "last_frame_time": stream_info.last_frame_time,
                "error_count": stream_info.error_count,
                "queue_size": stream_info.frame_queue.qsize()
            }

    async def stream_frames(self, camera_id: str) -> AsyncGenerator[bytes, None]:
        """Stream frames for MJPEG output"""
        camera_id = str(camera_id)
        while self.is_stream_active(camera_id):
            frame = self.get_frame(camera_id)
            if frame:
                yield b'--frame\r\n'
                yield b'Content-Type: image/jpeg\r\n\r\n'
                yield frame
                yield b'\r\n'
            else:
                # No frame available, wait a bit
                await asyncio.sleep(1/30)  # ~30 FPS

    def get_device_status(self) -> Dict:
        """Get status of all devices and conflicts"""
        with self.lock:
            return {
                "worker_id": self.worker_id,
                "active_streams": {camera_id: {
                    "device_index": info.device_index,
                    "camera_type": info.camera_type,
                    "is_active": info.is_active,
                    "error_count": info.error_count
                } for camera_id, info in self.streams.items()},
                "device_locks": dict(self.device_locks),
                "total_active_streams": len([s for s in self.streams.values() if s.is_active])
            }

    def cleanup_all_streams(self) -> None:
        """Stop all streams and cleanup resources"""
        with self.lock:
            camera_ids = list(self.streams.keys())
            for camera_id in camera_ids:
                self.stop_stream(camera_id)
            self.device_locks.clear()
            logger.info(f"Worker {self.worker_id} cleaned up all streams and device locks")

    def diagnose_device_conflicts(self) -> Dict:
        """Diagnose potential device conflicts and provide resolution suggestions"""
        with self.lock:
            conflicts = []
            suggestions = []
            
            # Check for duplicate device indices
            device_usage = {}
            for camera_id, stream_info in self.streams.items():
                if stream_info.camera_type.lower() == 'webcam' and stream_info.device_index is not None:
                    if stream_info.device_index in device_usage:
                        conflicts.append({
                            "type": "duplicate_device_index",
                            "device_index": stream_info.device_index,
                            "cameras": [device_usage[stream_info.device_index], camera_id],
                            "resolution": f"Only one camera can use device index {stream_info.device_index} at a time"
                        })
                    else:
                        device_usage[stream_info.device_index] = camera_id
            
            # Check for orphaned locks
            for device_index, locked_camera in self.device_locks.items():
                if locked_camera not in self.streams:
                    conflicts.append({
                        "type": "orphaned_lock",
                        "device_index": device_index,
                        "camera": locked_camera,
                        "resolution": f"Device index {device_index} is locked by non-existent camera {locked_camera}"
                    })
                    suggestions.append(f"Run cleanup_all_streams() to clear orphaned locks")
            
            return {
                "worker_id": self.worker_id,
                "conflicts": conflicts,
                "suggestions": suggestions,
                "current_device_locks": dict(self.device_locks),
                "active_webcam_streams": {
                    camera_id: {
                        "device_index": info.device_index,
                        "is_active": info.is_active
                    } for camera_id, info in self.streams.items() 
                    if info.camera_type.lower() == 'webcam'
                }
            }

    def get_active_cameras(self) -> list[str]:
        """Get list of active camera IDs"""
        with self.lock:
            return [camera_id for camera_id, stream_info in self.streams.items() if stream_info.is_active]