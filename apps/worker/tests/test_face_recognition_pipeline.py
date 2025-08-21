"""
Integration tests for the complete face recognition pipeline
"""

import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest
import httpx

from apps.worker.app.main import FaceRecognitionWorker, WorkerConfig, FaceDetectedEvent


@pytest.fixture
def worker_config():
    """Create test worker configuration"""
    config = WorkerConfig()
    config.mock_mode = True
    config.detector_type = "mock"
    config.embedder_type = "mock" 
    config.confidence_threshold = 0.5
    config.staff_match_threshold = 0.8
    config.worker_fps = 1
    config.max_api_retries = 2
    config.max_queue_retries = 2
    return config


@pytest.fixture
def mock_frame():
    """Create a mock camera frame"""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


@pytest.fixture  
async def worker(worker_config):
    """Create and initialize test worker"""
    with patch('httpx.AsyncClient') as mock_client:
        # Mock authentication response
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"access_token": "test-token"}
        mock_auth_response.raise_for_status = MagicMock()
        
        # Mock staff response
        mock_staff_response = MagicMock()
        mock_staff_response.status_code = 200
        mock_staff_response.json.return_value = [
            {
                "staff_id": "staff-1",
                "face_images": [{"embedding": [0.1] * 512}]
            }
        ]
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_auth_response
        mock_client_instance.get.return_value = mock_staff_response
        mock_client.return_value = mock_client_instance
        
        worker = FaceRecognitionWorker(worker_config)
        await worker.initialize()
        
        yield worker
        
        await worker.shutdown()


@pytest.mark.asyncio
async def test_worker_initialization(worker_config):
    """Test that worker initializes correctly"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"access_token": "test-token"}
        mock_auth_response.raise_for_status = MagicMock()
        
        mock_staff_response = MagicMock()
        mock_staff_response.status_code = 200
        mock_staff_response.json.return_value = []
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_auth_response
        mock_client_instance.get.return_value = mock_staff_response
        mock_client.return_value = mock_client_instance
        
        worker = FaceRecognitionWorker(worker_config)
        await worker.initialize()
        
        assert worker.access_token == "test-token"
        assert worker.detector is not None
        assert worker.embedder is not None
        assert worker.queue_processor_task is not None
        
        await worker.shutdown()


@pytest.mark.asyncio
async def test_face_detection_and_embedding(worker, mock_frame):
    """Test that face detection and embedding work together"""
    # Process a frame
    faces_processed = await worker.process_frame(mock_frame)
    
    # Should detect at least one mock face
    assert faces_processed > 0


@pytest.mark.asyncio
async def test_staff_matching(worker):
    """Test staff pre-matching functionality"""
    # Create a test embedding similar to staff embedding
    test_embedding = [0.1] * 512  # Same as staff-1 embedding
    
    is_staff, staff_id = worker._is_staff_match(test_embedding, threshold=0.7)
    
    assert is_staff
    assert staff_id == "staff-1"


@pytest.mark.asyncio
async def test_staff_no_match(worker):
    """Test when embedding doesn't match any staff"""
    # Create a different embedding
    test_embedding = [0.9] * 512  # Different from staff embeddings
    
    is_staff, staff_id = worker._is_staff_match(test_embedding)
    
    assert not is_staff
    assert staff_id is None


@pytest.mark.asyncio
async def test_face_event_creation_and_sending(worker, mock_frame):
    """Test complete pipeline from frame to API call"""
    # Mock successful API response
    mock_api_response = MagicMock()
    mock_api_response.status_code = 200
    mock_api_response.json.return_value = {
        "match": "new",
        "person_id": "c_12345678",
        "similarity": 0.0,
        "visit_id": "v_87654321",
        "person_type": "customer"
    }
    mock_api_response.raise_for_status = MagicMock()
    
    worker.http_client.post = AsyncMock(return_value=mock_api_response)
    
    # Process frame
    faces_processed = await worker.process_frame(mock_frame)
    
    assert faces_processed > 0
    
    # Verify API was called
    worker.http_client.post.assert_called()
    
    # Check the call arguments
    call_args = worker.http_client.post.call_args
    assert "/v1/events/face" in call_args[1]["json"]["tenant_id"]


