"""
Full integration test for the face recognition worker
"""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import numpy as np

from apps.worker.app.main import main, WorkerConfig


@pytest.mark.asyncio
async def test_worker_main_function_mock_mode():
    """Test the main worker function in mock mode"""
    
    # Set environment variables for test
    test_env = {
        "MOCK_MODE": "true",
        "DETECTOR_TYPE": "mock",
        "EMBEDDER_TYPE": "mock", 
        "WORKER_FPS": "2",
        "API_URL": "http://test-api:8080",
        "TENANT_ID": "test-tenant",
        "SITE_ID": "test-site",
        "CAMERA_ID": "test-camera",
        "WORKER_API_KEY": "test-key",
        "LOG_LEVEL": "INFO"
    }
    
    with patch.dict(os.environ, test_env):
        # Patch the config to use test values
        with patch('apps.worker.app.main.config') as mock_config:
            config = WorkerConfig()
            config.mock_mode = True
            config.detector_type = "mock"
            config.embedder_type = "mock"
            config.worker_fps = 2
            config.api_url = "http://test-api:8080"
            config.tenant_id = "test-tenant"
            config.site_id = "test-site" 
            config.camera_id = "test-camera"
            config.worker_api_key = "test-key"
            config.log_level = "INFO"
            config.max_api_retries = 1
            mock_config.return_value = config
            
            # Mock HTTP client
            with patch('httpx.AsyncClient') as mock_client:
                # Mock authentication response
                mock_auth_response = MagicMock()
                mock_auth_response.status_code = 200
                mock_auth_response.json.return_value = {"access_token": "test-token"}
                mock_auth_response.raise_for_status = MagicMock()
                
                # Mock staff response
                mock_staff_response = MagicMock()
                mock_staff_response.status_code = 200
                mock_staff_response.json.return_value = []
                
                # Mock face event response
                mock_face_response = MagicMock()
                mock_face_response.status_code = 200
                mock_face_response.json.return_value = {
                    "match": "new",
                    "person_id": "c_12345678",
                    "similarity": 0.0,
                    "visit_id": "v_87654321"
                }
                mock_face_response.raise_for_status = MagicMock()
                
                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = mock_auth_response
                mock_client_instance.get.return_value = mock_staff_response
                
                # Alternate between auth and face event responses
                def post_side_effect(*args, **kwargs):
                    if "/auth/token" in args[0]:
                        return mock_auth_response
                    else:
                        return mock_face_response
                
                mock_client_instance.post.side_effect = post_side_effect
                mock_client_instance.aclose = AsyncMock()
                mock_client.return_value = mock_client_instance
                
                # Run main function for a short time
                try:
                    await asyncio.wait_for(main(), timeout=2.0)
                except asyncio.TimeoutError:
                    # Expected - we want to stop after processing some frames
                    pass
                
                # Verify that API calls were made
                assert mock_client_instance.post.call_count >= 2  # At least auth + face event
                
                # Check that authentication was called
                auth_calls = [call for call in mock_client_instance.post.call_args_list 
                             if "/auth/token" in str(call)]
                assert len(auth_calls) >= 1
                
                # Check that face events were sent
                face_calls = [call for call in mock_client_instance.post.call_args_list 
                             if "/events/face" in str(call)]
                assert len(face_calls) >= 1


@pytest.mark.asyncio
async def test_worker_configuration_loading():
    """Test that worker configuration loads correctly from environment"""
    
    test_env = {
        "API_URL": "http://custom-api:9090",
        "TENANT_ID": "custom-tenant",
        "SITE_ID": "custom-site", 
        "CAMERA_ID": "custom-camera",
        "WORKER_API_KEY": "custom-key",
        "DETECTOR_TYPE": "yunet",
        "EMBEDDER_TYPE": "insightface",
        "WORKER_FPS": "10",
        "CONFIDENCE_THRESHOLD": "0.8",
        "STAFF_MATCH_THRESHOLD": "0.85",
        "MOCK_MODE": "false",
        "RTSP_URL": "rtsp://camera.local/stream",
        "USB_CAMERA": "1",
        "FRAME_WIDTH": "1280",
        "FRAME_HEIGHT": "720",
        "MAX_API_RETRIES": "5",
        "MAX_CAMERA_RECONNECT_ATTEMPTS": "10",
        "FAILED_EVENT_RETRY_INTERVAL": "60",
        "MAX_QUEUE_RETRIES": "8",
        "LOG_LEVEL": "DEBUG"
    }
    
    with patch.dict(os.environ, test_env):
        config = WorkerConfig()
        
        assert config.api_url == "http://custom-api:9090"
        assert config.tenant_id == "custom-tenant"
        assert config.site_id == "custom-site"
        assert config.camera_id == "custom-camera"
        assert config.worker_api_key == "custom-key"
        assert config.detector_type == "yunet"
        assert config.embedder_type == "insightface"
        assert config.worker_fps == 10
        assert config.confidence_threshold == 0.8
        assert config.staff_match_threshold == 0.85
        assert config.mock_mode is False
        assert config.rtsp_url == "rtsp://camera.local/stream"
        assert config.usb_camera == 1
        assert config.frame_width == 1280
        assert config.frame_height == 720
        assert config.max_api_retries == 5
        assert config.max_camera_reconnect_attempts == 10
        assert config.failed_event_retry_interval == 60
        assert config.max_queue_retries == 8
        assert config.log_level == "DEBUG"


