import pytest
import numpy as np
from apps.worker.app.embedder import InsightFaceEmbedder, MockEmbedder, create_embedder


def test_mock_embedder():
    """Test mock embedder for testing purposes"""
    embedder = MockEmbedder()
    
    # Create test face image
    face_image = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    
    embedding = embedder.embed(face_image)
    
    assert len(embedding) == 512
    assert all(isinstance(val, float) for val in embedding)
    
    # Check embedding is normalized
    embedding_np = np.array(embedding)
    norm = np.linalg.norm(embedding_np)
    assert abs(norm - 1.0) < 1e-6


def test_insightface_embedder_fallback():
    """Test InsightFace embedder falls back to mock when not available"""
    embedder = InsightFaceEmbedder()
    
    face_image = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    
    # Should work even if InsightFace is not available
    embedding = embedder.embed(face_image)
    
    assert len(embedding) == 512
    assert all(isinstance(val, float) for val in embedding)


def test_face_alignment():
    """Test face alignment with landmarks"""
    embedder = MockEmbedder()
    
    # Create test image and landmarks
    image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    landmarks = np.array([
        [50, 70],   # left eye
        [150, 70],  # right eye  
        [100, 110], # nose
        [70, 140],  # left mouth
        [130, 140], # right mouth
    ])
    
    aligned = embedder.align_face(image, landmarks)
    
    assert aligned.shape == (112, 112, 3)


def test_create_embedder_factory():
    """Test embedder factory function"""
    insightface_embedder = create_embedder("insightface")
    assert isinstance(insightface_embedder, InsightFaceEmbedder)
    
    mock_embedder = create_embedder("mock")
    assert isinstance(mock_embedder, MockEmbedder)
    
    # Test default fallback
    default_embedder = create_embedder("unknown")
    assert isinstance(default_embedder, InsightFaceEmbedder)


def test_embedding_consistency():
    """Test that same face produces similar embeddings"""
    embedder = MockEmbedder()
    
    # Create identical face images
    face_image = np.ones((112, 112, 3), dtype=np.uint8) * 128
    
    embedding1 = embedder.embed(face_image)
    embedding2 = embedder.embed(face_image)
    
    # Mock embedder should produce identical results for identical images
    assert embedding1 == embedding2
    
    # Test with slightly different images
    face_image2 = face_image.copy()
    face_image2[50:60, 50:60] = 255  # Add some variation
    
    embedding3 = embedder.embed(face_image2)
    
    # Embeddings should be different but still valid
    assert embedding1 != embedding3
    assert len(embedding3) == 512


def test_embedding_normalization():
    """Test that embeddings are properly normalized"""
    embedders = [
        create_embedder("mock"),
        create_embedder("insightface")
    ]
    
    face_image = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    
    for embedder in embedders:
        embedding = embedder.embed(face_image)
        embedding_np = np.array(embedding)
        norm = np.linalg.norm(embedding_np)
        
        # Should be unit normalized
        assert abs(norm - 1.0) < 1e-5