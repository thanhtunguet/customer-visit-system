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


class FaceDetectedEvent(BaseModel):
    tenant_id: str
    site_id: str
    camera_id: str
    timestamp: datetime
    embedding: list[float]
    bbox: list[float]
    snapshot_url: Optional[str] = None
    is_staff_local: bool = False


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
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import numpy as np
from pydantic import BaseModel

from .detectors import create_detector, FaceDetector
from .embedder import create_embedder, FaceEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment
API_URL = os.getenv("API_URL", "http://localhost:8080")
TENANT_ID = os.getenv("TENANT_ID", "t-dev")
SITE_ID = os.getenv("SITE_ID", "s-1")
CAMERA_ID = os.getenv("CAMERA_ID", "c-1")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "dev-api-key")

# Worker configuration
DETECTOR_TYPE = os.getenv("DETECTOR_TYPE", "yunet")  # yunet, mock
EMBEDDER_TYPE = os.getenv("EMBEDDER_TYPE", "insightface")  # insightface, mock
WORKER_FPS = int(os.getenv("WORKER_FPS", "5"))
RTSP_URL = os.getenv("RTSP_URL", "")
USB_CAMERA = int(os.getenv("USB_CAMERA", "0"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"


class FaceDetectedEvent(BaseModel):
    tenant_id: str
    site_id: str
    camera_id: str
    timestamp: datetime
    embedding: List[float]
    bbox: List[float]
    snapshot_url: Optional[str] = None
    is_staff_local: bool = False


class FaceRecognitionWorker:
    def __init__(self):
        self.detector: FaceDetector = create_detector(DETECTOR_TYPE)
        self.embedder: FaceEmbedder = create_embedder(EMBEDDER_TYPE)
        self.staff_embeddings: Dict[str, List[float]] = {}
        self.http_client: Optional[httpx.AsyncClient] = None
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0
    
    async def initialize(self):
        """Initialize the worker"""
        self.http_client = httpx.AsyncClient(timeout=10.0)
        await self._authenticate()
        await self._load_staff_embeddings()
        logger.info("Worker initialized successfully")
    
    async def shutdown(self):
        """Cleanup resources"""
        if self.http_client:
            await self.http_client.aclose()
    
    async def _authenticate(self):
        """Get JWT token for API access"""
        try:
            response = await self.http_client.post(
                f"{API_URL}/v1/auth/token",
                json={
                    "grant_type": "api_key",
                    "api_key": WORKER_API_KEY,
                    "tenant_id": TENANT_ID,
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
            
            response = await self.http_client.get(
                f"{API_URL}/v1/staff",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            if response.status_code == 200:
                staff_members = response.json()
                self.staff_embeddings = {
                    member["staff_id"]: member.get("face_embedding", [])
                    for member in staff_members
                    if member.get("face_embedding")
                }
                logger.info(f"Loaded {len(self.staff_embeddings)} staff embeddings")
            
        except Exception as e:
            logger.warning(f"Failed to load staff embeddings: {e}")
    
    def _is_staff_match(self, embedding: List[float], threshold: float = 0.8) -> bool:
        """Check if embedding matches any known staff member"""
        if not self.staff_embeddings:
            return False
        
        embedding_np = np.array(embedding)
        
        for staff_id, staff_embedding in self.staff_embeddings.items():
            if not staff_embedding:
                continue
            
            staff_np = np.array(staff_embedding)
            
            # Cosine similarity
            similarity = np.dot(embedding_np, staff_np) / (
                np.linalg.norm(embedding_np) * np.linalg.norm(staff_np)
            )
            
            if similarity >= threshold:
                logger.info(f"Matched staff member {staff_id} with similarity {similarity}")
                return True
        
        return False
    
    async def _send_face_event(self, event: FaceDetectedEvent) -> Dict:
        """Send face event to API"""
        try:
            await self._ensure_authenticated()
            
            response = await self.http_client.post(
                f"{API_URL}/v1/events/face",
                json=event.model_dump(mode="json"),
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Face event processed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to send face event: {e}")
            # In production, we'd queue this for retry
            return {"error": str(e)}
    
    async def process_frame(self, frame: np.ndarray) -> int:
        """Process a single frame and detect faces"""
        faces_processed = 0
        
        try:
            # Detect faces
            detections = self.detector.detect(frame)
            
            for detection in detections:
                if detection["confidence"] < CONFIDENCE_THRESHOLD:
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
                is_staff_local = self._is_staff_match(embedding)
                
                # Create event
                event = FaceDetectedEvent(
                    tenant_id=TENANT_ID,
                    site_id=SITE_ID,
                    camera_id=CAMERA_ID,
                    timestamp=datetime.now(timezone.utc),
                    embedding=embedding,
                    bbox=bbox,
                    is_staff_local=is_staff_local,
                )
                
                # Send to API
                await self._send_face_event(event)
                faces_processed += 1
        
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
        
        return faces_processed
    
    async def run_camera_capture(self):
        """Run continuous camera capture and processing"""
        cap = None
        
        try:
            # Initialize camera
            if RTSP_URL:
                cap = cv2.VideoCapture(RTSP_URL)
                logger.info(f"Opening RTSP stream: {RTSP_URL}")
            else:
                cap = cv2.VideoCapture(USB_CAMERA)
                logger.info(f"Opening USB camera: {USB_CAMERA}")
            
            if not cap.isOpened():
                raise RuntimeError("Failed to open camera")
            
            # Set camera properties
            cap.set(cv2.CAP_PROP_FPS, WORKER_FPS)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            frame_delay = 1.0 / WORKER_FPS
            last_process_time = 0
            
            logger.info(f"Starting camera processing at {WORKER_FPS} FPS")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame")
                    await asyncio.sleep(0.1)
                    continue
                
                current_time = time.time()
                if current_time - last_process_time >= frame_delay:
                    faces_count = await self.process_frame(frame)
                    if faces_count > 0:
                        logger.info(f"Processed {faces_count} faces")
                    last_process_time = current_time
                
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop
        
        except KeyboardInterrupt:
            logger.info("Stopping camera capture")
        except Exception as e:
            logger.error(f"Camera capture error: {e}")
        finally:
            if cap:
                cap.release()
    
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
                
                await asyncio.sleep(1.0 / WORKER_FPS)
                
            except KeyboardInterrupt:
                logger.info("Stopping simulation")
                break
            except Exception as e:
                logger.error(f"Simulation error: {e}")
                await asyncio.sleep(1)


async def main():
    """Main worker function"""
    worker = FaceRecognitionWorker()
    
    try:
        await worker.initialize()
        
        if MOCK_MODE:
            await worker.run_simulation()
        else:
            await worker.run_camera_capture()
    
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

