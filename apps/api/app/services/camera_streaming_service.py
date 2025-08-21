import asyncio
import cv2
import logging
from typing import Dict, Optional, AsyncGenerator
import threading
import time
from queue import Queue, Empty
from dataclasses import dataclass, field

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


class CameraStreamingService:
    def __init__(self):
        self.streams: Dict[str, StreamInfo] = {}
        self.lock = threading.Lock()
        self.device_locks: Dict[int, str] = {}  # Track which camera_id is using each device index
        
    def _capture_frames(self, stream_info: StreamInfo) -> None:
        """Capture frames in a separate thread"""
        thread_name = f"CaptureThread-{stream_info.camera_id}"
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
                
                # Add camera ID as metadata to frame (for debugging)
                if frame is not None:
                    # Add small text overlay to identify the camera
                    cv2.putText(frame, f"Cam: {stream_info.camera_id} (Dev: {stream_info.device_index})", 
                              (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # Encode frame as JPEG
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
        with self.lock:
            if camera_id in self.streams and self.streams[camera_id].is_active:
                logger.info(f"Stream for camera {camera_id} is already active")
                return True
            
            # Check for device conflicts for webcam type
            if camera_type.lower() == 'webcam' and device_index is not None:
                if device_index in self.device_locks:
                    existing_camera = self.device_locks[device_index]
                    logger.error(f"Device index {device_index} is already in use by camera {existing_camera}. Cannot start camera {camera_id}")
                    return False
            
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
                
                # Start capture thread
                stream_info.thread = threading.Thread(
                    target=self._capture_frames,
                    args=(stream_info,),
                    daemon=True
                )
                stream_info.thread.start()
                
                self.streams[camera_id] = stream_info
                logger.info(f"Successfully started stream for camera {camera_id} (type: {camera_type}, device_index: {device_index})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start stream for camera {camera_id}: {e}")
                if stream_info.cap:
                    stream_info.cap.release()
                return False

    def stop_stream(self, camera_id: str) -> bool:
        """Stop streaming for a camera"""
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
            
            # Wait for thread to finish
            if stream_info.thread and stream_info.thread.is_alive():
                stream_info.thread.join(timeout=5)
            
            # Release resources
            if stream_info.cap:
                stream_info.cap.release()
            
            # Clear frame queue
            while not stream_info.frame_queue.empty():
                try:
                    stream_info.frame_queue.get_nowait()
                except Empty:
                    break
            
            del self.streams[camera_id]
            logger.info(f"Stopped stream for camera {camera_id}")
            return True

    def get_frame(self, camera_id: str) -> Optional[bytes]:
        """Get the latest frame for a camera"""
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
        with self.lock:
            return camera_id in self.streams and self.streams[camera_id].is_active

    def get_stream_info(self, camera_id: str) -> Optional[Dict]:
        """Get stream information"""
        with self.lock:
            if camera_id not in self.streams:
                return None
            
            stream_info = self.streams[camera_id]
            return {
                "camera_id": camera_id,
                "is_active": stream_info.is_active,
                "camera_type": stream_info.camera_type,
                "last_frame_time": stream_info.last_frame_time,
                "error_count": stream_info.error_count,
                "queue_size": stream_info.frame_queue.qsize()
            }

    async def stream_frames(self, camera_id: str) -> AsyncGenerator[bytes, None]:
        """Stream frames for Server-Sent Events"""
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


# Global instance
streaming_service = CameraStreamingService()