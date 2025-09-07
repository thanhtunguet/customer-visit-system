from __future__ import annotations

import logging
import cv2
import numpy as np
from typing import List, Optional
import os

logger = logging.getLogger(__name__)


class FaceEmbedder:
    """Base class for face embedding generation"""
    
    def embed(self, face_image: np.ndarray, landmarks: Optional[np.ndarray] = None) -> List[float]:
        """Generate face embedding from aligned face image"""
        raise NotImplementedError
    
    def align_face(self, image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        """Align face using landmarks"""
        raise NotImplementedError


class InsightFaceEmbedder(FaceEmbedder):
    """InsightFace ArcFace embedding generator"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the InsightFace model"""
        try:
            import insightface
            
            # Try to load the model
            if self.model_path and os.path.exists(self.model_path):
                # Load specific model
                self.model = insightface.model_zoo.get_model(self.model_path)
                self.model.prepare(ctx_id=-1)  # Use CPU, change to 0 for GPU
            else:
                # Use default ArcFace model
                self.model = insightface.app.FaceAnalysis(providers=['CPUExecutionProvider'])
                self.model.prepare(ctx_id=-1, det_size=(640, 640))
            
            logger.info("InsightFace model initialized successfully")
            
        except ImportError:
            logger.warning("InsightFace not available, falling back to mock embedder")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}")
            self.model = None
    
    def align_face(self, image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        """Align face using 5-point landmarks"""
        if landmarks is None or len(landmarks) != 5:
            # Simple resize if no landmarks
            return cv2.resize(image, (112, 112))
        
        # Standard face template for 112x112 face alignment
        template = np.array([
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041]
        ], dtype=np.float32)
        
        # Compute similarity transformation
        landmarks = np.array(landmarks, dtype=np.float32)
        
        # Use partial affine transformation for better alignment
        tform = cv2.estimateAffinePartial2D(landmarks, template, method=cv2.RANSAC)[0]
        
        if tform is None:
            # Fallback to simple resize
            return cv2.resize(image, (112, 112))
        
        # Apply alignment transformation
        aligned = cv2.warpAffine(image, tform, (112, 112), borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return aligned
    
    def embed(self, face_image: np.ndarray, landmarks: Optional[np.ndarray] = None) -> List[float]:
        """Generate 512-dimensional face embedding using ArcFace"""
        if self.model is None:
            return self._generate_mock_embedding(face_image, landmarks)
        
        try:
            # Prepare face image
            if landmarks is not None and len(landmarks) == 5:
                # Align using landmarks
                aligned_face = self.align_face(face_image, landmarks)
            else:
                # Simple resize without alignment
                aligned_face = cv2.resize(face_image, (112, 112))
            
            # Ensure correct format (BGR for InsightFace)
            if len(aligned_face.shape) == 3 and aligned_face.shape[2] == 3:
                # Convert RGB to BGR if needed
                if aligned_face.max() <= 1.0:
                    aligned_face = (aligned_face * 255).astype(np.uint8)
            
            # For direct embedding without face detection, we need to use the recognition model directly
            # First try the full face analysis pipeline
            try:
                faces = self.model.get(aligned_face)
                if len(faces) > 0:
                    embedding = faces[0].embedding
                    embedding = embedding / np.linalg.norm(embedding)
                    return embedding.tolist()
            except:
                pass
            
            # Fallback: use direct model inference if available
            try:
                # Get the recognition model directly from the FaceAnalysis
                rec_model = None
                for model in self.model.models.values():
                    if hasattr(model, 'get_feat'):
                        rec_model = model
                        break
                
                if rec_model is not None:
                    # Direct feature extraction
                    embedding = rec_model.get_feat(aligned_face)
                    embedding = embedding / np.linalg.norm(embedding)
                    return embedding.tolist()
                    
            except Exception as inner_e:
                logger.debug(f"Direct embedding failed: {inner_e}")
            
            logger.warning("Could not generate embedding, using deterministic mock")
            return self._generate_mock_embedding(face_image, landmarks)
                
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return self._generate_mock_embedding(face_image, landmarks)
    
    def _generate_mock_embedding(self, face_image: np.ndarray, landmarks: Optional[np.ndarray] = None) -> List[float]:
        """Generate a deterministic 512D embedding based on image content.

        Avoids identical embeddings across different faces when the real
        model is unavailable by deriving features from the aligned face
        and seeding a PRNG with a stable pixel hash.
        """
        try:
            # Align if landmarks available; otherwise resize
            if landmarks is not None and len(landmarks) == 5:
                aligned = self.align_face(face_image, landmarks)
            else:
                aligned = cv2.resize(face_image, (112, 112))

            # Convert to grayscale and downscale to reduce noise
            gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (32, 32))

            # Stable seed from image bytes
            import hashlib
            h = hashlib.sha256(small.tobytes()).hexdigest()
            seed = int(h[:16], 16)

            # Low-frequency DCT features (256 dims)
            dct = cv2.dct(small.astype(np.float32))
            lf = dct[:16, :16].flatten()

            # Histogram features (32 dims)
            hist = cv2.calcHist([small], [0], None, [32], [0, 256]).flatten()

            # Basic stats (3 dims)
            mean = float(np.mean(small))
            std = float(np.std(small) + 1e-6)
            stats = np.array([mean, std, mean / (std + 1e-6)], dtype=np.float32)

            base = np.concatenate([lf.astype(np.float32), hist.astype(np.float32), stats])

            # Pad deterministically to 512D
            if base.size >= 512:
                vec = base[:512]
            else:
                rng = np.random.default_rng(seed)
                pad = rng.normal(0, 1, 512 - base.size).astype(np.float32)
                vec = np.concatenate([base, pad])

            # L2-normalize
            norm = float(np.linalg.norm(vec) + 1e-12)
            vec = (vec / norm).astype(np.float32)
            return vec.tolist()
        except Exception:
            # Last-resort deterministic fallback
            import hashlib
            b = cv2.resize(face_image, (16, 16)).tobytes()
            seed = int(hashlib.md5(b).hexdigest()[:16], 16)
            rng = np.random.default_rng(seed)
            vec = rng.normal(0, 1, 512).astype(np.float32)
            vec /= (np.linalg.norm(vec) + 1e-12)
            return vec.tolist()


class MockEmbedder(FaceEmbedder):
    """Mock embedder for testing"""
    
    def align_face(self, image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        """Simple resize for alignment"""
        return cv2.resize(image, (112, 112))
    
    def embed(self, face_image: np.ndarray, landmarks: Optional[np.ndarray] = None) -> List[float]:
        """Generate mock embedding based on image properties"""
        # Create deterministic embedding based on image statistics
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY) if len(face_image.shape) == 3 else face_image
        
        # Use image statistics to create a pseudo-embedding
        mean_val = np.mean(gray)
        std_val = np.std(gray)
        
        # Generate deterministic embedding
        np.random.seed(int(mean_val * std_val * 1000) % 2**32)
        embedding = np.random.normal(0, 1, 512)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding.tolist()


def create_embedder(embedder_type: str = "insightface") -> FaceEmbedder:
    """Factory function to create face embedders"""
    embedder_type = embedder_type.lower()
    
    if embedder_type == "insightface":
        return InsightFaceEmbedder()
    elif embedder_type == "mock":
        return MockEmbedder()
    else:
        logger.warning(f"Unknown embedder type: {embedder_type}, using InsightFace")
        return InsightFaceEmbedder()
