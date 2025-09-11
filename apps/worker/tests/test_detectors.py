import numpy as np

from apps.worker.app.detectors import MockDetector, YuNetDetector, create_detector


def test_mock_detector():
    """Test mock detector for testing purposes"""
    detector = MockDetector()

    # Create test image
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    detections = detector.detect(image)

    assert len(detections) == 1
    detection = detections[0]
    assert "bbox" in detection
    assert "confidence" in detection
    assert "landmarks" in detection
    assert detection["confidence"] == 0.95
    assert len(detection["bbox"]) == 4
    assert len(detection["landmarks"]) == 5


def test_yunet_detector_fallback():
    """Test YuNet detector falls back to Haar cascade"""
    detector = YuNetDetector()

    # Create test image
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Should not crash even without proper model
    detections = detector.detect(image)

    # May return empty list if no faces detected in random image
    assert isinstance(detections, list)

    for detection in detections:
        assert "bbox" in detection
        assert "confidence" in detection
        assert len(detection["bbox"]) == 4


def test_create_detector_factory():
    """Test detector factory function"""
    yunet_detector = create_detector("yunet")
    assert isinstance(yunet_detector, YuNetDetector)

    mock_detector = create_detector("mock")
    assert isinstance(mock_detector, MockDetector)

    # Test default fallback
    default_detector = create_detector("unknown")
    assert isinstance(default_detector, YuNetDetector)


def test_detector_bbox_format():
    """Test that detectors return consistent bbox format"""
    detectors = [create_detector("mock"), create_detector("yunet")]

    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    for detector in detectors:
        detections = detector.detect(image)

        for detection in detections:
            bbox = detection["bbox"]
            assert len(bbox) == 4
            assert all(isinstance(coord, (int, float)) for coord in bbox)

            # Basic sanity check for bbox coordinates
            x, y, w, h = bbox
            assert x >= 0 and y >= 0
            assert w > 0 and h > 0
