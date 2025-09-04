"""
Enhanced Face Recognition Worker with Integrated Camera Streaming
Combines camera streaming, face detection, and event reporting in a single service
"""
import asyncio
import logging
import os
import signal
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

from .detectors import create_detector, FaceDetector
from .embedder import create_embedder, FaceEmbedder
from .worker_client import WorkerClient
from .camera_streaming_service import WorkerCameraStreamingService
from .main import WorkerConfig, FaceDetectedEvent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EnhancedFaceRecognitionWorker:
    """Enhanced worker with integrated camera streaming and face recognition"""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.detector: FaceDetector = create_detector(config.detector_type)
        self.embedder: FaceEmbedder = create_embedder(config.embedder_type)
        self.staff_embeddings: Dict[str, List[float]] = {}
        self.http_client: Optional[httpx.AsyncClient] = None
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0
        
        # Worker client for registration and heartbeat
        self.worker_client = WorkerClient(config)
        
        # Enhanced camera streaming service
        self.streaming_service = WorkerCameraStreamingService(
            worker_id=f"worker-{os.getenv('WORKER_ID', 'unknown')}",
            face_processing_fps=self.config.worker_fps
        )
        
        # Set face processing callback
        self.streaming_service.set_face_processor(self._process_frame_for_faces)
        
        # Shared shutdown flag
        self._shutdown_requested = False
        
        # Event queue for failed events
        self.failed_events_queue: asyncio.Queue = asyncio.Queue()
        self.queue_processor_task: Optional[asyncio.Task] = None
        
        # Face processing control
        self.face_processing_enabled = True
        self.faces_processed_count = 0
    
    async def initialize(self):
        """Initialize the enhanced worker"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        await self._authenticate()
        await self._load_staff_embeddings()
        
        # Initialize worker client for registration and heartbeat
        await self.worker_client.initialize()
        
        # Set streaming service reference for status checks
        self.worker_client.set_streaming_service(self.streaming_service)
        
        # Set callbacks for camera assignment/release commands
        self.worker_client.set_camera_assignment_callback(self.assign_camera)
        self.worker_client.set_camera_release_callback(self.release_camera)
        
        # Start failed event queue processor
        self.queue_processor_task = asyncio.create_task(self._process_failed_events_queue())
        
        # Start shutdown monitor task
        self.shutdown_monitor_task = asyncio.create_task(self._monitor_shutdown())
        
        # Start background face processing task
        self.face_processing_task = asyncio.create_task(self._process_frames_background())
        
        logger.info("Enhanced worker initialized successfully")
    
    async def shutdown(self):
        """Cleanup resources with aggressive timeouts to prevent hanging"""
        logger.info("Starting enhanced worker shutdown... We should not wait too long before terminate the process. Just retry maximum 3 times to acknowledge the backend what worker will shutdown, then clean process (close camera streaming, memory, etc.) then shutdown process")
        
        # Set shutdown flag to stop any ongoing operations immediately
        self._shutdown_requested = True
        
        # 1. Stop all camera streams first - this should be fast
        try:
            logger.info("Cleaning up camera streams...")
            self.streaming_service.cleanup_all_streams()
            logger.info("✅ Camera streams cleaned up successfully")
        except Exception as e:
            logger.error(f"❌ Error cleaning up camera streams: {e}")
        
        # 2. Cancel and wait for background tasks with very short timeout
        tasks_to_cancel = []
        
        if self.queue_processor_task and not self.queue_processor_task.done():
            tasks_to_cancel.append(("queue_processor", self.queue_processor_task))
        
        if hasattr(self, 'shutdown_monitor_task') and self.shutdown_monitor_task and not self.shutdown_monitor_task.done():
            tasks_to_cancel.append(("shutdown_monitor", self.shutdown_monitor_task))
        
        if hasattr(self, 'face_processing_task') and self.face_processing_task and not self.face_processing_task.done():
            tasks_to_cancel.append(("face_processing", self.face_processing_task))
        
        # Cancel all tasks
        if tasks_to_cancel:
            logger.info(f"Cancelling {len(tasks_to_cancel)} background tasks...")
            for task_name, task in tasks_to_cancel:
                logger.info(f"Cancelling {task_name} task...")
                task.cancel()
            
            # Wait for tasks to complete with very short timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[task for _, task in tasks_to_cancel], return_exceptions=True), 
                    timeout=1.0  # Only wait 1 second
                )
                logger.info("✅ Background tasks cancelled successfully")
            except asyncio.TimeoutError:
                logger.warning("⚠️  Timeout waiting for background tasks - proceeding anyway")
            except Exception as e:
                logger.warning(f"⚠️  Error cancelling background tasks: {e}")
        
        # 3. Shutdown worker client with short timeout (this does the 3-attempt backend notification)
        try:
            logger.info("Shutting down worker client...")
            await asyncio.wait_for(self.worker_client.shutdown(), timeout=5.0)  # Allow time for 3 attempts
            logger.info("✅ Worker client shutdown complete")
        except asyncio.TimeoutError:
            logger.warning("⚠️  Worker client shutdown timeout - forcing shutdown")
        except Exception as e:
            logger.warning(f"⚠️  Error shutting down worker client: {e}")
        
        # 4. Close HTTP client with very short timeout
        if self.http_client:
            try:
                logger.info("Closing main HTTP client...")
                await asyncio.wait_for(self.http_client.aclose(), timeout=0.5)
                logger.info("✅ HTTP client closed")
            except asyncio.TimeoutError:
                logger.warning("⚠️  HTTP client close timeout - forcing close")
                try:
                    # Force close without waiting
                    self.http_client._client.close()
                except:
                    pass
            except Exception as e:
                logger.warning(f"⚠️  Error closing HTTP client: {e}")
        
        logger.info("🎉 Enhanced worker shutdown complete - process should exit cleanly now")
    
    async def _authenticate(self):
        """Get JWT token for API access"""
        try:
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/auth/token",
                json={
                    "grant_type": "api_key",
                    "api_key": self.config.worker_api_key,
                    "tenant_id": self.config.tenant_id,
                    "role": "worker",
                }
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            self.token_expires_at = time.time() + 3500  # Refresh before expiry
            
            logger.info("Successfully authenticated with API")
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid token"""
        if time.time() >= self.token_expires_at:
            await self._authenticate()
    
    async def _load_staff_embeddings(self):
        """Load staff embeddings for local pre-filtering"""
        try:
            await self._ensure_authenticated()
            
            # Get staff members with their embeddings
            response = await self.http_client.get(
                f"{self.config.api_url}/v1/staff",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"site_id": self.config.site_id, "include_embeddings": True}
            )
            
            if response.status_code == 200:
                staff_members = response.json()
                
                # Load embeddings for staff members
                for member in staff_members:
                    staff_id = member["staff_id"]
                    
                    # Try to get embedding from face images
                    if member.get("face_images"):
                        # Use the first face image for embedding
                        face_image = member["face_images"][0]
                        if face_image.get("embedding"):
                            self.staff_embeddings[staff_id] = face_image["embedding"]
                    
                    # Fallback to direct embedding field
                    elif member.get("face_embedding"):
                        self.staff_embeddings[staff_id] = member["face_embedding"]
                
                logger.info(f"Loaded {len(self.staff_embeddings)} staff embeddings for local matching")
            else:
                logger.warning(f"Failed to fetch staff embeddings: {response.status_code}")
            
        except Exception as e:
            logger.warning(f"Failed to load staff embeddings: {e}")
    
    def _is_staff_match(self, embedding: List[float], threshold: Optional[float] = None) -> tuple[bool, Optional[str]]:
        """
        Check if embedding matches any known staff member
        Returns (is_staff, staff_id) tuple
        """
        if threshold is None:
            threshold = self.config.staff_match_threshold
        
        if not self.staff_embeddings or not embedding:
            return False, None
        
        try:
            embedding_np = np.array(embedding, dtype=np.float32)
            embedding_np = embedding_np / np.linalg.norm(embedding_np)  # Normalize
            
            best_similarity = 0.0
            matched_staff_id = None
            
            for staff_id, staff_embedding in self.staff_embeddings.items():
                if not staff_embedding or len(staff_embedding) != len(embedding):
                    continue
                
                try:
                    staff_np = np.array(staff_embedding, dtype=np.float32)
                    staff_np = staff_np / np.linalg.norm(staff_np)  # Normalize
                    
                    # Cosine similarity (dot product of normalized vectors)
                    similarity = float(np.dot(embedding_np, staff_np))
                    
                    if similarity > best_similarity and similarity >= threshold:
                        best_similarity = similarity
                        matched_staff_id = staff_id
                        
                except Exception as e:
                    logger.debug(f"Error comparing with staff {staff_id}: {e}")
                    continue
            
            if matched_staff_id:
                logger.info(f"Matched staff member {matched_staff_id} with similarity {best_similarity:.3f}")
                return True, matched_staff_id
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error in staff matching: {e}")
            return False, None

    async def _process_frame_for_faces(self, frame: np.ndarray) -> int:
        """Process a single frame for face detection and recognition (callback from streaming)"""
        if not self.face_processing_enabled:
            return 0
            
        faces_processed = 0
        
        try:
            # Detect faces with enhanced logging
            detections = self.detector.detect(frame)
            logger.debug(f"Frame detection: Found {len(detections)} potential faces")
            
            for detection in detections:
                # Enhanced quality filtering
                confidence = detection["confidence"]
                bbox = detection["bbox"]
                
                # Skip low confidence detections
                if confidence < self.config.confidence_threshold:
                    logger.debug(f"Skipping low confidence detection: {confidence:.3f}")
                    continue
                
                # Skip very small faces (likely false positives)
                face_width, face_height = bbox[2], bbox[3]
                if min(face_width, face_height) < 40:  # Minimum 40px
                    logger.debug(f"Skipping small face: {face_width}x{face_height}")
                    continue
                
                # Skip faces that are too large (likely false positives)
                frame_area = frame.shape[0] * frame.shape[1]
                face_area = face_width * face_height
                face_ratio = face_area / frame_area
                if face_ratio > 0.8:  # Face shouldn't be more than 80% of frame
                    logger.debug(f"Skipping oversized face: {face_ratio:.2%} of frame")
                    continue
                
                # Extract face region
                bbox = detection["bbox"]
                x, y, w, h = map(int, bbox)
                face_image = frame[y:y+h, x:x+w]
                
                if face_image.size == 0:
                    continue
                
                # Generate embedding
                landmarks = detection.get("landmarks")
                if landmarks:
                    landmarks = np.array(landmarks)
                
                embedding = self.embedder.embed(face_image, landmarks)
                
                # Check if staff member with enhanced logging
                is_staff_local, staff_id = self._is_staff_match(embedding)
                
                if is_staff_local:
                    logger.info(f"✅ Staff member detected: {staff_id} (confidence: {detection['confidence']:.3f})")
                else:
                    logger.info(f"👤 Customer detected (confidence: {detection['confidence']:.3f})")
                
                # Get assigned camera ID from worker client
                assigned_camera_id = self.worker_client.get_assigned_camera()
                if not assigned_camera_id:
                    logger.warning("No camera assigned to worker, skipping face processing")
                    continue
                
                # Upload face image and get image bytes for API
                await self._ensure_authenticated()  # Ensure we have auth for upload
                face_image_bytes = await self._upload_face_image_to_api(face_image)
                
                # Create event without snapshot_url (will be handled by API)
                event = FaceDetectedEvent(
                    tenant_id=self.config.tenant_id,
                    site_id=self.config.site_id,
                    camera_id=assigned_camera_id,
                    timestamp=datetime.now(timezone.utc),
                    embedding=embedding,
                    bbox=bbox,
                    confidence=detection["confidence"],
                    snapshot_url=None,  # No longer needed - sending image directly
                    is_staff_local=is_staff_local,
                    staff_id=staff_id,
                )
                
                # Send to API with face image bytes
                await self._send_face_event(event, face_image_bytes)
                
                # Report face processed to worker client
                self.worker_client.report_face_processed()
                self.faces_processed_count += 1
                faces_processed += 1
        
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            await self.worker_client.report_error(f"Frame processing error: {str(e)}")
        
        return faces_processed

    async def _process_failed_events_queue(self):
        """Process failed events from the queue with periodic retry"""
        retry_interval = self.config.failed_event_retry_interval
        
        while True:
            try:
                # Process all events currently in queue
                processed = 0
                failed_again = []
                
                # Process existing events in queue
                while not self.failed_events_queue.empty():
                    try:
                        event_data = await asyncio.wait_for(
                            self.failed_events_queue.get(), timeout=1.0
                        )
                        
                        # Handle both old and new queue item formats for backward compatibility
                        if len(event_data) == 2:
                            # Old format: (event, retry_count)
                            event, retry_count = event_data
                            face_image_bytes = None
                        else:
                            # New format: (event, face_image_bytes, retry_count)
                            event, face_image_bytes, retry_count = event_data
                        
                        # Try to send the event
                        result = await self._send_face_event(event, face_image_bytes, max_retries=1)
                        
                        if "error" not in result:
                            processed += 1
                            logger.info(f"Successfully processed queued event: {result}")
                        elif retry_count < self.config.max_queue_retries:
                            failed_again.append((event, face_image_bytes, retry_count + 1))
                        else:
                            logger.error(f"Permanently dropping event after {self.config.max_queue_retries} retries: {event.camera_id}")
                            
                    except asyncio.TimeoutError:
                        break
                    except Exception as e:
                        logger.error(f"Error processing queued event: {e}")
                
                # Re-queue events that failed again
                for event_data in failed_again:
                    await self.failed_events_queue.put(event_data)
                
                if processed > 0:
                    logger.info(f"Processed {processed} queued events, {len(failed_again)} still pending")
                
                # Wait before next retry cycle
                await asyncio.sleep(retry_interval)
                
            except asyncio.CancelledError:
                logger.info("Failed events queue processor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in failed events queue processor: {e}")
                await asyncio.sleep(retry_interval)
    
    async def _send_face_event(self, event: FaceDetectedEvent, face_image_bytes: Optional[bytes] = None, max_retries: Optional[int] = None) -> Dict:
        """Send face event to API with face image as multipart form data"""
        if max_retries is None:
            max_retries = self.config.max_api_retries
            
        for attempt in range(max_retries + 1):
            try:
                await self._ensure_authenticated()
                
                if face_image_bytes:
                    # Send as multipart form data with face image
                    import json
                    
                    # Prepare the multipart form data
                    files = {
                        'face_image': ('face.jpg', face_image_bytes, 'image/jpeg')
                    }
                    
                    # Prepare the event data as form data
                    # Remove snapshot_url since we're sending the actual image
                    event_dict = event.model_dump(mode="json")
                    event_dict.pop('snapshot_url', None)  # Remove if present
                    
                    data = {
                        'event_data': json.dumps(event_dict)
                    }
                    
                    response = await self.http_client.post(
                        f"{self.config.api_url}/v1/events/face",
                        data=data,
                        files=files,
                        headers={"Authorization": f"Bearer {self.access_token}"},
                        timeout=30.0
                    )
                else:
                    # Fallback to JSON if no image (shouldn't happen but safety)
                    response = await self.http_client.post(
                        f"{self.config.api_url}/v1/events/face",
                        json=event.model_dump(mode="json"),
                        headers={"Authorization": f"Bearer {self.access_token}"},
                        timeout=30.0
                    )
                
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"Face event processed successfully: person_id={result.get('person_id')}, match={result.get('match')}")
                return result
                
            except httpx.TimeoutException as e:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries + 1}): {e}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Auth token expired, will be refreshed on next call
                    logger.warning("Authentication token expired, will refresh")
                    self.token_expires_at = 0
                elif e.response.status_code >= 500:
                    # Server error, retry
                    logger.warning(f"Server error (attempt {attempt + 1}/{max_retries + 1}): {e.response.status_code}")
                else:
                    # Client error, don't retry
                    logger.error(f"Client error: {e.response.status_code} - {e.response.text}")
                    return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
            except httpx.RequestError as e:
                logger.warning(f"Request error (attempt {attempt + 1}/{max_retries + 1}): {e}")
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}/{max_retries + 1}): {e}")
            
            # Exponential backoff with jitter
            if attempt < max_retries:
                wait_time = (2 ** attempt) + (0.1 * attempt)  # 0.1s, 1.1s, 2.2s, 4.3s...
                logger.info(f"Retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
        
        # All retries failed
        logger.error(f"Failed to send face event after {max_retries + 1} attempts, queuing for later retry")
        
        # Add to failed events queue for later processing
        try:
            await self.failed_events_queue.put((event, face_image_bytes, 1))  # (event, face_image_bytes, retry_count)
            logger.info("Event queued for later retry")
        except Exception as queue_error:
            logger.error(f"Failed to queue event: {queue_error}")
        
        return {"error": "Max retries exceeded, event queued for retry"}
    
    async def _upload_face_image_to_api(self, face_image: np.ndarray, max_retries: int = 3) -> Optional[str]:
        """Upload face image directly to API and return the snapshot URL with improved retry logic"""
        for attempt in range(max_retries):
            try:
                import cv2
                import uuid
                
                # Generate unique filename
                image_filename = f"face-{uuid.uuid4().hex[:8]}.jpg"
                
                # Convert face image to JPEG bytes with quality optimization
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85, cv2.IMWRITE_JPEG_OPTIMIZE, 1]
                success, img_buffer = cv2.imencode('.jpg', face_image, encode_params)
                
                if not success:
                    logger.warning(f"Failed to encode face image (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))  # Progressive delay
                        continue
                    return None
                
                img_bytes = img_buffer.tobytes()
                
                # Validate image size (should be reasonable)
                if len(img_bytes) < 1000 or len(img_bytes) > 10*1024*1024:  # 1KB to 10MB
                    logger.warning(f"Face image size unusual: {len(img_bytes)} bytes")
                
                # Store the image temporarily to send with the event
                # We'll return the image bytes so they can be sent with the face event
                logger.debug(f"Successfully encoded face image: {image_filename} ({len(img_bytes)} bytes) (attempt {attempt + 1})")
                return img_bytes  # Return the image bytes instead of a URL
                
            except Exception as e:
                logger.error(f"Unexpected encode error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
        
        logger.error(f"Failed to encode face image after {max_retries} attempts")
        return None
    
    async def _monitor_shutdown(self):
        """Monitor for shutdown signals and initiate graceful shutdown"""
        check_interval = 2  # Check every 2 seconds
        
        while True:
            try:
                if self.worker_client.should_shutdown() and not self._shutdown_requested:
                    logger.info("Shutdown monitor detected shutdown request - setting shutdown flag")
                    self._shutdown_requested = True
                    
                    # Send stop signal to backend with retries as requested
                    await self._send_stop_signal_to_backend()
                    
                    # Wait a reasonable time for graceful shutdown
                    await asyncio.sleep(10)
                    
                    # If we're still here after 10 seconds, force complete shutdown
                    if self._shutdown_requested:
                        logger.warning("Graceful shutdown period expired, completing shutdown...")
                        await self.worker_client.complete_shutdown()
                        
                        # Exit the process
                        logger.info("Exiting worker process")
                        import os
                        os._exit(0)
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                logger.info("Shutdown monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in shutdown monitor: {e}")
                await asyncio.sleep(check_interval)

    async def _process_frames_background(self):
        """Background task to process frames for face detection when streaming is active"""
        logger.info("Starting background face processing task")
        
        while True:
            try:
                if self._shutdown_requested:
                    break
                
                # Check all active camera streams for frames that need processing
                if hasattr(self.streaming_service, 'streams'):
                    for camera_id, stream_info in self.streaming_service.streams.items():
                        if (stream_info.is_active and 
                            stream_info.needs_face_processing and 
                            stream_info.latest_frame_for_processing is not None):
                            
                            try:
                                # Process the frame
                                frame = stream_info.latest_frame_for_processing
                                await self._process_frame_for_faces(frame)
                                
                                # Mark as processed
                                stream_info.needs_face_processing = False
                                stream_info.latest_frame_for_processing = None
                                
                            except Exception as e:
                                logger.error(f"Error processing frame for camera {camera_id}: {e}")
                                stream_info.needs_face_processing = False
                
                # Sleep briefly before checking again
                await asyncio.sleep(0.1)  # Check 10 times per second
                
            except asyncio.CancelledError:
                logger.info("Background face processing task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background face processing: {e}")
                await asyncio.sleep(1)  # Wait longer on error

    
    async def _send_stop_signal_to_backend(self):
        """Send stop signal to backend with 3 retry attempts, 1-second timeout each"""
        max_retries = 3
        timeout = 1.0  # 1 second timeout for each request as requested
        
        # Don't hang if worker client or http client is not available
        if not self.worker_client.worker_id or not self.http_client:
            logger.warning("Cannot send stop signal - worker not properly initialized")
            return False
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending stop signal to backend (attempt {attempt + 1}/{max_retries})")
                
                # Try to ensure authentication but don't hang on it
                try:
                    await asyncio.wait_for(self._ensure_authenticated(), timeout=0.5)
                except asyncio.TimeoutError:
                    logger.warning("Authentication timeout, proceeding with existing token")
                
                # Send the stop signal
                response = await self.http_client.post(
                    f"{self.config.api_url}/v1/workers/{self.worker_client.worker_id}/stop-signal",
                    headers={"Authorization": f"Bearer {self.access_token}"} if self.access_token else {},
                    json={
                        "worker_id": self.worker_client.worker_id,
                        "reason": "shutdown_requested",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    timeout=timeout
                )
                response.raise_for_status()
                
                logger.info(f"Successfully sent stop signal to backend on attempt {attempt + 1}")
                return True
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout sending stop signal (attempt {attempt + 1}/{max_retries})")
            except httpx.TimeoutException:
                logger.warning(f"Request timeout sending stop signal (attempt {attempt + 1}/{max_retries})")  
            except Exception as e:
                logger.warning(f"Error sending stop signal (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Don't wait after the last attempt
            if attempt < max_retries - 1:
                try:
                    await asyncio.wait_for(asyncio.sleep(0.1), timeout=0.2)
                except asyncio.TimeoutError:
                    pass
        
        logger.error(f"Failed to send stop signal to backend after {max_retries} attempts")
        return False
    
    def should_shutdown(self) -> bool:
        """Check if worker should shutdown"""
        return self._shutdown_requested or self.worker_client.should_shutdown()
    
    # Camera Management Methods (called by worker command handlers)
    
    async def assign_camera(self, camera_id: str, camera_type: str = "webcam", rtsp_url: str = None, device_index: int = None) -> bool:
        """Assign and start streaming for a camera"""
        try:
            # Start streaming with face processing
            success = self.streaming_service.start_stream(
                camera_id=camera_id,
                camera_type=camera_type,
                rtsp_url=rtsp_url,
                device_index=device_index
            )
            
            if success:
                logger.info(f"Successfully assigned and started streaming for camera {camera_id}")
                # Enable face processing
                self.face_processing_enabled = True
                await self.worker_client.report_processing()
                
                # Immediately send heartbeat with updated streaming status to notify frontend
                logger.info(f"Sending immediate status update for camera {camera_id}")
                await self.worker_client._send_heartbeat()
            else:
                logger.error(f"Failed to start streaming for assigned camera {camera_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error assigning camera {camera_id}: {e}")
            await self.worker_client.report_error(f"Camera assignment error: {str(e)}")
            return False
    
    async def release_camera(self, camera_id: str) -> bool:
        """Release and stop streaming for a camera"""
        try:
            success = self.streaming_service.stop_stream(camera_id)
            
            # Check if any cameras are still active
            if not self.streaming_service.get_active_cameras():
                # Disable face processing if no cameras active
                self.face_processing_enabled = False
                await self.worker_client.report_idle()
            
            # Immediately send heartbeat with updated streaming status
            logger.info(f"Sending immediate status update for released camera {camera_id}")
            await self.worker_client._send_heartbeat()
            
            logger.info(f"Released camera {camera_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error releasing camera {camera_id}: {e}")
            return False
    
    def get_stream_info(self, camera_id: str) -> Optional[Dict]:
        """Get streaming info for a camera"""
        return self.streaming_service.get_stream_info(camera_id)
    
    def is_camera_active(self, camera_id: str) -> bool:
        """Check if camera is actively streaming"""
        return self.streaming_service.is_stream_active(camera_id)
    
    async def get_camera_frame_stream(self, camera_id: str):
        """Get MJPEG stream for a camera"""
        async for chunk in self.streaming_service.stream_frames(camera_id):
            yield chunk


# FastAPI app for worker HTTP endpoints
def create_worker_app(worker: EnhancedFaceRecognitionWorker) -> FastAPI:
    """Create FastAPI application for worker HTTP endpoints"""
    app = FastAPI(
        title="Face Recognition Worker",
        description="Enhanced worker with camera streaming and face recognition",
        version="1.0.0"
    )
    
    # Log streaming storage
    from collections import deque
    import threading
    import json
    from datetime import datetime
    
    # Circular buffer to store recent log entries
    log_buffer = deque(maxlen=1000)  # Keep last 1000 log entries
    log_buffer_lock = threading.Lock()
    
    # Custom log handler to capture logs for streaming
    class LogStreamHandler(logging.Handler):
        def emit(self, record):
            try:
                log_entry = {
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": getattr(record, 'module', ''),
                    "funcName": getattr(record, 'funcName', ''),
                    "lineno": getattr(record, 'lineno', 0)
                }
                
                # Add exception info if present
                if record.exc_info:
                    log_entry["exception"] = self.format(record)
                
                with log_buffer_lock:
                    log_buffer.append(log_entry)
            except Exception:
                pass  # Avoid logging errors in log handler
    
    # Install the log handler
    log_stream_handler = LogStreamHandler()
    log_stream_handler.setLevel(logging.DEBUG)  # Capture all log levels
    
    # Add to root logger to capture all worker logs
    root_logger = logging.getLogger()
    root_logger.addHandler(log_stream_handler)
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "worker_id": worker.streaming_service.worker_id,
            "faces_processed": worker.faces_processed_count,
            "active_cameras": worker.streaming_service.get_active_cameras(),
            "face_processing_enabled": worker.face_processing_enabled
        }
    
    @app.get("/cameras/{camera_id}/stream/feed")
    async def get_camera_feed(camera_id: str):
        """Get MJPEG stream for a camera"""
        if not worker.is_camera_active(camera_id):
            raise HTTPException(status_code=404, detail="Camera stream not active")
        
        async def stream_wrapper():
            async for chunk in worker.streaming_service.stream_frames(camera_id):
                yield chunk
        
        return StreamingResponse(
            stream_wrapper(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )
    
    @app.get("/cameras/{camera_id}/stream/status")
    async def get_camera_stream_status(camera_id: str):
        """Get streaming status for a camera"""
        stream_info = worker.get_stream_info(camera_id)
        if not stream_info:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        return stream_info
    
    @app.post("/cameras/{camera_id}/stream/start")
    async def start_camera_stream(camera_id: str, request: Request):
        """Start streaming for a camera (from API delegation)"""
        body = await request.json()
        
        success = await worker.assign_camera(
            camera_id=camera_id,
            camera_type=body.get("camera_type", "webcam"),
            rtsp_url=body.get("rtsp_url"),
            device_index=body.get("device_index")
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to start camera stream")
        
        return {
            "message": "Camera stream started successfully",
            "camera_id": camera_id,
            "worker_id": worker.streaming_service.worker_id
        }
    
    @app.post("/cameras/{camera_id}/stream/stop")
    async def stop_camera_stream(camera_id: str):
        """Stop streaming for a camera"""
        success = await worker.release_camera(camera_id)
        return {
            "message": "Camera stream stopped",
            "camera_id": camera_id,
            "success": success
        }
    
    @app.get("/streaming/debug")
    async def get_streaming_debug():
        """Get debug information about streaming service"""
        return {
            "device_status": worker.streaming_service.get_device_status(),
            "conflicts": worker.streaming_service.diagnose_device_conflicts()
        }
    
    @app.get("/logs/recent")
    async def get_recent_logs(limit: int = 100):
        """Get recent log entries"""
        with log_buffer_lock:
            # Get last N entries
            recent_logs = list(log_buffer)[-limit:] if limit > 0 else list(log_buffer)
        
        return {
            "logs": recent_logs,
            "total_count": len(recent_logs),
            "buffer_size": len(log_buffer)
        }
    
    @app.get("/logs/stream")
    async def stream_logs(request: Request):
        """Server-Sent Events stream for real-time logs"""
        try:
            from sse_starlette import EventSourceResponse
            
            async def log_stream_generator():
                # Send recent logs first
                with log_buffer_lock:
                    recent_logs = list(log_buffer)[-50:]  # Last 50 entries
                
                # Send initial batch
                if recent_logs:
                    yield {
                        "event": "initial_logs",
                        "data": json.dumps({
                            "logs": recent_logs,
                            "message": "Initial log entries"
                        })
                    }
                
                # Track the last position we sent
                last_sent_count = len(log_buffer)
                
                try:
                    while True:
                        # Check for client disconnect
                        if await request.is_disconnected():
                            break
                        
                        # Check for new log entries
                        with log_buffer_lock:
                            current_count = len(log_buffer)
                            if current_count > last_sent_count:
                                # Send new entries
                                new_logs = list(log_buffer)[last_sent_count:]
                                yield {
                                    "event": "new_logs", 
                                    "data": json.dumps({
                                        "logs": new_logs,
                                        "timestamp": datetime.now().isoformat()
                                    })
                                }
                                last_sent_count = current_count
                        
                        # Wait before checking again
                        await asyncio.sleep(0.5)  # Check every 500ms
                        
                except asyncio.CancelledError:
                    pass  # Client disconnected
            
            return EventSourceResponse(log_stream_generator())
            
        except ImportError:
            # Manual SSE implementation fallback
            async def manual_sse_generator():
                # Send SSE headers manually
                yield "data: " + json.dumps({
                    "event": "connection_established", 
                    "message": "Log stream connected"
                }) + "\n\n"
                
                # Send recent logs first
                with log_buffer_lock:
                    recent_logs = list(log_buffer)[-50:]
                
                if recent_logs:
                    yield "event: initial_logs\n"
                    yield "data: " + json.dumps({
                        "logs": recent_logs,
                        "message": "Initial log entries"
                    }) + "\n\n"
                
                last_sent_count = len(log_buffer)
                
                try:
                    while True:
                        if await request.is_disconnected():
                            break
                        
                        with log_buffer_lock:
                            current_count = len(log_buffer)
                            if current_count > last_sent_count:
                                new_logs = list(log_buffer)[last_sent_count:]
                                yield "event: new_logs\n"
                                yield "data: " + json.dumps({
                                    "logs": new_logs,
                                    "timestamp": datetime.now().isoformat()
                                }) + "\n\n"
                                last_sent_count = current_count
                        
                        await asyncio.sleep(0.5)
                        
                except asyncio.CancelledError:
                    pass
            
            return StreamingResponse(
                manual_sse_generator(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream"
                }
            )
    
    @app.post("/logs/test")
    async def test_log_generation():
        """Generate test log entries for testing"""
        logger.info("Test INFO log entry from API endpoint")
        logger.warning("Test WARNING log entry from API endpoint") 
        logger.error("Test ERROR log entry from API endpoint")
        logger.debug("Test DEBUG log entry from API endpoint")
        
        return {"message": "Test log entries generated"}
    
    return app


async def run_enhanced_worker():
    """Run the enhanced worker with HTTP server"""
    # Global configuration instance
    config = WorkerConfig()
    config.validate()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    worker = EnhancedFaceRecognitionWorker(config)
    
    # Shutdown event to coordinate between signal handler and main loop
    shutdown_event = asyncio.Event()
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        worker._shutdown_requested = True
        shutdown_event.set()
        
        # Send stop signal to backend immediately
        asyncio.create_task(worker._send_stop_signal_to_backend())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server = None
    try:
        await worker.initialize()
        
        # Create and configure FastAPI app
        app = create_worker_app(worker)
        
        # Get worker HTTP port (default 8090, can be overridden)
        worker_port = int(os.getenv("WORKER_HTTP_PORT", "8090"))
        
        # Create uvicorn server
        config_uvicorn = uvicorn.Config(
            app, 
            host="0.0.0.0", 
            port=worker_port,
            log_level="info"
        )
        server = uvicorn.Server(config_uvicorn)
        
        logger.info(f"Starting enhanced worker HTTP server on port {worker_port}")
        
        # Start server in background task
        server_task = asyncio.create_task(server.serve())
        
        # Wait for shutdown signal or server to complete
        done, pending = await asyncio.wait(
            [server_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # If shutdown event was set, stop the server
        if shutdown_event.is_set():
            logger.info("Shutdown event detected, stopping server...")
            if server:
                server.should_exit = True
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            
            # Wait briefly for server to shutdown
            try:
                await asyncio.wait_for(server_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Server shutdown timeout, proceeding with worker shutdown")
        
    except Exception as e:
        logger.error(f"Enhanced worker error: {e}")
        
    finally:
        # Ensure worker shutdown
        await worker.shutdown()
        
        # Force exit if still running
        logger.info("Worker shutdown complete, exiting process")
        os._exit(0)


if __name__ == "__main__":
    asyncio.run(run_enhanced_worker())