def test_worker_config_defaults():
    """Test that worker configuration has sensible defaults"""
    
    # Clear environment to test defaults
    env_keys_to_clear = [
        "API_URL", "TENANT_ID", "SITE_ID", "CAMERA_ID", "WORKER_API_KEY",
        "DETECTOR_TYPE", "EMBEDDER_TYPE", "WORKER_FPS", "CONFIDENCE_THRESHOLD",
        "STAFF_MATCH_THRESHOLD", "MOCK_MODE", "RTSP_URL", "USB_CAMERA",
        "FRAME_WIDTH", "FRAME_HEIGHT", "MAX_API_RETRIES", 
        "MAX_CAMERA_RECONNECT_ATTEMPTS", "FAILED_EVENT_RETRY_INTERVAL",
        "MAX_QUEUE_RETRIES", "LOG_LEVEL"
    ]
    
    original_values = {}
    for key in env_keys_to_clear:
        original_values[key] = os.environ.get(key)
        if key in os.environ:
            del os.environ[key]
    
    try:
        config = WorkerConfig()
        
        # Check defaults
        assert config.api_url == "http://localhost:8080"
        assert config.tenant_id == "t-dev"
        assert config.site_id == "s-1" 
        assert config.camera_id == "c-1"
        assert config.worker_api_key == "dev-api-key"
        assert config.detector_type == "yunet"
        assert config.embedder_type == "insightface"
        assert config.worker_fps == 5
        assert config.confidence_threshold == 0.7
        assert config.staff_match_threshold == 0.8
        assert config.mock_mode is True  # Default for safety
        assert config.rtsp_url == ""
        assert config.usb_camera == 0
        assert config.frame_width == 640
        assert config.frame_height == 480
        assert config.max_api_retries == 3
        assert config.max_camera_reconnect_attempts == 5
        assert config.failed_event_retry_interval == 30
        assert config.max_queue_retries == 5
        assert config.log_level == "INFO"
        
    finally:
        # Restore original environment
        for key, value in original_values.items():
            if value is not None:
                os.environ[key] = value


@pytest.mark.asyncio
async def test_worker_graceful_shutdown():
    """Test that worker shuts down gracefully"""
    
    config = WorkerConfig()
    config.mock_mode = True
    config.detector_type = "mock"
    config.embedder_type = "mock"
    
    with patch('httpx.AsyncClient') as mock_client:
        # Mock successful initialization
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
        mock_client_instance.aclose = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        from apps.worker.app.main import FaceRecognitionWorker
        
        worker = FaceRecognitionWorker(config)
        await worker.initialize()
        
        # Verify initialization
        assert worker.queue_processor_task is not None
        assert not worker.queue_processor_task.done()
        
        # Shutdown
        await worker.shutdown()
        
        # Verify cleanup
        assert worker.queue_processor_task.cancelled() or worker.queue_processor_task.done()
        mock_client_instance.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_end_to_end_face_processing():
    """Test end-to-end face processing from detection to API call"""
    
    config = WorkerConfig() 
    config.mock_mode = True
    config.detector_type = "mock"
    config.embedder_type = "mock"
    config.confidence_threshold = 0.5
    config.staff_match_threshold = 0.9  # High threshold so no staff matches
    
    with patch('httpx.AsyncClient') as mock_client:
        # Mock responses
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"access_token": "test-token"}
        mock_auth_response.raise_for_status = MagicMock()
        
        mock_staff_response = MagicMock()
        mock_staff_response.status_code = 200
        mock_staff_response.json.return_value = [
            {"staff_id": "staff-1", "face_images": [{"embedding": [0.9] * 512}]}
        ]
        
        mock_face_response = MagicMock() 
        mock_face_response.status_code = 200
        mock_face_response.json.return_value = {
            "match": "new",
            "person_id": "c_abcd1234", 
            "similarity": 0.0,
            "visit_id": "v_1234abcd",
            "person_type": "customer"
        }
        mock_face_response.raise_for_status = MagicMock()
        
        mock_client_instance = AsyncMock()
        
        def post_side_effect(url, **kwargs):
            if "/auth/token" in url:
                return mock_auth_response
            elif "/events/face" in url:
                return mock_face_response
        
        mock_client_instance.post.side_effect = post_side_effect
        mock_client_instance.get.return_value = mock_staff_response
        mock_client.return_value = mock_client_instance
        
        from apps.worker.app.main import FaceRecognitionWorker
        
        worker = FaceRecognitionWorker(config)
        await worker.initialize()
        
        try:
            # Create test frame
            test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            # Process frame
            faces_processed = await worker.process_frame(test_frame)
            
            # Verify processing
            assert faces_processed > 0
            
            # Verify API calls
            face_event_calls = [
                call for call in mock_client_instance.post.call_args_list
                if "/events/face" in str(call)
            ]
            assert len(face_event_calls) >= 1
            
            # Verify event structure
            last_call = face_event_calls[-1]
            event_data = last_call.kwargs["json"]
            
            assert event_data["tenant_id"] == config.tenant_id
            assert event_data["site_id"] == config.site_id
            assert event_data["camera_id"] == config.camera_id
            assert len(event_data["embedding"]) == 512
            assert len(event_data["bbox"]) == 4
            assert "confidence" in event_data
            assert "timestamp" in event_data
            
        finally:
            await worker.shutdown()