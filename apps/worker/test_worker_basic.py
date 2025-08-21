#!/usr/bin/env python3
"""
Basic test script for face recognition worker functionality
"""

import asyncio
import numpy as np
from app.main import WorkerConfig, FaceRecognitionWorker
from app.detectors import create_detector
from app.embedder import create_embedder

async def test_basic_functionality():
    """Test basic worker functionality"""
    print("🧪 Testing Face Recognition Worker Basic Functionality")
    
    # Test detector creation
    print("\n📷 Testing Face Detectors...")
    
    mock_detector = create_detector("mock")
    print(f"✅ Mock detector created: {type(mock_detector).__name__}")
    
    yunet_detector = create_detector("yunet")
    print(f"✅ YuNet detector created: {type(yunet_detector).__name__}")
    
    # Test embedder creation
    print("\n🧠 Testing Face Embedders...")
    
    mock_embedder = create_embedder("mock")
    print(f"✅ Mock embedder created: {type(mock_embedder).__name__}")
    
    insightface_embedder = create_embedder("insightface")
    print(f"✅ InsightFace embedder created: {type(insightface_embedder).__name__}")
    
    # Test face detection
    print("\n🔍 Testing Face Detection...")
    
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    mock_detections = mock_detector.detect(test_image)
    print(f"✅ Mock detector found {len(mock_detections)} faces")
    
    yunet_detections = yunet_detector.detect(test_image)
    print(f"✅ YuNet detector found {len(yunet_detections)} faces")
    
    # Test face embedding
    print("\n🎯 Testing Face Embedding...")
    
    if mock_detections:
        det = mock_detections[0]
        bbox = det["bbox"]
        x, y, w, h = map(int, bbox)
        face_img = test_image[y:y+h, x:x+w]
        
        if face_img.size > 0:
            mock_embedding = mock_embedder.embed(face_img, det.get("landmarks"))
            print(f"✅ Mock embedding generated: {len(mock_embedding)} dimensions")
            
            insightface_embedding = insightface_embedder.embed(face_img, det.get("landmarks"))
            print(f"✅ InsightFace embedding generated: {len(insightface_embedding)} dimensions")
    
    # Test worker configuration
    print("\n⚙️ Testing Worker Configuration...")
    
    config = WorkerConfig()
    config.validate()
    print("✅ Worker configuration validated")
    
    print(f"   - API URL: {config.api_url}")
    print(f"   - Tenant: {config.tenant_id}")
    print(f"   - Site: {config.site_id}")
    print(f"   - Camera: {config.camera_id}")
    print(f"   - Mock Mode: {config.mock_mode}")
    print(f"   - Detector: {config.detector_type}")
    print(f"   - Embedder: {config.embedder_type}")
    print(f"   - FPS: {config.worker_fps}")
    print(f"   - Confidence Threshold: {config.confidence_threshold}")
    print(f"   - Staff Match Threshold: {config.staff_match_threshold}")
    
    print("\n🎉 All basic functionality tests passed!")
    return True

def test_synchronous_components():
    """Test non-async components"""
    print("\n🔧 Testing Synchronous Components...")
    
    # Test configuration with different values
    import os
    
    old_values = {}
    test_env = {
        "DETECTOR_TYPE": "yunet",
        "EMBEDDER_TYPE": "insightface", 
        "WORKER_FPS": "10",
        "MOCK_MODE": "false",
        "CONFIDENCE_THRESHOLD": "0.8"
    }
    
    # Save old values and set test values
    for key, value in test_env.items():
        old_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        config = WorkerConfig()
        assert config.detector_type == "yunet"
        assert config.embedder_type == "insightface"
        assert config.worker_fps == 10
        assert config.mock_mode is False
        assert config.confidence_threshold == 0.8
        print("✅ Environment configuration loading works")
        
    finally:
        # Restore old values
        for key, old_value in old_values.items():
            if old_value is not None:
                os.environ[key] = old_value
            elif key in os.environ:
                del os.environ[key]
    
    # Test face detection and embedding with different parameters
    detector = create_detector("mock")
    embedder = create_embedder("mock")
    
    # Create test images of different sizes
    test_images = [
        np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8),
        np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8),
    ]
    
    for i, img in enumerate(test_images):
        detections = detector.detect(img)
        print(f"✅ Image {i+1} ({img.shape}): {len(detections)} faces detected")
        
        if detections:
            det = detections[0]
            bbox = det["bbox"]
            x, y, w, h = map(int, bbox)
            
            # Ensure valid crop
            x = max(0, min(x, img.shape[1] - 1))
            y = max(0, min(y, img.shape[0] - 1))
            w = max(1, min(w, img.shape[1] - x))
            h = max(1, min(h, img.shape[0] - y))
            
            face_img = img[y:y+h, x:x+w]
            
            if face_img.size > 0:
                embedding = embedder.embed(face_img)
                print(f"   - Embedding: {len(embedding)} dims, range: [{min(embedding):.3f}, {max(embedding):.3f}]")
    
    print("✅ Synchronous component tests passed!")

if __name__ == "__main__":
    print("🚀 Starting Face Recognition Worker Tests")
    
    # Run synchronous tests
    test_synchronous_components()
    
    # Run async tests
    try:
        asyncio.run(test_basic_functionality())
        print("\n✅ All tests completed successfully! 🎉")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()