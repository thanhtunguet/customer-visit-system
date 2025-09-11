"""Face processing service for landmark detection and embedding generation."""

import base64
import io
import logging
from typing import Dict, List

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
            self.face_detector = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            if self.face_detector.empty():
                raise RuntimeError("Failed to load Haar cascade classifier")
            logger.info("Face detector initialized (Haar cascade)")
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}")

        try:
            # Initialize face recognition model - placeholder for actual implementation
            # In production, use InsightFace ArcFace or similar
            self.face_embedder = (
                True  # Simple flag to indicate embedder is "initialized"
            )
            logger.info("Face embedder initialized (placeholder)")
        except Exception as e:
            logger.error(f"Failed to initialize face embedder: {e}")

    def decode_base64_image(self, base64_data: str) -> ArrayType:
        """Decode base64 image data to numpy array."""
        if not FACE_PROCESSING_AVAILABLE:
            raise RuntimeError("Face processing dependencies not available")

        try:
            # Remove data URL prefix if present
            if base64_data.startswith("data:image"):
                base64_data = base64_data.split(",", 1)[1]

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
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

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
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            face_results = []
            for x, y, w, h in faces:
                # Convert NumPy types to Python ints to avoid JSON serialization issues
                x, y, w, h = int(x), int(y), int(w), int(h)

                # Generate synthetic 5-point landmarks based on face bbox
                # In production, use a proper landmark detector like dlib or MediaPipe
                center_x, _center_y = x + w // 2, y + h // 2
                eye_y = y + h // 3
                nose_y = y + h // 2
                mouth_y = y + 2 * h // 3

                landmarks = [
                    [float(x + w // 4), float(eye_y)],  # left eye
                    [float(x + 3 * w // 4), float(eye_y)],  # right eye
                    [float(center_x), float(nose_y)],  # nose tip
                    [float(x + w // 3), float(mouth_y)],  # left mouth corner
                    [float(x + 2 * w // 3), float(mouth_y)],  # right mouth corner
                ]

                # Calculate confidence based on face size (larger faces = higher confidence)
                confidence = min(
                    0.9, max(0.3, (w * h) / (image.shape[0] * image.shape[1]) * 10)
                )

                face_results.append(
                    {
                        "bbox": [x, y, w, h],
                        "landmarks": landmarks,
                        "confidence": float(confidence),
                    }
                )

            return face_results

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []

    def extract_face_embedding(
        self, image: ArrayType, landmarks: List[List[float]]
    ) -> List[float]:
        """
        Extract a more sophisticated 512D embedding from an aligned face region.

        Enhanced to capture better facial features for improved recognition accuracy.
        """
        try:
            face_region = self._extract_face_region(image, landmarks)

            # Convert to grayscale for analysis
            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)

            # Resize to standard size for consistent features
            standard_size = cv2.resize(gray, (112, 112))

            # Enhanced feature extraction combining multiple approaches
            features = []

            # 1. Multi-scale LBP features (128 dims)
            try:
                from skimage import feature

                lbp = feature.local_binary_pattern(
                    standard_size, P=8, R=1, method="uniform"
                )
                lbp_hist, _ = np.histogram(lbp.ravel(), bins=64, range=(0, 64))
                features.extend(lbp_hist.astype(np.float32))
            except ImportError:
                # Fallback: Simple gradient features
                sobelx = cv2.Sobel(standard_size, cv2.CV_64F, 1, 0, ksize=3)
                sobely = cv2.Sobel(standard_size, cv2.CV_64F, 0, 1, ksize=3)
                gradient_mag = np.sqrt(sobelx**2 + sobely**2)
                grad_hist, _ = np.histogram(gradient_mag.ravel(), bins=64)
                features.extend(grad_hist.astype(np.float32))

            # 2. DCT coefficients from different regions (128 dims)
            dct_full = cv2.dct(standard_size.astype(np.float32))
            # Extract low-frequency coefficients
            dct_features = dct_full[:16, :8].flatten()  # Top-left 128 coefficients
            features.extend(dct_features.astype(np.float32))

            # 3. Regional histogram features (96 dims)
            h, w = standard_size.shape
            regions = [
                standard_size[: h // 2, : w // 2],  # Top-left (eyes region)
                standard_size[: h // 2, w // 2 :],  # Top-right (eyes region)
                standard_size[
                    h // 3 : 2 * h // 3, w // 4 : 3 * w // 4
                ],  # Center (nose region)
                standard_size[
                    2 * h // 3 :, w // 4 : 3 * w // 4
                ],  # Bottom (mouth region)
            ]

            for region in regions:
                if region.size > 0:
                    hist, _ = np.histogram(region.ravel(), bins=24, range=(0, 256))
                    features.extend(hist.astype(np.float32))
                else:
                    features.extend(np.zeros(24, dtype=np.float32))

            # 4. Landmark-based geometric features (32 dims)
            if len(landmarks) >= 5:
                # Eye distance
                eye_dist = np.linalg.norm(
                    np.array(landmarks[1]) - np.array(landmarks[0])
                )

                # Face proportions
                face_width = max(landmark[0] for landmark in landmarks) - min(landmark[0] for landmark in landmarks)
                face_height = max(landmark[1] for landmark in landmarks) - min(
                    landmark[1] for landmark in landmarks
                )
                aspect_ratio = face_width / (face_height + 1e-6)

                # Angles and distances between key points
                geom_features = [
                    eye_dist,
                    face_width,
                    face_height,
                    aspect_ratio,
                    # Distances from nose to eyes and mouth
                    np.linalg.norm(np.array(landmarks[2]) - np.array(landmarks[0])),
                    np.linalg.norm(np.array(landmarks[2]) - np.array(landmarks[1])),
                    np.linalg.norm(np.array(landmarks[2]) - np.array(landmarks[3])),
                    np.linalg.norm(np.array(landmarks[2]) - np.array(landmarks[4])),
                ]

                # Pad to 32 dimensions with derived features
                while len(geom_features) < 32:
                    geom_features.append(geom_features[-1] * 0.1)  # Scaled derivatives

                features.extend(np.array(geom_features[:32], dtype=np.float32))
            else:
                features.extend(np.zeros(32, dtype=np.float32))

            # 5. Statistical features (32 dims)
            stats = [
                np.mean(standard_size),
                np.std(standard_size),
                np.median(standard_size),
                np.var(standard_size),
                np.percentile(standard_size, 25),
                np.percentile(standard_size, 75),
                np.min(standard_size),
                np.max(standard_size),
            ]

            # Add texture measures
            laplacian = cv2.Laplacian(standard_size, cv2.CV_64F)
            stats.extend(
                [
                    np.mean(laplacian),
                    np.std(laplacian),
                    np.mean(np.abs(laplacian)),
                    np.var(laplacian),
                ]
            )

            # Pad statistical features to 32
            while len(stats) < 32:
                stats.append(stats[-1] * 0.5)

            features.extend(np.array(stats[:32], dtype=np.float32))

            # 6. Gabor filter responses (96 dims)
            try:
                from skimage.filters import gabor

                gabor_responses = []

                # Multiple orientations and frequencies
                for angle in [0, 45, 90, 135]:
                    for freq in [0.1, 0.3, 0.5]:
                        try:
                            filtered, _ = gabor(
                                standard_size, frequency=freq, theta=np.deg2rad(angle)
                            )
                            response = np.mean(np.abs(filtered))
                            gabor_responses.append(response)
                        except Exception:
                            gabor_responses.append(0.0)

                # Pad to 96 dimensions
                while len(gabor_responses) < 96:
                    gabor_responses.extend(
                        gabor_responses[: min(12, len(gabor_responses))]
                    )

                features.extend(np.array(gabor_responses[:96], dtype=np.float32))

            except ImportError:
                # Fallback: More DCT coefficients
                dct_fallback = dct_full[8:16, :12].flatten()  # Different DCT region
                features.extend(dct_fallback.astype(np.float32))

                # Pad with texture analysis
                for i in range(0, min(112, standard_size.shape[0]), 14):
                    for j in range(0, min(112, standard_size.shape[1]), 14):
                        patch = standard_size[i : i + 14, j : j + 14]
                        if patch.size > 0:
                            features.append(np.std(patch))
                        if len(features) >= 416:  # 320 + 96 total so far
                            break
                    if len(features) >= 416:
                        break

                # Pad to complete 96 dimensions for this section
                while len(features) < 416:
                    features.append(0.0)

            # Ensure exactly 512 dimensions
            features = np.array(features, dtype=np.float32)
            if len(features) > 512:
                features = features[:512]
            elif len(features) < 512:
                # Pad with normalized noise based on existing features
                seed = int(np.sum(features) * 1000) % 10000
                rng = np.random.default_rng(seed)
                padding = rng.normal(0, 0.1, 512 - len(features)).astype(np.float32)
                features = np.concatenate([features, padding])

            # Normalize to unit vector
            norm = np.linalg.norm(features)
            if norm > 1e-12:
                features = features / norm
            else:
                # Fallback for zero vector
                features[0] = 1.0

            return features.tolist()

        except Exception as e:
            logger.error(f"Enhanced embedding extraction failed: {e}")
            # Deterministic fallback
            try:
                face_region = self._extract_face_region(image, landmarks)
                gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
                small = cv2.resize(gray, (32, 32))

                # Simple but deterministic features
                dct = cv2.dct(small.astype(np.float32))
                features = dct[:16, :16].flatten()

                # Pad to 512 with deterministic pattern
                seed = int(np.sum(features)) % 10000
                rng = np.random.default_rng(seed)
                full_features = np.zeros(512, dtype=np.float32)
                full_features[: len(features)] = features
                full_features[len(features) :] = rng.normal(0, 0.5, 512 - len(features))

                # Normalize
                norm = np.linalg.norm(full_features)
                if norm > 1e-12:
                    full_features = full_features / norm
                else:
                    full_features[0] = 1.0

                return full_features.tolist()

            except Exception as fallback_error:
                logger.error(f"Fallback embedding extraction failed: {fallback_error}")
                # Last resort: random but deterministic vector
                vec = np.zeros(512, dtype=np.float32)
                vec[0] = 1.0
                return vec.tolist()

    def _extract_face_region(
        self, image: ArrayType, landmarks: List[List[float]]
    ) -> ArrayType:
        """Extract face region using enhanced cropping algorithm."""
        try:
            from .face_cropper import api_face_cropper

            # Convert landmarks to face info format
            landmarks_np = np.array(landmarks, dtype=np.float32)

            # Get bounding box from landmarks with small padding
            x_min = int(np.min(landmarks_np[:, 0]) - 10)
            y_min = int(np.min(landmarks_np[:, 1]) - 10)
            x_max = int(np.max(landmarks_np[:, 0]) + 10)
            y_max = int(np.max(landmarks_np[:, 1]) + 10)

            # Ensure bounds are within image
            h, w = image.shape[:2]
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(w, x_max)
            y_max = min(h, y_max)

            # Create face info for enhanced cropping
            face_info = {
                "bbox": [x_min, y_min, x_max - x_min, y_max - y_min],
                "landmarks": landmarks,
                "confidence": 0.8,  # Default confidence for landmark-based detection
            }

            # Use enhanced cropping
            crop_result = api_face_cropper.crop_face(image, face_info, debug=False)

            if api_face_cropper.validate_crop_result(crop_result):
                return crop_result["cropped_face"]
            else:
                logger.warning("Enhanced cropping failed, using fallback")
                # Fallback to original simple crop
                face_region = image[y_min:y_max, x_min:x_max]
                if face_region.size > 0:
                    face_region = cv2.resize(face_region, (112, 112))
                    return face_region
                else:
                    return np.zeros((112, 112, 3), dtype=np.uint8)

        except Exception as e:
            logger.error(f"Enhanced face region extraction failed: {e}")
            # Fallback to original logic
            try:
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

            except Exception as fallback_error:
                logger.error(
                    f"Fallback face region extraction failed: {fallback_error}"
                )
                return np.zeros((112, 112, 3), dtype=np.uint8)

    async def upload_image_to_minio(
        self, image_data: ArrayType, tenant_id: str, image_id: str
    ) -> str:
        """Upload processed image to MinIO and return the path."""
        try:
            # Encode image as JPEG
            _, buffer = cv2.imencode(".jpg", image_data, [cv2.IMWRITE_JPEG_QUALITY, 90])
            image_bytes = buffer.tobytes()

            # Upload to MinIO
            object_path = f"staff-faces/{tenant_id}/{image_id}.jpg"

            minio_client.upload_image(
                bucket="faces-derived",
                object_name=object_path,
                data=image_bytes,
                content_type="image/jpeg",
            )

            return object_path

        except Exception as e:
            logger.error(f"Failed to upload image to MinIO: {e}")
            raise

    async def process_staff_face_image(
        self, base64_image: str, tenant_id: str, staff_id: str
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
            import uuid

            import cv2

            # Decode image
            image = self.decode_base64_image(base64_image)

            # Calculate image hash for duplicate detection
            image_bytes = base64.b64decode(base64_image.split(",")[-1])
            image_hash = hashlib.sha256(image_bytes).hexdigest()

            # Detect faces
            face_results = self.detect_faces_and_landmarks(image)

            if not face_results:
                return {
                    "success": False,
                    "error": "No faces detected in image",
                    "face_count": 0,
                }

            # Use the first (most confident) face
            face_data = face_results[0]
            landmarks = face_data["landmarks"]

            # Generate embedding
            embedding = self.extract_face_embedding(image, landmarks)

            # Extract face crop
            face_crop = self._extract_face_region(image, landmarks)

            # Convert face crop to base64
            face_crop_b64 = None
            try:
                _, buffer = cv2.imencode(".jpg", face_crop)
                face_crop_b64 = base64.b64encode(buffer).decode("utf-8")
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
                    return {
                        key: ensure_json_serializable(value)
                        for key, value in obj.items()
                    }
                else:
                    return obj

            result = {
                "success": True,
                "image_id": image_id,
                "image_path": image_path,
                "image_hash": image_hash,
                "landmarks": ensure_json_serializable(landmarks),
                "embedding": ensure_json_serializable(embedding),
                "face_count": int(len(face_results)),
                "confidence": float(face_data["confidence"]),
                "bbox": ensure_json_serializable(face_data["bbox"]),
                "face_crop_b64": face_crop_b64,  # Add the cropped face image
            }

            return result

        except Exception as e:
            logger.error(f"Face processing failed: {e}")
            return {"success": False, "error": str(e), "face_count": 0}

    async def process_customer_faces_from_image(
        self, base64_image: str, tenant_id: str
    ) -> Dict:
        """
        Process all faces in an uploaded image for customer detection.
        Unlike staff processing which only uses the first face, this processes ALL faces.

        Returns:
            {
                'success': bool,
                'faces': List[face_data],  # All detected faces
                'face_count': int,
                'error': str (if success=False)
            }
        """
        try:
            import base64
            import hashlib

            import cv2

            # Decode image
            image = self.decode_base64_image(base64_image)

            # Calculate image hash for duplicate detection
            image_bytes = base64.b64decode(base64_image.split(",")[-1])
            image_hash = hashlib.sha256(image_bytes).hexdigest()

            # Detect faces
            face_results = self.detect_faces_and_landmarks(image)

            if not face_results:
                return {
                    "success": False,
                    "error": "No faces detected in image",
                    "face_count": 0,
                    "faces": [],
                }

            logger.info(f"Detected {len(face_results)} faces in uploaded image")

            # Process ALL faces, not just the first one
            processed_faces = []

            for i, face_data in enumerate(face_results):
                try:
                    landmarks = face_data["landmarks"]

                    # Generate embedding for this face
                    embedding = self.extract_face_embedding(image, landmarks)

                    # Extract face crop for this face
                    face_crop = self._extract_face_region(image, landmarks)

                    # Convert face crop to base64
                    face_crop_b64 = None
                    try:
                        _, buffer = cv2.imencode(".jpg", face_crop)
                        face_crop_b64 = base64.b64encode(buffer).decode("utf-8")
                    except Exception as e:
                        logger.warning(f"Failed to encode face crop {i} to base64: {e}")

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
                            return {
                                key: ensure_json_serializable(value)
                                for key, value in obj.items()
                            }
                        else:
                            return obj

                    # Prepare face data
                    processed_face = {
                        "face_index": i,
                        "landmarks": ensure_json_serializable(landmarks),
                        "embedding": ensure_json_serializable(embedding),
                        "confidence": float(face_data["confidence"]),
                        "bbox": ensure_json_serializable(face_data["bbox"]),
                        "face_crop_b64": face_crop_b64,
                    }

                    processed_faces.append(processed_face)
                    logger.info(
                        f"Successfully processed face {i+1}/{len(face_results)} with confidence {face_data['confidence']:.3f}"
                    )

                except Exception as face_error:
                    logger.error(f"Failed to process face {i}: {face_error}")
                    # Continue with other faces even if one fails
                    continue

            if not processed_faces:
                return {
                    "success": False,
                    "error": "Failed to process any faces from the image",
                    "face_count": 0,
                    "faces": [],
                }

            result = {
                "success": True,
                "image_hash": image_hash,
                "faces": processed_faces,
                "face_count": len(processed_faces),
                "total_detected": len(face_results),
            }

            logger.info(
                f"Successfully processed {len(processed_faces)} faces from uploaded image"
            )
            return result

        except Exception as e:
            logger.error(f"Customer face processing failed: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e), "face_count": 0, "faces": []}

    async def test_face_recognition(
        self, test_image_b64: str, tenant_id: str, staff_embeddings: List[Dict]
    ) -> Dict:
        """Test face recognition against known staff embeddings."""
        try:
            # Process test image
            image = self.decode_base64_image(test_image_b64)
            face_results = self.detect_faces_and_landmarks(image)

            if not face_results:
                return {
                    "success": False,
                    "error": "No faces detected in test image",
                    "matches": [],
                }

            # Use first detected face
            test_landmarks = face_results[0]["landmarks"]
            test_embedding = self.extract_face_embedding(image, test_landmarks)

            # Compare against staff embeddings
            matches = []
            for staff_data in staff_embeddings:
                similarity = self._calculate_similarity(
                    test_embedding, staff_data["embedding"]
                )
                matches.append(
                    {
                        "staff_id": staff_data["staff_id"],
                        "staff_name": staff_data.get("name", "Unknown"),
                        "similarity": similarity,
                        "image_id": staff_data.get("image_id"),
                    }
                )

            # Sort by similarity (descending)
            matches.sort(key=lambda x: x["similarity"], reverse=True)

            # Find best match above threshold
            best_match = None
            if matches and matches[0]["similarity"] > 0.7:  # Configurable threshold
                best_match = matches[0]

            return {
                "success": True,
                "matches": matches[:5],  # Top 5 matches
                "best_match": best_match,
                "processing_info": {
                    "test_face_detected": True,
                    "test_confidence": face_results[0]["confidence"],
                    "total_staff_compared": len(staff_embeddings),
                },
            }

        except Exception as e:
            logger.error(f"Face recognition test failed: {e}")
            return {"success": False, "error": str(e), "matches": []}

    def _calculate_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
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

    def _enhanced_detect_faces_and_landmarks(self, image: ArrayType) -> List[Dict]:
        """
        Enhanced face detection with improved face information for cropping
        """
        try:
            # Use existing detection method
            face_results = self.detect_faces_and_landmarks(image)

            # Enhance face results with additional metadata for cropping
            enhanced_results = []
            for face_data in face_results:
                enhanced_face = face_data.copy()

                # Add face area for size-based strategies
                bbox = face_data["bbox"]
                w, h = bbox[2], bbox[3]
                enhanced_face["area"] = w * h

                # Add face quality assessment
                try:
                    x, y, w, h = bbox
                    face_crop = image[y : y + h, x : x + w]
                    face_quality = self._assess_face_crop_quality(face_crop)
                    enhanced_face["face_quality"] = face_quality
                except Exception:
                    enhanced_face["face_quality"] = 0.5  # Default quality

                # Add detector type for quality scoring
                enhanced_face["detector"] = "haar"  # Current detector type

                enhanced_results.append(enhanced_face)

            return enhanced_results

        except Exception as e:
            logger.error(f"Enhanced face detection failed: {e}")
            return self.detect_faces_and_landmarks(image)

    def _assess_face_crop_quality(self, face_crop: ArrayType) -> float:
        """Assess quality of a face crop for selection"""
        if face_crop.size == 0:
            return 0.0

        try:
            # Convert to grayscale for analysis
            gray = (
                cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
                if len(face_crop.shape) == 3
                else face_crop
            )

            # Multiple quality factors
            quality_factors = []

            # Sharpness
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(1.0, laplacian_var / 200)
            quality_factors.append(sharpness_score)

            # Contrast
            contrast = gray.std()
            contrast_score = min(1.0, contrast / 40)
            quality_factors.append(contrast_score)

            # Brightness (face should be well lit)
            brightness = gray.mean()
            brightness_score = 1.0 - abs(brightness - 120) / 120
            quality_factors.append(brightness_score * 0.8)

            # Face size quality (larger is generally better for recognition)
            size_score = min(1.0, min(face_crop.shape[:2]) / 100)
            quality_factors.append(size_score)

            return np.mean(quality_factors)

        except Exception as e:
            logger.debug(f"Face crop quality assessment failed: {e}")
            return 0.5

    async def process_staff_face_image_enhanced(
        self, base64_image: str, tenant_id: str, staff_id: str
    ) -> Dict:
        """
        Enhanced staff face processing pipeline with advanced cropping
        """
        try:
            import base64
            import hashlib
            import uuid

            import cv2

            from .face_cropper import api_face_cropper

            # Decode image
            image = self.decode_base64_image(base64_image)

            # Calculate image hash for duplicate detection
            image_bytes = base64.b64decode(base64_image.split(",")[-1])
            image_hash = hashlib.sha256(image_bytes).hexdigest()

            # Enhanced face detection
            face_results = self._enhanced_detect_faces_and_landmarks(image)

            if not face_results:
                return {
                    "success": False,
                    "error": "No faces detected in image",
                    "face_count": 0,
                }

            # Use enhanced cropping for multi-face selection
            if len(face_results) > 1:
                logger.info(
                    f"Multiple faces detected ({len(face_results)}), using enhanced selection"
                )
                crop_result = api_face_cropper.crop_multiple_faces(image, face_results)
                selected_face_data = face_results[crop_result["selected_face_index"]]
                face_crop = crop_result["cropped_face"]
                crop_metadata = {
                    "crop_strategy": crop_result["crop_strategy"],
                    "total_faces": crop_result["total_faces"],
                    "selection_strategy": crop_result["selection_strategy"],
                }
            else:
                # Single face processing
                face_data = face_results[0]
                crop_result = api_face_cropper.crop_face(image, face_data)
                selected_face_data = face_data
                face_crop = crop_result["cropped_face"]
                crop_metadata = {
                    "crop_strategy": crop_result["crop_strategy"],
                    "total_faces": 1,
                    "selection_strategy": "single_face",
                }

            landmarks = selected_face_data["landmarks"]

            # Generate embedding using cropped face
            # For embedding, we still use the landmark-based extraction for consistency
            embedding = self.extract_face_embedding(image, landmarks)

            # Convert face crop to base64
            face_crop_b64 = None
            try:
                _, buffer = cv2.imencode(".jpg", face_crop)
                face_crop_b64 = base64.b64encode(buffer).decode("utf-8")
            except Exception as e:
                logger.warning(f"Failed to encode face crop to base64: {e}")

            # Generate unique image ID
            image_id = str(uuid.uuid4())

            # Upload original image to MinIO
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
                    return {
                        key: ensure_json_serializable(value)
                        for key, value in obj.items()
                    }
                else:
                    return obj

            result = {
                "success": True,
                "image_id": image_id,
                "image_path": image_path,
                "image_hash": image_hash,
                "landmarks": ensure_json_serializable(landmarks),
                "embedding": ensure_json_serializable(embedding),
                "face_count": len(face_results),
                "confidence": float(selected_face_data["confidence"]),
                "bbox": ensure_json_serializable(selected_face_data["bbox"]),
                "face_crop_b64": face_crop_b64,
                "crop_metadata": ensure_json_serializable(crop_metadata),
                "face_quality": float(selected_face_data.get("face_quality", 0.5)),
                "processing_version": "enhanced_v2",  # Version flag for tracking
            }

            return result

        except Exception as e:
            logger.error(f"Enhanced face processing failed: {e}")
            # Fallback to original processing
            return await self.process_staff_face_image(
                base64_image, tenant_id, staff_id
            )

    async def process_customer_faces_from_image_enhanced(
        self, base64_image: str, tenant_id: str
    ) -> Dict:
        """
        Enhanced customer face processing with improved cropping for all faces
        """
        try:
            import base64
            import hashlib

            import cv2

            from .face_cropper import api_face_cropper

            # Decode image
            image = self.decode_base64_image(base64_image)

            # Calculate image hash for duplicate detection
            image_bytes = base64.b64decode(base64_image.split(",")[-1])
            image_hash = hashlib.sha256(image_bytes).hexdigest()

            # Enhanced face detection
            face_results = self._enhanced_detect_faces_and_landmarks(image)

            if not face_results:
                return {
                    "success": False,
                    "error": "No faces detected in image",
                    "face_count": 0,
                    "faces": [],
                }

            logger.info(
                f"Detected {len(face_results)} faces in uploaded customer image"
            )

            # Process ALL faces with enhanced cropping
            processed_faces = []

            for i, face_data in enumerate(face_results):
                try:
                    # Use enhanced cropping for each face
                    crop_result = api_face_cropper.crop_face(image, face_data)
                    face_crop = crop_result["cropped_face"]

                    # Generate embedding using landmark-based extraction (for consistency)
                    landmarks = face_data["landmarks"]
                    embedding = self.extract_face_embedding(image, landmarks)

                    # Convert face crop to base64
                    face_crop_b64 = None
                    try:
                        _, buffer = cv2.imencode(".jpg", face_crop)
                        face_crop_b64 = base64.b64encode(buffer).decode("utf-8")
                    except Exception as e:
                        logger.warning(f"Failed to encode face crop {i} to base64: {e}")

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
                            return {
                                key: ensure_json_serializable(value)
                                for key, value in obj.items()
                            }
                        else:
                            return obj

                    # Prepare face data
                    processed_face = {
                        "face_index": i,
                        "landmarks": ensure_json_serializable(landmarks),
                        "embedding": ensure_json_serializable(embedding),
                        "confidence": float(face_data["confidence"]),
                        "bbox": ensure_json_serializable(face_data["bbox"]),
                        "face_crop_b64": face_crop_b64,
                        "crop_metadata": {
                            "crop_strategy": crop_result["crop_strategy"],
                            "face_ratio": crop_result["face_ratio"],
                        },
                        "face_quality": float(face_data.get("face_quality", 0.5)),
                        "processing_version": "enhanced_v2",
                    }

                    processed_faces.append(processed_face)
                    logger.info(
                        f"Successfully processed customer face {i+1}/{len(face_results)} "
                        f"with confidence {face_data['confidence']:.3f} "
                        f"using {crop_result['crop_strategy']} strategy"
                    )

                except Exception as face_error:
                    logger.error(f"Failed to process customer face {i}: {face_error}")
                    # Continue with other faces even if one fails
                    continue

            if not processed_faces:
                return {
                    "success": False,
                    "error": "Failed to process any faces from the image",
                    "face_count": 0,
                    "faces": [],
                }

            result = {
                "success": True,
                "image_hash": image_hash,
                "faces": processed_faces,
                "face_count": len(processed_faces),
                "total_detected": len(face_results),
                "processing_version": "enhanced_v2",
            }

            logger.info(
                f"Successfully processed {len(processed_faces)} customer faces from uploaded image"
            )
            return result

        except Exception as e:
            logger.error(f"Enhanced customer face processing failed: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            # Fallback to original processing
            return await self.process_customer_faces_from_image(base64_image, tenant_id)


# Service instance
face_processing_service = FaceProcessingService()
