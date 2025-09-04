from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
import numpy as np
from pydantic import BaseModel
from common.models import FaceDetectedEvent

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue with environment variables only
    pass


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


async def simulate_event_with_image(token: str, client: httpx.AsyncClient) -> None:
    """Simulate face detection with actual image upload and improved reliability"""
    import base64
    import io
    import uuid
    from PIL import Image, ImageDraw
    
    # Create a mock face image (150x150 pixels for better quality)
    img_size = 150
    img = Image.new('RGB', (img_size, img_size), color='lightblue')
    draw = ImageDraw.Draw(img)
    
    # Draw a more detailed face-like shape
    face_margin = 20
    face_size = img_size - 2 * face_margin
    
    # Face outline
    draw.ellipse([face_margin, face_margin, face_margin + face_size, face_margin + face_size], 
                fill='peachpuff', outline='darkgoldenrod', width=3)
    
    # Eyes
    eye_size = face_size // 8
    left_eye_x = face_margin + face_size // 3 - eye_size
    right_eye_x = face_margin + 2 * face_size // 3 - eye_size
    eye_y = face_margin + face_size // 3
    
    draw.ellipse([left_eye_x, eye_y, left_eye_x + eye_size * 2, eye_y + eye_size], 
                fill='darkblue', outline='black', width=1)
    draw.ellipse([right_eye_x, eye_y, right_eye_x + eye_size * 2, eye_y + eye_size], 
                fill='darkblue', outline='black', width=1)
    
    # Nose
    nose_x = face_margin + face_size // 2
    nose_y = face_margin + face_size // 2
    draw.polygon([(nose_x, nose_y - 8), (nose_x - 5, nose_y + 5), (nose_x + 5, nose_y + 5)], 
                fill='rosybrown', outline='sienna')
    
    # Mouth
    mouth_left = face_margin + face_size // 3
    mouth_right = face_margin + 2 * face_size // 3
    mouth_y = face_margin + 2 * face_size // 3
    mouth_h = face_size // 6
    
    draw.arc([mouth_left, mouth_y, mouth_right, mouth_y + mouth_h],
            start=0, end=180, fill='darkred', width=3)
    
    # Convert to bytes with high quality
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='JPEG', quality=95, optimize=True)
    img_bytes = img_buffer.getvalue()
    
    # Upload image to MinIO via API with retry logic
    max_retries = 3
    image_filename = f"faces-raw/mock-face-{uuid.uuid4().hex[:8]}.jpg"
    snapshot_url = None
    
    for attempt in range(max_retries):
        try:
            # Get presigned upload URL
            upload_response = await client.post(
                f"{API_URL}/v1/files/upload-url",
                json={"filename": image_filename, "content_type": "image/jpeg"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            
            if upload_response.status_code == 200:
                upload_data = upload_response.json()
                presigned_url = upload_data["upload_url"]
                
                # Upload the image
                upload_result = await client.put(
                    presigned_url,
                    content=img_bytes,
                    headers={"Content-Type": "image/jpeg"},
                    timeout=30,
                )
                
                if upload_result.status_code in [200, 204]:
                    # Create download URL for the event
                    download_response = await client.post(
                        f"{API_URL}/v1/files/download-url",
                        json={"filename": image_filename},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                    )
                    
                    if download_response.status_code == 200:
                        snapshot_url = download_response.json()["download_url"]
                        print(f"✅ Successfully uploaded mock face image: {image_filename}")
                        print(f"📸 Snapshot URL: {snapshot_url[:80]}...")
                        break
                    else:
                        print(f"⚠️ Failed to get download URL (attempt {attempt + 1}): {download_response.status_code}")
                        if attempt == max_retries - 1:
                            # Use fallback S3 path format
                            snapshot_url = f"s3://faces-raw/{image_filename.split('/')[-1]}"
                            print(f"🔄 Using fallback URL: {snapshot_url}")
                            break
                else:
                    print(f"❌ Failed to upload image (attempt {attempt + 1}): {upload_result.status_code}")
            else:
                print(f"❌ Failed to get upload URL (attempt {attempt + 1}): {upload_response.status_code}")
                
        except Exception as e:
            print(f"💥 Upload error (attempt {attempt + 1}): {e}")
        
        if attempt < max_retries - 1:
            print(f"🔄 Retrying upload in 2 seconds...")
            await asyncio.sleep(2)
    
    # Create event with improved coordinates
    face_bbox = [face_margin, face_margin, face_size, face_size]  # x, y, w, h matching the drawn face
    
    evt = FaceDetectedEvent(
        tenant_id=TENANT_ID,
        site_id=int(SITE_ID),
        camera_id=int(CAMERA_ID.split('-')[1]) if CAMERA_ID.startswith('c-') else int(CAMERA_ID),
        timestamp=datetime.now(timezone.utc),
        embedding=[np.random.random() for _ in range(512)],  # Random but realistic embedding
        bbox=face_bbox,  # Coordinates matching the actual face in the image
        snapshot_url=snapshot_url,
    )
    
    # Send the face detection event
    try:
        r = await client.post(
            f"{API_URL}/v1/events/face",
            json=evt.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        print(f"📤 POST /v1/events/face => {r.status_code}")
        if r.status_code == 200:
            response_data = r.json()
            print(f"✅ Event processed: person_id={response_data.get('person_id')}, match={response_data.get('match')}")
            if response_data.get('visit_id'):
                print(f"🎯 Visit created: {response_data.get('visit_id')}")
        else:
            print(f"❌ Event processing failed: {r.text}")
            
    except Exception as e:
        print(f"💥 Error sending event: {e}")
    
    print(f"🖼️ Image upload success: {'✅' if snapshot_url else '❌'}")
    print(f"📊 Final snapshot_url: {snapshot_url or 'None - will use API fallback'}")
    print("─" * 60)


import asyncio
import cv2
import logging
import signal
import sys
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
        site_id_str = os.getenv("SITE_ID", "1")
        # Handle both prefixed (s-1) and plain (1) formats
        self.site_id = int(site_id_str.split('-')[1]) if site_id_str.startswith('s-') else int(site_id_str)
        # camera_id is now assigned by backend, not from env
        self.camera_id = None  # Will be set by WorkerClient after registration
        self.worker_api_key = os.getenv("WORKER_API_KEY", "dev-secret")
        
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
        if not self.worker_api_key or self.worker_api_key == "dev-secret":
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


# Import FaceDetectedEvent from common instead of defining it locally


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
        
        # Shared shutdown flag
        self._shutdown_requested = False
        
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
        
        # Start shutdown monitor task
        self.shutdown_monitor_task = asyncio.create_task(self._monitor_shutdown())
        
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
        
        # Cancel shutdown monitor
        if hasattr(self, 'shutdown_monitor_task') and self.shutdown_monitor_task and not self.shutdown_monitor_task.done():
            self.shutdown_monitor_task.cancel()
            try:
                await self.shutdown_monitor_task
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
    
    async def _upload_face_image(self, face_image: np.ndarray, max_retries: int = 3) -> Optional[str]:
        """Upload face image to MinIO and return the snapshot URL with improved retry logic"""
        for attempt in range(max_retries):
            try:
                import cv2
                import uuid
                
                # Generate unique filename
                image_filename = f"faces-raw/face-{uuid.uuid4().hex[:8]}.jpg"
                
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
                
                # Get presigned upload URL with timeout
                upload_response = await self.http_client.post(
                    f"{self.config.api_url}/v1/files/upload-url",
                    json={"filename": image_filename, "content_type": "image/jpeg"},
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    timeout=15,  # Increased timeout
                )
                
                if upload_response.status_code != 200:
                    logger.warning(f"Failed to get upload URL (attempt {attempt + 1}/{max_retries}): {upload_response.status_code}")
                    if upload_response.status_code >= 500 and attempt < max_retries - 1:
                        await asyncio.sleep(1.0 * (attempt + 1))  # Server error, retry
                        continue
                    return None
                
                upload_data = upload_response.json()
                presigned_url = upload_data["upload_url"]
                
                # Upload the image with retry on network issues
                upload_result = await self.http_client.put(
                    presigned_url,
                    content=img_bytes,
                    headers={"Content-Type": "image/jpeg"},
                    timeout=30,  # Long timeout for upload
                )
                
                if upload_result.status_code not in [200, 204]:
                    logger.warning(f"Failed to upload image (attempt {attempt + 1}/{max_retries}): {upload_result.status_code}")
                    if upload_result.status_code >= 500 and attempt < max_retries - 1:
                        await asyncio.sleep(1.0 * (attempt + 1))  # Server error, retry
                        continue
                    return None
                
                # Instead of using presigned URLs with credentials, return secure internal path
                # This will be served through the API's secure /files/{file_path} endpoint
                secure_path = f"worker-faces/{image_filename.split('/')[-1]}"
                logger.debug(f"Successfully uploaded face image: {image_filename} -> {secure_path} (attempt {attempt + 1})")
                return secure_path
                
            except httpx.TimeoutException as e:
                logger.warning(f"Upload timeout (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
            except httpx.RequestError as e:
                logger.warning(f"Upload request error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
            except Exception as e:
                logger.error(f"Unexpected upload error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
        
        logger.error(f"Failed to upload face image after {max_retries} attempts")
        return None
    
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
                        os._exit(0)
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                logger.info("Shutdown monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in shutdown monitor: {e}")
                await asyncio.sleep(check_interval)

    async def _send_stop_signal_to_backend(self):
        """Send stop signal to backend with 3 retry attempts, wait for acknowledgment"""
        max_retries = 3
        timeout = 1.0  # 1 second timeout for each request as requested
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🚪 Sending stop signal to backend (attempt {attempt + 1}/{max_retries})")
                
                # Ensure we have authentication
                await self._ensure_authenticated()
                
                # Send the stop signal
                response = await self.http_client.post(
                    f"{self.config.api_url}/v1/workers/{self.worker_client.worker_id}/stop-signal",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json={
                        "worker_id": self.worker_client.worker_id,
                        "reason": "shutdown_requested",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    timeout=timeout
                )
                response.raise_for_status()
                
                # Parse response to check backend cleanup status
                response_data = response.json()
                backend_cleanup_completed = response_data.get("backend_cleanup_completed", False)
                camera_released = response_data.get("camera_released", False)
                
                logger.info(f"✅ Successfully sent stop signal to backend (attempt {attempt + 1})")
                logger.info(f"📄 Backend response: {response_data.get('message', 'No message')}")
                
                if backend_cleanup_completed:
                    logger.info("🎉 Backend confirmed cleanup completed - safe to shutdown")
                    if camera_released:
                        released_camera = response_data.get("released_camera_id")
                        logger.info(f"🔓 Backend released camera {released_camera}")
                else:
                    logger.info("⚠️  Backend cleanup status unknown - proceeding with shutdown")
                
                return True
                
            except asyncio.TimeoutError:
                logger.warning(f"⏱️  Timeout sending stop signal (attempt {attempt + 1}/{max_retries})")
            except httpx.TimeoutException:
                logger.warning(f"⏱️  Request timeout sending stop signal (attempt {attempt + 1}/{max_retries})")  
            except Exception as e:
                logger.warning(f"❌ Error sending stop signal (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Don't wait after the last attempt
            if attempt < max_retries - 1:
                await asyncio.sleep(0.1)  # Brief delay before retry
        
        logger.error(f"💥 Failed to send stop signal to backend after {max_retries} attempts - proceeding with local cleanup")
        return False
    
    def should_shutdown(self) -> bool:
        """Check if worker should shutdown"""
        return self._shutdown_requested or self.worker_client.should_shutdown()
    
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
                
                # Get assigned camera ID from worker client
                assigned_camera_id = self.worker_client.get_assigned_camera()
                if not assigned_camera_id:
                    logger.warning("No camera assigned to worker, skipping face processing")
                    continue
                
                # Upload face image and get snapshot URL
                await self._ensure_authenticated()  # Ensure we have auth for upload
                snapshot_url = await self._upload_face_image(face_image)

                # Create event with snapshot URL
                event = FaceDetectedEvent(
                    tenant_id=self.config.tenant_id,
                    site_id=self.config.site_id,
                    camera_id=assigned_camera_id,
                    timestamp=datetime.now(timezone.utc),
                    embedding=embedding,
                    bbox=bbox,
                    snapshot_url=snapshot_url,  # Now includes the actual image URL
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
    
    async def _wait_for_camera_assignment(self, timeout: int = 60) -> bool:
        """Wait for camera assignment from backend"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.worker_client.get_assigned_camera():
                return True
            
            logger.info("Waiting for camera assignment from backend...")
            await self.worker_client.request_camera_assignment()
            await asyncio.sleep(5)
        
        return False
    
    async def run_camera_capture(self):
        """Run continuous camera capture and processing"""
        cap = None
        reconnect_attempts = 0
        max_reconnect_attempts = self.config.max_camera_reconnect_attempts
        
        # Wait for camera assignment before starting
        logger.info("Waiting for camera assignment from backend...")
        if not await self._wait_for_camera_assignment():
            logger.error("No camera assignment received, cannot start processing")
            return
        
        assigned_camera_id = self.worker_client.get_assigned_camera()
        logger.info(f"Camera {assigned_camera_id} assigned, starting capture...")
        
        try:
            while True:
                    # Check for shutdown signal at the outer loop level too
                if self.should_shutdown():
                    logger.info("Shutdown signal received, exiting main camera loop")
                    break
                    
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
                    
                    # Report ready to process
                    await self.worker_client.report_idle()
                    
                    # Main processing loop
                    frame_count = 0
                    while True:
                        # Check for shutdown signal every few frames
                        if frame_count % 10 == 0 or self.should_shutdown():
                            if self.should_shutdown():
                                logger.info("Shutdown signal received, stopping camera capture")
                                break
                        
                        ret, frame = cap.read()
                        if not ret:
                            logger.warning("Failed to read frame, attempting reconnection")
                            break  # Break to outer loop for reconnection
                        
                        current_time = time.time()
                        frame_count += 1
                        
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
            
            # Handle graceful shutdown
            if self.should_shutdown():
                logger.info("Completing graceful shutdown...")
                self._shutdown_requested = True
                await self.worker_client.complete_shutdown()
    
    async def run_simulation(self):
        """Run simulation mode for testing"""
        logger.info("Running in simulation mode")
        
        cycle_count = 0
        while True:
            try:
                # Check for shutdown signal every few cycles
                cycle_count += 1
                if cycle_count % 5 == 0 or self.should_shutdown():
                    if self.should_shutdown():
                        logger.info("Shutdown signal received, stopping simulation")
                        break
                
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
    
    # Check if we should use enhanced worker (default: yes)
    use_enhanced_worker = os.getenv("USE_ENHANCED_WORKER", "true").lower() == "true"
    
    if use_enhanced_worker:
        # Use the enhanced worker with streaming
        from .enhanced_worker_with_streaming import run_enhanced_worker
        logger.info("Starting enhanced worker with streaming capabilities")
        await run_enhanced_worker()
        return
    
    # Fallback to basic worker
    worker = FaceRecognitionWorker(config)
    
    # Set up signal handlers for graceful shutdown with force-exit timeout
    shutdown_start_time = None
    
    def signal_handler(signum, frame):
        nonlocal shutdown_start_time
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        
        if shutdown_start_time is None:
            shutdown_start_time = asyncio.get_event_loop().time()
            worker._shutdown_requested = True
            
            # Create a task to send stop signal to backend immediately
            asyncio.create_task(worker._send_stop_signal_to_backend())
        else:
            # Second signal - force exit immediately
            elapsed = asyncio.get_event_loop().time() - shutdown_start_time
            logger.warning(f"Second signal received after {elapsed:.1f}s - forcing immediate exit")
            os._exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await worker.initialize()
        
        # Main execution loop with shutdown checking
        if config.mock_mode:
            await worker.run_simulation()
        else:
            await worker.run_camera_capture()
            
        # Check if shutdown was requested and complete it
        if worker.should_shutdown():
            logger.info("Completing graceful shutdown...")
            await worker.worker_client.complete_shutdown()
    
    except Exception as e:
        logger.error(f"Worker error: {e}")
        
    finally:
        # Add timeout for shutdown to prevent hanging
        try:
            logger.info("Starting worker shutdown with 10-second timeout...")
            await asyncio.wait_for(worker.shutdown(), timeout=10.0)
            logger.info("Worker shutdown completed successfully")
        except asyncio.TimeoutError:
            logger.error("Worker shutdown timeout - forcing exit")
            os._exit(1)
        except Exception as e:
            logger.error(f"Error during worker shutdown: {e}")
            os._exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt - exiting")
        os._exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
        os._exit(1)

