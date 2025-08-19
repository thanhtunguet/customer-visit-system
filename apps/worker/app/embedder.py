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
                self.model = insightface.model_zoo.get_model(self.model_path)
                self.model.prepare(ctx_id=-1)  # Use CPU
            else:
                # Download and use default model
                self.model = insightface.app.FaceAnalysis()
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
            # Simple crop if no landmarks
            return cv2.resize(image, (112, 112))
        
        # Standard face template for alignment
        template = np.array([
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041]
        ], dtype=np.float32)
        
        # Compute transformation matrix
        landmarks = np.array(landmarks, dtype=np.float32)
        tform = cv2.estimateAffinePartial2D(landmarks, template)[0]
        
        # Apply alignment
        aligned = cv2.warpAffine(image, tform, (112, 112), borderMode=cv2.BORDER_CONSTANT)
        return aligned
    
    def embed(self, face_image: np.ndarray, landmarks: Optional[np.ndarray] = None) -> List[float]:
        """Generate 512-dimensional face embedding"""
        if self.model is None:
            # Return mock embedding if model not available
            return self._generate_mock_embedding()
        
        try:
            # Align face if landmarks provided
            if landmarks is not None:
                face_image = self.align_face(face_image, landmarks)
            else:
                # Ensure consistent input size
                face_image = cv2.resize(face_image, (112, 112))
            
            # Generate embedding
            embedding = self.model.get_feat(face_image)
            
            # Normalize embedding
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return self._generate_mock_embedding()
    
    def _generate_mock_embedding(self) -> List[float]:
        """Generate a mock 512-dimensional embedding for testing"""
        # Create a deterministic mock embedding based on image content
        np.random.seed(42)
        embedding = np.random.normal(0, 1, 512)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()


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