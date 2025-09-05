"""
Camera Manager for Worker

This module manages camera capture and provides frames to both
face recognition processing and WebRTC streaming components.

Features:
- Shared camera access between face detection and WebRTC streaming
- Thread-safe frame buffer management
- Camera configuration and reconnection handling
- Frame rate control and buffering
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Optional, Any, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class CameraManager:
    """Manages camera capture and frame distribution"""
    
    def __init__(self):
        # Active cameras: {camera_id: camera_info}
        self.active_cameras: Dict[int, Dict[str, Any]] = {}
        
        # Frame buffers: {camera_id: latest_frame}
        self.frame_buffers: Dict[int, np.ndarray] = {}
        
        # Camera capture threads: {camera_id: thread}
        self.capture_threads: Dict[int, threading.Thread] = {}
        
        # Thread control flags: {camera_id: should_stop}
        self.stop_flags: Dict[int, threading.Event] = {}
        
        # Frame locks for thread safety: {camera_id: lock}
        self.frame_locks: Dict[int, threading.Lock] = {}
        
        # Camera statistics: {camera_id: stats}
        self.camera_stats: Dict[int, Dict[str, Any]] = {}
        
    async def start_camera(self, camera_id: int, camera_config: Dict[str, Any]) -> bool:
        """Start camera capture in separate thread"""
        
        if camera_id in self.active_cameras:
            logger.warning(f"Camera {camera_id} already active")
            return True
            
        logger.info(f"Starting camera {camera_id} with config: {camera_config}")
        
        # Initialize camera data structures
        self.active_cameras[camera_id] = camera_config
        self.frame_buffers[camera_id] = None
        self.frame_locks[camera_id] = threading.Lock()
        self.stop_flags[camera_id] = threading.Event()
        self.camera_stats[camera_id] = {
            "start_time": time.time(),
            "frames_captured": 0,
            "last_frame_time": 0,
            "fps": 0,
            "errors": 0
        }
        
        # Start capture thread
        thread = threading.Thread(
            target=self._camera_capture_thread,
            args=(camera_id, camera_config),
            daemon=True,
            name=f"camera-{camera_id}"
        )
        
        self.capture_threads[camera_id] = thread
        thread.start()
        
        # Wait a moment to see if camera starts successfully
        await asyncio.sleep(1.0)
        
        if camera_id in self.frame_buffers and self.frame_buffers[camera_id] is not None:
            logger.info(f"Camera {camera_id} started successfully")
            return True
        else:
            logger.error(f"Camera {camera_id} failed to start")
            await self.stop_camera(camera_id)
            return False
            
    async def stop_camera(self, camera_id: int):
        """Stop camera capture and cleanup resources"""
        
        if camera_id not in self.active_cameras:
            logger.warning(f"Camera {camera_id} not active")
            return
            
        logger.info(f"Stopping camera {camera_id}")
        
        # Signal thread to stop
        if camera_id in self.stop_flags:
            self.stop_flags[camera_id].set()
            
        # Wait for thread to finish
        if camera_id in self.capture_threads:
            thread = self.capture_threads[camera_id]
            if thread.is_alive():
                thread.join(timeout=5.0)
                if thread.is_alive():
                    logger.warning(f"Camera {camera_id} thread did not stop gracefully")
            del self.capture_threads[camera_id]
            
        # Cleanup resources
        if camera_id in self.active_cameras:
            del self.active_cameras[camera_id]
        if camera_id in self.frame_buffers:
            del self.frame_buffers[camera_id]
        if camera_id in self.frame_locks:
            del self.frame_locks[camera_id]
        if camera_id in self.stop_flags:
            del self.stop_flags[camera_id]
        if camera_id in self.camera_stats:
            del self.camera_stats[camera_id]
            
        logger.info(f"Camera {camera_id} stopped and cleaned up")
        
    def get_latest_frame(self, camera_id: int) -> Optional[np.ndarray]:
        """Get the latest frame from camera (thread-safe)"""
        
        if camera_id not in self.frame_buffers:
            return None
            
        with self.frame_locks[camera_id]:
            frame = self.frame_buffers[camera_id]
            if frame is not None:
                return frame.copy()  # Return copy for thread safety
            return None
            
    def is_camera_active(self, camera_id: int) -> bool:
        """Check if camera is currently active"""
        return camera_id in self.active_cameras
        
    def get_camera_stats(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """Get camera statistics"""
        return self.camera_stats.get(camera_id)
        
    def get_active_cameras(self) -> Dict[int, Dict[str, Any]]:
        """Get list of active cameras"""
        return self.active_cameras.copy()
        
    def _camera_capture_thread(self, camera_id: int, camera_config: Dict[str, Any]):
        """Camera capture thread function"""
        
        cap = None
        stats = self.camera_stats[camera_id]
        
        try:
            # Initialize camera based on config
            camera_type = camera_config.get("camera_type", "webcam")
            
            if camera_type == "rtsp":
                rtsp_url = camera_config.get("rtsp_url")
                if not rtsp_url:
                    logger.error(f"No RTSP URL provided for camera {camera_id}")
                    return
                cap = cv2.VideoCapture(rtsp_url)
                logger.info(f"Camera {camera_id}: Opening RTSP stream: {rtsp_url}")
            else:
                # Webcam
                device_index = camera_config.get("device_index", 0)
                cap = cv2.VideoCapture(device_index)
                logger.info(f"Camera {camera_id}: Opening webcam device: {device_index}")
                
            if not cap or not cap.isOpened():
                logger.error(f"Camera {camera_id}: Failed to open camera")
                return
                
            # Set camera properties
            fps = camera_config.get("fps", 30)
            width = camera_config.get("width", 640)
            height = camera_config.get("height", 480)
            
            cap.set(cv2.CAP_PROP_FPS, fps)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffering
            
            logger.info(f"Camera {camera_id}: Configured for {width}x{height} at {fps} FPS")
            
            # Capture loop
            last_stats_update = time.time()
            frame_count = 0
            
            while not self.stop_flags[camera_id].is_set():
                ret, frame = cap.read()
                
                if not ret:
                    stats["errors"] += 1
                    logger.warning(f"Camera {camera_id}: Failed to read frame")
                    time.sleep(0.1)  # Brief pause on error
                    continue
                    
                # Update frame buffer (thread-safe)
                with self.frame_locks[camera_id]:
                    self.frame_buffers[camera_id] = frame
                    
                # Update statistics
                current_time = time.time()
                stats["frames_captured"] += 1
                stats["last_frame_time"] = current_time
                frame_count += 1
                
                # Update FPS every second
                if current_time - last_stats_update >= 1.0:
                    stats["fps"] = frame_count / (current_time - last_stats_update)
                    frame_count = 0
                    last_stats_update = current_time
                    logger.debug(f"Camera {camera_id}: capture FPS ~{stats['fps']:.1f}, last_frame_age={(time.time()-stats['last_frame_time']):.2f}s")
                    
                # Small delay to prevent CPU overload
                time.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Camera {camera_id} capture error: {e}")
            stats["errors"] += 1
        finally:
            if cap:
                cap.release()
                logger.info(f"Camera {camera_id}: Capture released")
                
    async def shutdown(self):
        """Shutdown all cameras and cleanup"""
        
        logger.info("Shutting down camera manager")
        
        # Stop all active cameras
        camera_ids = list(self.active_cameras.keys())
        for camera_id in camera_ids:
            await self.stop_camera(camera_id)
            
        logger.info("Camera manager shutdown complete")