@pytest.mark.asyncio
async def test_api_retry_logic(worker):
    """Test API retry logic on failures"""
    # Create test event
    event = FaceDetectedEvent(
        tenant_id="test-tenant",
        site_id="test-site", 
        camera_id="test-camera",
        timestamp=datetime.now(timezone.utc),
        embedding=[0.1] * 512,
        bbox=[0, 0, 100, 100],
        confidence=0.9,
    )
    
    # Mock API failure then success
    mock_failure = MagicMock()
    mock_failure.status_code = 500
    mock_failure.raise_for_status.side_effect = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_failure)
    
    mock_success = MagicMock()
    mock_success.status_code = 200
    mock_success.json.return_value = {"match": "new", "person_id": "test"}
    mock_success.raise_for_status = MagicMock()
    
    worker.http_client.post = AsyncMock(side_effect=[mock_failure, mock_success])
    
    # Send event
    result = await worker._send_face_event(event, max_retries=1)
    
    # Should succeed after retry
    assert "error" not in result
    assert result["person_id"] == "test"
    assert worker.http_client.post.call_count == 2


@pytest.mark.asyncio
async def test_failed_event_queuing(worker):
    """Test that failed events are queued for retry"""
    # Create test event
    event = FaceDetectedEvent(
        tenant_id="test-tenant",
        site_id="test-site",
        camera_id="test-camera", 
        timestamp=datetime.now(timezone.utc),
        embedding=[0.1] * 512,
        bbox=[0, 0, 100, 100],
        confidence=0.9,
    )
    
    # Mock API failure
    mock_failure = MagicMock()
    mock_failure.status_code = 500
    mock_failure.raise_for_status.side_effect = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_failure)
    
    worker.http_client.post = AsyncMock(return_value=mock_failure)
    
    # Send event
    result = await worker._send_face_event(event, max_retries=1)
    
    # Should queue for retry
    assert "queued for retry" in result["error"]
    assert not worker.failed_events_queue.empty()


@pytest.mark.asyncio
async def test_config_validation():
    """Test configuration validation"""
    config = WorkerConfig()
    
    # Should not raise any exceptions
    config.validate()
    
    # Test with custom values
    config.worker_fps = 15
    config.worker_api_key = "custom-key"
    config.mock_mode = False
    
    # Should log warnings but not fail
    config.validate()


@pytest.mark.asyncio  
async def test_camera_connection_failure():
    """Test behavior when camera connection fails"""
    config = WorkerConfig()
    config.mock_mode = False
    config.usb_camera = 999  # Non-existent camera
    config.max_camera_reconnect_attempts = 1
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"access_token": "test-token"}
        mock_auth_response.raise_for_status = MagicMock()
        
        mock_staff_response = MagicMock()
        mock_staff_response.status_code = 200
        mock_staff_response.json.return_value = []
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_auth_response
        mock_client_instance.get.return_value = mock_staff_response
        mock_client.return_value = mock_client_instance
        
        worker = FaceRecognitionWorker(config)
        await worker.initialize()
        
        # This should handle camera failure gracefully
        with patch('cv2.VideoCapture') as mock_cap:
            mock_cap_instance = MagicMock()
            mock_cap_instance.isOpened.return_value = False
            mock_cap.return_value = mock_cap_instance
            
            # Should not raise exception
            try:
                await asyncio.wait_for(worker.run_camera_capture(), timeout=0.5)
            except asyncio.TimeoutError:
                pass  # Expected to timeout in test
        
        await worker.shutdown()


def test_face_detected_event_serialization():
    """Test that FaceDetectedEvent serializes correctly"""
    event = FaceDetectedEvent(
        tenant_id="test-tenant",
        site_id="test-site", 
        camera_id="test-camera",
        timestamp=datetime.now(timezone.utc),
        embedding=[0.1] * 512,
        bbox=[0, 0, 100, 100],
        confidence=0.95,
        is_staff_local=True,
        staff_id="staff-123"
    )
    
    # Should serialize to JSON without errors
    serialized = event.model_dump(mode="json")
    
    assert serialized["tenant_id"] == "test-tenant"
    assert serialized["confidence"] == 0.95
    assert serialized["is_staff_local"] is True
    assert serialized["staff_id"] == "staff-123"
    assert len(serialized["embedding"]) == 512