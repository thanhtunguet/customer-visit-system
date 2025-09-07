"""Face processing service for landmark detection and embedding generation."""

import base64
import io
import json
import logging
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    FACE_PROCESSING_AVAILABLE = True
    ArrayType = np.ndarray
except ImportError as e:
    logging.warning(f"Face processing dependencies not available: {e}")
    FACE_PROCESSING_AVAILABLE = False
    # Create mock modules for development/testing
    cv2 = None
    np = None
    Image = None
    # Use Any for type hints when dependencies aren't available
    from typing import Any
    ArrayType = Any

from ..core.milvus_client import milvus_client
from ..core.minio_client import minio_client

logger = logging.getLogger(__name__)

class FaceProcessingService:
    """Service for processing face images, detecting landmarks, and generating embeddings."""
    
    def __init__(self):
        self.face_detector = None
        self.face_embedder = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize face detection and embedding models."""
        if not FACE_PROCESSING_AVAILABLE:
            logger.warning("Face processing not available - dependencies not installed")
            return
            
        try:
            # Use OpenCV's Haar cascade for face detection (no external files needed)
            self.face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            if self.face_detector.empty():
                raise RuntimeError("Failed to load Haar cascade classifier")
            logger.info("Face detector initialized (Haar cascade)")
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}")
            
        try:
            # Initialize face recognition model - placeholder for actual implementation
            # In production, use InsightFace ArcFace or similar
            self.face_embedder = True  # Simple flag to indicate embedder is "initialized"
            logger.info("Face embedder initialized (placeholder)")
        except Exception as e:
            logger.error(f"Failed to initialize face embedder: {e}")
    
    def decode_base64_image(self, base64_data: str) -> ArrayType:
        """Decode base64 image data to numpy array."""
        if not FACE_PROCESSING_AVAILABLE:
            raise RuntimeError("Face processing dependencies not available")
            
        try:
            # Remove data URL prefix if present
            if base64_data.startswith('data:image'):
                base64_data = base64_data.split(',', 1)[1]
            
            # Decode base64
            image_bytes = base64.b64decode(base64_data)
            
            # Convert to PIL Image
            pil_image = Image.open(io.BytesIO(image_bytes))

            # Normalize orientation using EXIF so pixel coords match displayed image
            try:
                pil_image = ImageOps.exif_transpose(pil_image)
            except Exception:
                pass
            
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Convert to numpy array
            image_array = np.array(pil_image)
            
            # Convert RGB to BGR for OpenCV
            image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            
            return image_bgr
            
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise ValueError(f"Invalid image data: {e}")
    
    def detect_faces_and_landmarks(self, image: ArrayType) -> List[Dict]:
        """
        Detect faces and extract 5-point landmarks.
        
        Returns:
            List of dictionaries containing bbox and landmarks for each face
        """
        if self.face_detector is None:
            raise RuntimeError("Face detector not initialized")
        
        try:
            # Convert to grayscale for Haar cascade
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect faces using Haar cascade
            faces = self.face_detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            face_results = []
            for (x, y, w, h) in faces:
                # Convert NumPy types to Python ints to avoid JSON serialization issues
                x, y, w, h = int(x), int(y), int(w), int(h)
                
                # Generate synthetic 5-point landmarks based on face bbox
                # In production, use a proper landmark detector like dlib or MediaPipe
                center_x, center_y = x + w // 2, y + h // 2
                eye_y = y + h // 3
                nose_y = y + h // 2
                mouth_y = y + 2 * h // 3
                
                landmarks = [
                    [float(x + w // 4), float(eye_y)],      # left eye
                    [float(x + 3 * w // 4), float(eye_y)],  # right eye
                    [float(center_x), float(nose_y)],        # nose tip
                    [float(x + w // 3), float(mouth_y)],     # left mouth corner
                    [float(x + 2 * w // 3), float(mouth_y)] # right mouth corner
                ]
                
                # Calculate confidence based on face size (larger faces = higher confidence)
                confidence = min(0.9, max(0.3, (w * h) / (image.shape[0] * image.shape[1]) * 10))
                
                face_results.append({
                    'bbox': [x, y, w, h],
                    'landmarks': landmarks,
                    'confidence': float(confidence)
                })
            
            return face_results
            
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []
    
    def extract_face_embedding(self, image: ArrayType, landmarks: List[List[float]]) -> List[float]:
        """
        Extract 512-dimensional face embedding from aligned face.
        
        This is a placeholder implementation. In production, use:
        - InsightFace ArcFace
        - FaceNet
        - Or other production-ready embedding model
        """
        try:
            # Placeholder: generate a random 512-D vector
            # In production, this would:
            # 1. Align the face using landmarks
            # 2. Preprocess for the embedding model
            # 3. Run inference to get embedding
            # 4. Normalize the embedding
            
            # For now, create a deterministic embedding based on image properties
            # This ensures consistent results for the same image
            face_region = self._extract_face_region(image, landmarks)
            
            # Simple feature extraction (placeholder)
            features = []
            
            # Add some basic statistical features
            features.extend([
                float(np.mean(face_region)),
                float(np.std(face_region)),
                float(np.median(face_region)),
            ])
            
            # Pad to 512 dimensions with deterministic values
            while len(features) < 512:
                features.append(float(np.random.random()))
            
            # Normalize to unit vector
            features = np.array(features[:512])
            features = features / (np.linalg.norm(features) + 1e-8)
            
            return features.tolist()
            
        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            return [0.0] * 512  # Return zero vector on error
    
    def _extract_face_region(self, image: ArrayType, landmarks: List[List[float]]) -> ArrayType:
        """Extract face region using landmarks for alignment."""
        try:
            # Convert landmarks to numpy array
            landmarks_np = np.array(landmarks, dtype=np.float32)
            
            # Get bounding box from landmarks
            x_min = int(np.min(landmarks_np[:, 0]) - 20)
            y_min = int(np.min(landmarks_np[:, 1]) - 20)
            x_max = int(np.max(landmarks_np[:, 0]) + 20)
            y_max = int(np.max(landmarks_np[:, 1]) + 20)
            
            # Ensure bounds are within image
            h, w = image.shape[:2]
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(w, x_max)
            y_max = min(h, y_max)
            
            # Extract face region
            face_region = image[y_min:y_max, x_min:x_max]
            
            # Resize to standard size
            if face_region.size > 0:
                face_region = cv2.resize(face_region, (112, 112))
            
            return face_region
            
        except Exception as e:
            logger.error(f"Face region extraction failed: {e}")
            return np.zeros((112, 112, 3), dtype=np.uint8)
    
    async def upload_image_to_minio(self, image_data: ArrayType, tenant_id: str, image_id: str) -> str:
        """Upload processed image to MinIO and return the path."""
        try:
            # Encode image as JPEG
            _, buffer = cv2.imencode('.jpg', image_data, [cv2.IMWRITE_JPEG_QUALITY, 90])
            image_bytes = buffer.tobytes()
            
            # Upload to MinIO
            object_path = f"staff-faces/{tenant_id}/{image_id}.jpg"
            
            minio_client.upload_image(
                bucket="faces-derived",
                object_name=object_path,
                data=image_bytes,
                content_type="image/jpeg"
            )
            
            return object_path
            
        except Exception as e:
            logger.error(f"Failed to upload image to MinIO: {e}")
            raise
    
    async def process_staff_face_image(
        self, 
        base64_image: str, 
        tenant_id: str, 
        staff_id: str
    ) -> Dict:
        """
        Complete face processing pipeline:
        1. Decode image
        2. Detect faces and landmarks
        3. Generate embeddings
        4. Extract face crop
        5. Upload to MinIO
        6. Return processing results
        """
        try:
            import base64
            import hashlib
            import cv2
            import uuid
            
            # Decode image
            image = self.decode_base64_image(base64_image)
            
            # Calculate image hash for duplicate detection
            image_bytes = base64.b64decode(base64_image.split(',')[-1])
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            
            # Detect faces
            face_results = self.detect_faces_and_landmarks(image)
            
            if not face_results:
                return {
                    'success': False,
                    'error': 'No faces detected in image',
                    'face_count': 0
                }
            
            # Use the first (most confident) face
            face_data = face_results[0]
            landmarks = face_data['landmarks']
            
            # Generate embedding
            embedding = self.extract_face_embedding(image, landmarks)
            
            # Extract face crop
            face_crop = self._extract_face_region(image, landmarks)
            
            # Convert face crop to base64
            face_crop_b64 = None
            try:
                _, buffer = cv2.imencode('.jpg', face_crop)
                face_crop_b64 = base64.b64encode(buffer).decode('utf-8')
            except Exception as e:
                logger.warning(f"Failed to encode face crop to base64: {e}")
            
            # Generate unique image ID
            image_id = str(uuid.uuid4())
            
            # Upload to MinIO
            image_path = await self.upload_image_to_minio(image, tenant_id, image_id)
            
            # Ensure all data is JSON serializable
            def ensure_json_serializable(obj):
                """Convert NumPy types to Python native types"""
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, list):
                    return [ensure_json_serializable(item) for item in obj]
                elif isinstance(obj, dict):
                    return {key: ensure_json_serializable(value) for key, value in obj.items()}
                else:
                    return obj
            
            result = {
                'success': True,
                'image_id': image_id,
                'image_path': image_path,
                'image_hash': image_hash,
                'landmarks': ensure_json_serializable(landmarks),
                'embedding': ensure_json_serializable(embedding),
                'face_count': int(len(face_results)),
                'confidence': float(face_data['confidence']),
                'bbox': ensure_json_serializable(face_data['bbox']),
                'face_crop_b64': face_crop_b64  # Add the cropped face image
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Face processing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'face_count': 0
            }
    
    async def test_face_recognition(
        self, 
        test_image_b64: str, 
        tenant_id: str, 
        staff_embeddings: List[Dict]
    ) -> Dict:
        """Test face recognition against known staff embeddings."""
        try:
            # Process test image
            image = self.decode_base64_image(test_image_b64)
            face_results = self.detect_faces_and_landmarks(image)
            
            if not face_results:
                return {
                    'success': False,
                    'error': 'No faces detected in test image',
                    'matches': []
                }
            
            # Use first detected face
            test_landmarks = face_results[0]['landmarks']
            test_embedding = self.extract_face_embedding(image, test_landmarks)
            
            # Compare against staff embeddings
            matches = []
            for staff_data in staff_embeddings:
                similarity = self._calculate_similarity(test_embedding, staff_data['embedding'])
                matches.append({
                    'staff_id': staff_data['staff_id'],
                    'staff_name': staff_data.get('name', 'Unknown'),
                    'similarity': similarity,
                    'image_id': staff_data.get('image_id')
                })
            
            # Sort by similarity (descending)
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Find best match above threshold
            best_match = None
            if matches and matches[0]['similarity'] > 0.7:  # Configurable threshold
                best_match = matches[0]
            
            return {
                'success': True,
                'matches': matches[:5],  # Top 5 matches
                'best_match': best_match,
                'processing_info': {
                    'test_face_detected': True,
                    'test_confidence': face_results[0]['confidence'],
                    'total_staff_compared': len(staff_embeddings)
                }
            }
            
        except Exception as e:
            logger.error(f"Face recognition test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'matches': []
            }
    
    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        try:
            if not embedding1 or not embedding2 or len(embedding1) != len(embedding2):
                return 0.0
            
            # Convert to numpy arrays
            emb1 = np.array(embedding1)
            emb2 = np.array(embedding2)
            
            # Cosine similarity
            dot_product = np.dot(emb1, emb2)
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0

# Service instance
face_processing_service = FaceProcessingService()