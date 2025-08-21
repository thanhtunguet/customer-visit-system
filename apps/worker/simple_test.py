#!/usr/bin/env python3
"""
Simple test for face recognition worker without external dependencies
"""

import sys
import os
import subprocess

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        import cv2
        print("✅ OpenCV imported successfully")
    except ImportError as e:
        print(f"❌ OpenCV import failed: {e}")
        return False
        
    try:
        import numpy as np
        print("✅ NumPy imported successfully") 
    except ImportError as e:
        print(f"❌ NumPy import failed: {e}")
        return False
        
    try:
        import httpx
        print("✅ httpx imported successfully")
    except ImportError as e:
        print(f"❌ httpx import failed: {e}")
        return False
        
    try:
        from pydantic import BaseModel
        print("✅ Pydantic imported successfully")
    except ImportError as e:
        print(f"❌ Pydantic import failed: {e}")
        return False
        
    # Test optional InsightFace
    try:
        import insightface
        print("✅ InsightFace imported successfully")
    except ImportError as e:
        print(f"⚠️  InsightFace not available (will use mock): {e}")
        
    return True

def test_worker_modules():
    """Test that worker modules can be imported"""
    print("\nTesting worker modules...")
    
    # Add current directory to Python path
    sys.path.insert(0, os.getcwd())
    
    try:
        from app.detectors import create_detector, FaceDetector
        print("✅ Detectors module imported")
        
        # Test detector creation
        mock_detector = create_detector("mock")
        print(f"✅ Mock detector created: {type(mock_detector).__name__}")
        
        yunet_detector = create_detector("yunet")  
        print(f"✅ YuNet detector created: {type(yunet_detector).__name__}")
        
    except ImportError as e:
        print(f"❌ Detectors import failed: {e}")
        return False
        
    try:
        from app.embedder import create_embedder, FaceEmbedder
        print("✅ Embedder module imported")
        
        # Test embedder creation
        mock_embedder = create_embedder("mock")
        print(f"✅ Mock embedder created: {type(mock_embedder).__name__}")
        
        insightface_embedder = create_embedder("insightface")
        print(f"✅ InsightFace embedder created: {type(insightface_embedder).__name__}")
        
    except ImportError as e:
        print(f"❌ Embedder import failed: {e}")
        return False
        
    try:
        from app.main import WorkerConfig, FaceRecognitionWorker, FaceDetectedEvent
        print("✅ Main module imported")
        
        # Test configuration
        config = WorkerConfig()
        print(f"✅ Worker config created: mock_mode={config.mock_mode}")
        
    except ImportError as e:
        print(f"❌ Main module import failed: {e}")
        return False
        
    return True

def test_basic_functionality():
    """Test basic functionality without async"""
    print("\nTesting basic functionality...")
    
    try:
        import numpy as np
        from app.detectors import create_detector
        from app.embedder import create_embedder
        
        # Create test image
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        print("✅ Test image created")
        
        # Test mock detector
        detector = create_detector("mock")
        detections = detector.detect(test_image)
        print(f"✅ Mock detector found {len(detections)} faces")
        
        if detections:
            detection = detections[0]
            print(f"   - Bbox: {detection['bbox']}")
            print(f"   - Confidence: {detection['confidence']}")
            print(f"   - Has landmarks: {detection.get('landmarks') is not None}")
        
        # Test mock embedder
        embedder = create_embedder("mock")
        if detections:
            det = detections[0]
            bbox = det["bbox"]
            x, y, w, h = map(int, bbox)
            
            # Extract face region safely
            x = max(0, min(x, test_image.shape[1] - 1))
            y = max(0, min(y, test_image.shape[0] - 1)) 
            w = max(1, min(w, test_image.shape[1] - x))
            h = max(1, min(h, test_image.shape[0] - y))
            
            face_img = test_image[y:y+h, x:x+w]
            
            if face_img.size > 0:
                embedding = embedder.embed(face_img)
                print(f"✅ Mock embedding generated: {len(embedding)} dimensions")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_configuration():
    """Test configuration system"""
    print("\nTesting configuration...")
    
    try:
        from app.main import WorkerConfig
        
        # Test default config
        config = WorkerConfig()
        print("✅ Default configuration loaded")
        
        # Test validation
        config.validate()
        print("✅ Configuration validation passed")
        
        # Test environment override
        old_value = os.environ.get("WORKER_FPS")
        os.environ["WORKER_FPS"] = "10"
        
        config_new = WorkerConfig()
        assert config_new.worker_fps == 10, "Environment variable not loaded"
        print("✅ Environment variable override works")
        
        # Restore
        if old_value is not None:
            os.environ["WORKER_FPS"] = old_value
        else:
            del os.environ["WORKER_FPS"]
            
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Face Recognition Worker - Simple Test Suite\n")
    
    tests = [
        ("Import Tests", test_imports),
        ("Worker Module Tests", test_worker_modules), 
        ("Basic Functionality Tests", test_basic_functionality),
        ("Configuration Tests", test_configuration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"📋 {test_name}")
        print("-" * 50)
        
        try:
            if test_func():
                print(f"✅ {test_name} PASSED\n")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED\n")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}\n")
            failed += 1
    
    print("=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())