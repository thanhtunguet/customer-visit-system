"""Tests for face processing service."""

import base64
import io
import json
import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from PIL import Image

from app.services.face_processing_service import FaceProcessingService


@pytest.fixture
def face_processing_service():
    """Create a face processing service instance for testing."""
    service = FaceProcessingService()
    # Mock the models to avoid initialization issues in tests
    service.face_detector = MagicMock()
    service.face_embedder = MagicMock()
    return service


@pytest.fixture
def sample_base64_image():
    """Create a sample base64 encoded image for testing."""
    # Create a simple RGB image
    img = Image.new('RGB', (200, 200), color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    img_bytes = buffer.getvalue()
    
    # Encode to base64
    b64_string = base64.b64encode(img_bytes).decode('utf-8')
    return f"data:image/jpeg;base64,{b64_string}"


def test_decode_base64_image_success(face_processing_service, sample_base64_image):
    """Test successful base64 image decoding."""
    result = face_processing_service.decode_base64_image(sample_base64_image)
    
    assert isinstance(result, np.ndarray)
    assert result.shape == (200, 200, 3)  # Height, Width, Channels
    assert result.dtype == np.uint8


def test_decode_base64_image_without_data_url(face_processing_service):
    """Test decoding base64 without data URL prefix."""
    # Create simple image without data URL prefix
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    b64_string = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    result = face_processing_service.decode_base64_image(b64_string)
    
    assert isinstance(result, np.ndarray)
    assert result.shape == (100, 100, 3)


def test_decode_base64_image_invalid_data(face_processing_service):
    """Test decoding invalid base64 image data."""
    with pytest.raises(ValueError, match="Invalid image data"):
        face_processing_service.decode_base64_image("invalid_base64_data")


@patch('cv2.FaceDetectorYN')
def test_detect_faces_and_landmarks_success(mock_detector_class, face_processing_service):
    """Test successful face detection and landmark extraction."""
    # Mock the detector
    mock_detector = MagicMock()
    mock_detector_class.create.return_value = mock_detector
    face_processing_service.face_detector = mock_detector
    
    # Mock face detection result
    # Format: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
    mock_faces = np.array([
        [50, 50, 100, 100, 70, 70, 90, 70, 80, 90, 75, 95, 85, 95, 0.95]
    ])
    mock_detector.detect.return_value = (None, mock_faces)
    
    # Create test image
    test_image = np.zeros((200, 200, 3), dtype=np.uint8)
    
    result = face_processing_service.detect_faces_and_landmarks(test_image)
    
    assert len(result) == 1
    face_data = result[0]
    assert face_data['bbox'] == [50, 50, 100, 100]
    assert len(face_data['landmarks']) == 5  # 5-point landmarks
    assert face_data['confidence'] == 0.95


def test_detect_faces_and_landmarks_no_faces(face_processing_service):
    """Test face detection when no faces are found."""
    # Mock no faces detected
    mock_detector = MagicMock()
    mock_detector.detect.return_value = (None, None)
    face_processing_service.face_detector = mock_detector
    
    test_image = np.zeros((200, 200, 3), dtype=np.uint8)
    
    result = face_processing_service.detect_faces_and_landmarks(test_image)
    
    assert result == []


def test_detect_faces_and_landmarks_low_confidence(face_processing_service):
    """Test face detection with low confidence scores."""
    # Mock low confidence detection
    mock_detector = MagicMock()
    mock_faces = np.array([
        [50, 50, 100, 100, 70, 70, 90, 70, 80, 90, 75, 95, 85, 95, 0.5]  # Low confidence
    ])
    mock_detector.detect.return_value = (None, mock_faces)
    face_processing_service.face_detector = mock_detector
    
    test_image = np.zeros((200, 200, 3), dtype=np.uint8)
    
    result = face_processing_service.detect_faces_and_landmarks(test_image)
    
    assert result == []  # Should filter out low confidence detections


def test_extract_face_embedding(face_processing_service):
    """Test face embedding extraction."""
    test_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    test_landmarks = [[70.0, 70.0], [90.0, 70.0], [80.0, 80.0], [75.0, 90.0], [85.0, 90.0]]
    
    result = face_processing_service.extract_face_embedding(test_image, test_landmarks)
    
    assert isinstance(result, list)
    assert len(result) == 512
    assert all(isinstance(x, float) for x in result)
    
    # Check that embedding is normalized (unit vector)
    embedding_array = np.array(result)
    norm = np.linalg.norm(embedding_array)
    assert abs(norm - 1.0) < 1e-6


def test_extract_face_region(face_processing_service):
    """Test face region extraction."""
    test_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    test_landmarks = [[70.0, 70.0], [90.0, 70.0], [80.0, 80.0], [75.0, 90.0], [85.0, 90.0]]
    
    result = face_processing_service._extract_face_region(test_image, test_landmarks)
    
    assert isinstance(result, np.ndarray)
    assert result.shape == (112, 112, 3)  # Standard face size
    assert result.dtype == np.uint8


@pytest.mark.asyncio
async def test_upload_image_to_minio_success(face_processing_service):
    """Test successful image upload to MinIO."""
    test_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    
    with patch('app.services.face_processing_service.minio_client.upload_file') as mock_upload:
        mock_upload.return_value = None
        
        result = await face_processing_service.upload_image_to_minio(
            test_image, "tenant-123", "image-456"
        )
        
        expected_path = "staff-faces/tenant-123/image-456.jpg"
        assert result == expected_path
        mock_upload.assert_called_once_with(
            bucket_name="faces-derived",
            object_name=expected_path,
            file_data=pytest.any(bytes),
            content_type="image/jpeg"
        )


@pytest.mark.asyncio
async def test_process_staff_face_image_success(face_processing_service, sample_base64_image):
    """Test complete face image processing pipeline."""
    # Mock face detection
    mock_faces = [
        {
            'bbox': [50, 50, 100, 100],
            'landmarks': [[70.0, 70.0], [90.0, 70.0], [80.0, 80.0], [75.0, 90.0], [85.0, 90.0]],
            'confidence': 0.95
        }
    ]
    
    with patch.object(face_processing_service, 'detect_faces_and_landmarks', return_value=mock_faces):
        with patch.object(face_processing_service, 'extract_face_embedding', return_value=[0.1] * 512):
            with patch.object(face_processing_service, 'upload_image_to_minio', return_value="test-path.jpg"):
                with patch('uuid.uuid4', return_value=MagicMock(hex='test-uuid')):
                    
                    result = await face_processing_service.process_staff_face_image(
                        sample_base64_image, "tenant-123", 456
                    )
    
    assert result['success'] is True
    assert result['image_id'] == 'test-uuid'
    assert result['image_path'] == 'test-path.jpg'
    assert len(result['landmarks']) == 5
    assert len(result['embedding']) == 512
    assert result['face_count'] == 1
    assert result['confidence'] == 0.95


@pytest.mark.asyncio
async def test_process_staff_face_image_no_faces(face_processing_service, sample_base64_image):
    """Test face processing when no faces are detected."""
    with patch.object(face_processing_service, 'detect_faces_and_landmarks', return_value=[]):
        result = await face_processing_service.process_staff_face_image(
            sample_base64_image, "tenant-123", 456
        )
    
    assert result['success'] is False
    assert result['error'] == 'No faces detected in image'
    assert result['face_count'] == 0


@pytest.mark.asyncio
async def test_test_face_recognition_success(face_processing_service, sample_base64_image):
    """Test face recognition testing functionality."""
    # Mock staff embeddings
    staff_embeddings = [
        {
            'staff_id': 123,
            'name': 'John Doe',
            'image_id': 'img-1',
            'embedding': [0.1] * 512
        },
        {
            'staff_id': 456,
            'name': 'Jane Smith',
            'image_id': 'img-2', 
            'embedding': [0.9] * 512
        }
    ]
    
    # Mock face detection and embedding
    mock_faces = [
        {
            'landmarks': [[70.0, 70.0], [90.0, 70.0], [80.0, 80.0], [75.0, 90.0], [85.0, 90.0]],
            'confidence': 0.88
        }
    ]
    
    test_embedding = [0.15] * 512  # Should match better with John Doe
    
    with patch.object(face_processing_service, 'detect_faces_and_landmarks', return_value=mock_faces):
        with patch.object(face_processing_service, 'extract_face_embedding', return_value=test_embedding):
            
            result = await face_processing_service.test_face_recognition(
                sample_base64_image, "tenant-123", staff_embeddings
            )
    
    assert result['success'] is True
    assert len(result['matches']) == 2
    assert result['matches'][0]['staff_id'] == 123  # John Doe should be first (better match)
    assert result['best_match']['staff_id'] == 123
    assert result['processing_info']['test_face_detected'] is True
    assert result['processing_info']['test_confidence'] == 0.88
    assert result['processing_info']['total_staff_compared'] == 2


@pytest.mark.asyncio
async def test_test_face_recognition_no_face_detected(face_processing_service, sample_base64_image):
    """Test face recognition testing when no face is detected."""
    with patch.object(face_processing_service, 'detect_faces_and_landmarks', return_value=[]):
        result = await face_processing_service.test_face_recognition(
            sample_base64_image, "tenant-123", []
        )
    
    assert result['success'] is False
    assert result['error'] == 'No faces detected in test image'
    assert result['matches'] == []


def test_calculate_similarity_success(face_processing_service):
    """Test cosine similarity calculation."""
    embedding1 = [1.0, 0.0, 0.0]
    embedding2 = [1.0, 0.0, 0.0]  # Same vector
    
    similarity = face_processing_service._calculate_similarity(embedding1, embedding2)
    
    assert abs(similarity - 1.0) < 1e-6  # Should be exactly 1.0


def test_calculate_similarity_orthogonal(face_processing_service):
    """Test similarity of orthogonal vectors."""
    embedding1 = [1.0, 0.0, 0.0]
    embedding2 = [0.0, 1.0, 0.0]  # Orthogonal
    
    similarity = face_processing_service._calculate_similarity(embedding1, embedding2)
    
    assert abs(similarity - 0.0) < 1e-6  # Should be exactly 0.0


def test_calculate_similarity_opposite(face_processing_service):
    """Test similarity of opposite vectors."""
    embedding1 = [1.0, 0.0, 0.0]
    embedding2 = [-1.0, 0.0, 0.0]  # Opposite
    
    similarity = face_processing_service._calculate_similarity(embedding1, embedding2)
    
    assert abs(similarity - (-1.0)) < 1e-6  # Should be exactly -1.0


def test_calculate_similarity_invalid_input(face_processing_service):
    """Test similarity calculation with invalid input."""
    # Different lengths
    similarity = face_processing_service._calculate_similarity([1.0, 0.0], [1.0, 0.0, 0.0])
    assert similarity == 0.0
    
    # Empty embeddings
    similarity = face_processing_service._calculate_similarity([], [])
    assert similarity == 0.0
    
    # None values
    similarity = face_processing_service._calculate_similarity(None, [1.0, 0.0])
    assert similarity == 0.0


def test_calculate_similarity_zero_norm(face_processing_service):
    """Test similarity calculation with zero norm vectors."""
    embedding1 = [0.0, 0.0, 0.0]
    embedding2 = [1.0, 0.0, 0.0]
    
    similarity = face_processing_service._calculate_similarity(embedding1, embedding2)
    
    assert similarity == 0.0  # Should handle zero norm gracefully