from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FaceDetector:
    """Base class for face detectors"""

    def detect(self, image: np.ndarray) -> List[Dict]:
        """
        Detect faces in image
        Returns list of detections with 'bbox' and optional 'landmarks'
        """
        raise NotImplementedError


class YuNetDetector(FaceDetector):
    """YuNet face detector - fast and lightweight"""

    def __init__(self, model_path: Optional[str] = None, score_threshold: float = 0.5):
        self.score_threshold = score_threshold
        self.model_path = model_path or self._download_model()
        self.detector = None
        self._initialize()

    def _download_model(self) -> str:
        """Download YuNet model if not exists"""
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(model_dir, exist_ok=True)

        model_path = os.path.join(model_dir, "yunet.onnx")

        if not os.path.exists(model_path):
            # For now, we'll create a placeholder - in production you'd download the actual model
            logger.warning("YuNet model not found, using OpenCV DNN face detector")
            return None

        return model_path

    def _initialize(self):
        """Initialize the detector"""
        try:
            if self.model_path and os.path.exists(self.model_path):
                self.detector = cv2.FaceDetectorYN.create(
                    model=self.model_path,
                    config="",
                    input_size=(320, 240),
                    score_threshold=self.score_threshold,
                )
            else:
                # Fallback to OpenCV Haar Cascades
                cascade_path = (
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                )
                self.detector = cv2.CascadeClassifier(cascade_path)
                logger.info("Using Haar Cascade fallback detector")
        except Exception as e:
            logger.error(f"Failed to initialize YuNet detector: {e}")
            # Fallback to Haar Cascade
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.detector = cv2.CascadeClassifier(cascade_path)

    def detect(self, image: np.ndarray) -> List[Dict]:
        """Detect faces in image"""
        if self.detector is None:
            return []

        try:
            height, width = image.shape[:2]

            if isinstance(self.detector, cv2.FaceDetectorYN):
                # YuNet detector
                self.detector.setInputSize((width, height))
                _, faces = self.detector.detect(image)

                results = []
                if faces is not None:
                    for face in faces:
                        x, y, w, h = face[:4].astype(int)
                        confidence = face[14]
                        landmarks = face[4:14].reshape(5, 2)  # 5 facial landmarks

                        results.append(
                            {
                                "bbox": [x, y, w, h],
                                "confidence": float(confidence),
                                "landmarks": landmarks.tolist(),
                            }
                        )
                return results

            else:
                # Haar Cascade fallback
                gray = (
                    cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    if len(image.shape) == 3
                    else image
                )
                faces = self.detector.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))

                results = []
                for x, y, w, h in faces:
                    results.append(
                        {
                            "bbox": [x, y, w, h],
                            "confidence": 1.0,  # Haar cascade doesn't provide confidence
                            "landmarks": None,
                        }
                    )
                return results

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []


class MockDetector(FaceDetector):
    """Mock detector for testing"""

    def detect(self, image: np.ndarray) -> List[Dict]:
        height, width = image.shape[:2]
        # Return a single mock face in the center
        return [
            {
                "bbox": [width // 4, height // 4, width // 2, height // 2],
                "confidence": 0.95,
                "landmarks": [
                    [width // 2 - 20, height // 2 - 10],  # left eye
                    [width // 2 + 20, height // 2 - 10],  # right eye
                    [width // 2, height // 2],  # nose
                    [width // 2 - 15, height // 2 + 20],  # left mouth
                    [width // 2 + 15, height // 2 + 20],  # right mouth
                ],
            }
        ]


def create_detector(detector_type: str = "yunet") -> FaceDetector:
    """Factory function to create face detectors"""
    detector_type = detector_type.lower()

    if detector_type == "yunet":
        return YuNetDetector()
    elif detector_type == "mock":
        return MockDetector()
    else:
        logger.warning(f"Unknown detector type: {detector_type}, using YuNet")
        return YuNetDetector()
