from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel


API_URL = os.getenv("API_URL", "http://api:8080")
TENANT_ID = os.getenv("TENANT_ID", "t-dev")
SITE_ID = os.getenv("SITE_ID", "s-1")
CAMERA_ID = os.getenv("CAMERA_ID", "c-1")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "dev-api-key")


async def get_token(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{API_URL}/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": WORKER_API_KEY,
            "tenant_id": TENANT_ID,
            "role": "worker",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def simulate_event_post(token: str, client: httpx.AsyncClient) -> None:
    evt = FaceDetectedEvent(
        tenant_id=TENANT_ID,
        site_id=SITE_ID,
        camera_id=CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        embedding=[0.0] * 512,
        bbox=[10, 10, 100, 100],
        snapshot_url=None,
    )
    r = await client.post(
        f"{API_URL}/v1/events/face",
        json=evt.model_dump(mode="json"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    # Endpoint may not exist yet in bootstrap; ignore failures
    print("POST /v1/events/face =>", r.status_code)


import asyncio
import cv2
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import numpy as np
from pydantic import BaseModel

from .detectors import create_detector, FaceDetector
from .embedder import create_embedder, FaceEmbedder
from .worker_client import WorkerClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment (will be replaced by config object later)
API_URL = os.getenv("API_URL", "http://localhost:8080")
TENANT_ID = os.getenv("TENANT_ID", "t-dev")
SITE_ID = os.getenv("SITE_ID", "s-1")
CAMERA_ID = os.getenv("CAMERA_ID", "c-1")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "dev-api-key")
DETECTOR_TYPE = os.getenv("DETECTOR_TYPE", "yunet")
EMBEDDER_TYPE = os.getenv("EMBEDDER_TYPE", "insightface")
WORKER_FPS = int(os.getenv("WORKER_FPS", "5"))
RTSP_URL = os.getenv("RTSP_URL", "")
USB_CAMERA = int(os.getenv("USB_CAMERA", "0"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"


class WorkerConfig:
    """Configuration management for the face recognition worker"""
    
    def __init__(self):
        # API Configuration
        self.api_url = os.getenv("API_URL", "http://localhost:8080")
        self.tenant_id = os.getenv("TENANT_ID", "t-dev")
        self.site_id = os.getenv("SITE_ID", "s-1")
        self.camera_id = os.getenv("CAMERA_ID", "c-1")
        self.worker_api_key = os.getenv("WORKER_API_KEY", "dev-api-key")
        
        # Worker Configuration
        self.detector_type = os.getenv("DETECTOR_TYPE", "yunet")  # yunet, mock
        self.embedder_type = os.getenv("EMBEDDER_TYPE", "insightface")  # insightface, mock
        self.worker_fps = int(os.getenv("WORKER_FPS", "5"))
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
        self.staff_match_threshold = float(os.getenv("STAFF_MATCH_THRESHOLD", "0.8"))
        self.mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
        
        # Camera Configuration
        self.rtsp_url = os.getenv("RTSP_URL", "")
        self.usb_camera = int(os.getenv("USB_CAMERA", "0"))
        self.frame_width = int(os.getenv("FRAME_WIDTH", "640"))
        self.frame_height = int(os.getenv("FRAME_HEIGHT", "480"))
        
        # Retry and Queue Configuration
        self.max_api_retries = int(os.getenv("MAX_API_RETRIES", "3"))
        self.max_camera_reconnect_attempts = int(os.getenv("MAX_CAMERA_RECONNECT_ATTEMPTS", "5"))
        self.failed_event_retry_interval = int(os.getenv("FAILED_EVENT_RETRY_INTERVAL", "30"))
        self.max_queue_retries = int(os.getenv("MAX_QUEUE_RETRIES", "5"))
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
    
    def validate(self):
        """Validate configuration and log warnings for important settings"""
        if not self.worker_api_key or self.worker_api_key == "dev-api-key":
            logger.warning("Using default API key - this should be changed in production")
        
        if self.mock_mode:
            logger.info("Running in MOCK MODE - no real cameras or ML models will be used")
        
        if not self.rtsp_url and self.usb_camera is None:
            logger.warning("No camera source configured (RTSP_URL or USB_CAMERA)")
        
        if self.worker_fps > 10:
            logger.warning(f"High FPS setting ({self.worker_fps}) may impact performance")
        
        logger.info(f"Worker configured: {self.detector_type} detector, {self.embedder_type} embedder, {self.worker_fps} FPS")


# Global configuration instance
config = WorkerConfig()


class FaceDetectedEvent(BaseModel):
    tenant_id: str
    site_id: str
    camera_id: str
    timestamp: datetime
    embedding: List[float]
    bbox: List[float]
    confidence: float = 0.0
    snapshot_url: Optional[str] = None
    is_staff_local: bool = False
    staff_id: Optional[str] = None


class FaceRecognitionWorker:
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
        
        # Event queue for failed events
        self.failed_events_queue: asyncio.Queue = asyncio.Queue()
        self.queue_processor_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize the worker"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        await self._authenticate()
        await self._load_staff_embeddings()
        
        # Initialize worker client for registration and heartbeat
        await self.worker_client.initialize()
        
        # Start failed event queue processor
        self.queue_processor_task = asyncio.create_task(self._process_failed_events_queue())
        
        logger.info("Worker initialized successfully")
    
    async def shutdown(self):
        """Cleanup resources"""
        # Shutdown worker client first
        await self.worker_client.shutdown()
        
        # Cancel queue processor
        if self.queue_processor_task and not self.queue_processor_task.done():
            self.queue_processor_task.cancel()
            try:
                await self.queue_processor_task
            except asyncio.CancelledError:
                pass
        
        if self.http_client:
            await self.http_client.aclose()
        
        logger.info("Worker shutdown complete")
    
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
            # Continue without staff filtering - all faces will be processed as visitors
    
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
                        event, retry_count = event_data
                        
                        # Try to send the event
                        result = await self._send_face_event(event, max_retries=1)
                        
                        if "error" not in result:
                            processed += 1
                            logger.info(f"Successfully processed queued event: {result}")
                        elif retry_count < self.config.max_queue_retries:
                            failed_again.append((event, retry_count + 1))
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
    
    async def _send_face_event(self, event: FaceDetectedEvent, max_retries: Optional[int] = None) -> Dict:
        """Send face event to API with exponential backoff retry logic"""
        if max_retries is None:
            max_retries = self.config.max_api_retries
        for attempt in range(max_retries + 1):
            try:
                await self._ensure_authenticated()
                
                response = await self.http_client.post(
                    f"{self.config.api_url}/v1/events/face",
                    json=event.model_dump(mode="json"),
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    timeout=30.0  # Increased timeout for ML processing
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
            await self.failed_events_queue.put((event, 1))  # (event, retry_count)
            logger.info("Event queued for later retry")
        except Exception as queue_error:
            logger.error(f"Failed to queue event: {queue_error}")
        
        return {"error": "Max retries exceeded, event queued for retry"}
    
    async def process_frame(self, frame: np.ndarray) -> int:
        """Process a single frame and detect faces"""
        faces_processed = 0
        
        try:
            # Detect faces
            detections = self.detector.detect(frame)
            
            for detection in detections:
                if detection["confidence"] < self.config.confidence_threshold:
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
                
                # Check if staff member
                is_staff_local, staff_id = self._is_staff_match(embedding)
                
                # Create event
                event = FaceDetectedEvent(
                    tenant_id=self.config.tenant_id,
                    site_id=self.config.site_id,
                    camera_id=self.config.camera_id,
                    timestamp=datetime.now(timezone.utc),
                    embedding=embedding,
                    bbox=bbox,
                    confidence=detection["confidence"],
                    is_staff_local=is_staff_local,
                    staff_id=staff_id,
                )
                
                # Send to API
                await self._send_face_event(event)
                
                # Report face processed to worker client
                self.worker_client.report_face_processed()
                faces_processed += 1
        
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            await self.worker_client.report_error(f"Frame processing error: {str(e)}")
        
        return faces_processed
    
    async def run_camera_capture(self):
        """Run continuous camera capture and processing"""
        cap = None
        reconnect_attempts = 0
        max_reconnect_attempts = self.config.max_camera_reconnect_attempts
        
        try:
            while True:
                try:
                    # Initialize camera
                    if self.config.rtsp_url:
                        cap = cv2.VideoCapture(self.config.rtsp_url)
                        logger.info(f"Opening RTSP stream: {self.config.rtsp_url}")
                    else:
                        cap = cv2.VideoCapture(self.config.usb_camera)
                        logger.info(f"Opening USB camera: {self.config.usb_camera}")
                    
                    if not cap.isOpened():
                        raise RuntimeError("Failed to open camera")
                    
                    # Set camera properties for optimal performance
                    cap.set(cv2.CAP_PROP_FPS, self.config.worker_fps)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer to get latest frames
                    
                    frame_delay = 1.0 / self.config.worker_fps
                    last_process_time = 0
                    reconnect_attempts = 0  # Reset on successful connection
                    
                    logger.info(f"Camera connected successfully, processing at {self.config.worker_fps} FPS")
                    
                    # Main processing loop
                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            logger.warning("Failed to read frame, attempting reconnection")
                            break  # Break to outer loop for reconnection
                        
                        current_time = time.time()
                        
                        # Process frame based on FPS setting
                        if current_time - last_process_time >= frame_delay:
                            try:
                                faces_count = await self.process_frame(frame)
                                if faces_count > 0:
                                    logger.info(f"Processed {faces_count} faces at {datetime.now().strftime('%H:%M:%S')}")
                                last_process_time = current_time
                                
                            except Exception as frame_error:
                                logger.error(f"Frame processing error: {frame_error}")
                                continue
                        
                        # Small delay to prevent CPU overload
                        await asyncio.sleep(0.01)
                
                except KeyboardInterrupt:
                    logger.info("Stopping camera capture")
                    break
                    
                except Exception as camera_error:
                    logger.error(f"Camera error: {camera_error}")
                    await self.worker_client.report_error(f"Camera error: {str(camera_error)}")
                    
                    if cap:
                        cap.release()
                        cap = None
                    
                    reconnect_attempts += 1
                    if reconnect_attempts >= max_reconnect_attempts:
                        logger.error(f"Max reconnection attempts ({max_reconnect_attempts}) reached")
                        break
                    
                    # Exponential backoff for reconnection
                    wait_time = min(2 ** reconnect_attempts, 60)
                    logger.info(f"Waiting {wait_time}s before reconnection attempt {reconnect_attempts}")
                    await asyncio.sleep(wait_time)
        
        finally:
            if cap:
                cap.release()
                logger.info("Camera released")
    
    async def run_simulation(self):
        """Run simulation mode for testing"""
        logger.info("Running in simulation mode")
        
        while True:
            try:
                # Generate mock frame
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                
                faces_count = await self.process_frame(frame)
                if faces_count > 0:
                    logger.info(f"Simulated {faces_count} faces")
                
                await asyncio.sleep(1.0 / self.config.worker_fps)
                
            except KeyboardInterrupt:
                logger.info("Stopping simulation")
                break
            except Exception as e:
                logger.error(f"Simulation error: {e}")
                await asyncio.sleep(1)


async def main():
    """Main worker function"""
    # Validate configuration
    config.validate()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    worker = FaceRecognitionWorker(config)
    
    try:
        await worker.initialize()
        
        if config.mock_mode:
            await worker.run_simulation()
        else:
            await worker.run_camera_capture()
    
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

