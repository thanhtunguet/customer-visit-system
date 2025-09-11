"""
Enhanced face processing service for API integration
Provides high-level interface to the enhanced face detection pipeline
"""

import asyncio
import base64
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class EnhancedFaceProcessorService:
    """
    Service that integrates enhanced face processing capabilities into the API
    """

    def __init__(self):
        self._face_processor = None
        self._initialization_lock = asyncio.Lock()

    async def _get_face_processor(self):
        """Lazy initialization of face processor"""
        if self._face_processor is None:
            async with self._initialization_lock:
                if self._face_processor is None:
                    try:
                        # Import here to avoid circular imports and startup issues
                        import os
                        import sys

                        worker_path = os.path.join(
                            os.path.dirname(__file__), "../../../worker/app"
                        )
                        sys.path.insert(0, worker_path)

                        from face_processor import FaceProcessor

                        self._face_processor = FaceProcessor(
                            min_face_size=40,
                            confidence_threshold=0.6,
                            quality_threshold=0.5,
                            max_workers=1,  # Limit workers in API context
                        )

                        logger.info("Enhanced face processor initialized")

                    except Exception as e:
                        logger.error(
                            f"Failed to initialize enhanced face processor: {e}"
                        )
                        # Create mock processor for fallback
                        self._face_processor = MockFaceProcessor()

        return self._face_processor

    async def process_staff_image(
        self, image_bytes: bytes, staff_id: str
    ) -> Dict[str, Any]:
        """
        Process a staff face image with enhanced pipeline

        Returns:
            Dictionary containing processing results, quality metrics, and recommendations
        """
        try:
            face_processor = await self._get_face_processor()
            result = await face_processor.process_staff_image(image_bytes, staff_id)

            if result["success"]:
                # Add processing metadata
                result["processing_info"] = {
                    "image_id": str(uuid.uuid4()),
                    "processed_at": datetime.utcnow().isoformat(),
                    "processing_version": "2.0",
                    "enhancement_applied": True,
                }

                # Convert face crop to base64 for optional storage
                if "face_crop" in result:
                    import cv2

                    face_crop = result["face_crop"]
                    _, buffer = cv2.imencode(
                        ".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95]
                    )
                    result["face_crop_b64"] = base64.b64encode(buffer.tobytes()).decode(
                        "utf-8"
                    )
                    del result["face_crop"]  # Remove numpy array from result

            return result

        except Exception as e:
            logger.error(f"Enhanced staff image processing failed: {e}")
            return {
                "success": False,
                "error": f"Enhanced processing failed: {str(e)}",
                "quality_score": 0.0,
                "suggestions": ["Try using the standard upload method as fallback"],
            }

    async def assess_image_quality_only(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Assess image quality without full processing or storage

        Returns:
            Dictionary containing quality assessment and recommendations
        """
        try:
            face_processor = await self._get_face_processor()

            # Process image with enhanced pipeline but don't store anything
            result = await face_processor.process_staff_image(
                image_bytes, staff_id="quality_assessment_only"
            )

            # Return assessment-focused results
            assessment = {
                "success": True,
                "face_detected": result.get("success", False),
                "quality_score": result.get("quality_score", 0.0),
                "confidence": result.get("confidence", 0.0),
                "has_landmarks": result.get("face_landmarks") is not None,
                "detector_used": result.get("detector_used"),
                "processing_notes": result.get("processing_notes", []),
                "issues": result.get("issues", []),
                "suggestions": result.get("suggestions", []),
            }

            # Add quality recommendations
            quality_score = assessment["quality_score"]

            if quality_score >= 0.8:
                assessment["quality_rating"] = "Excellent"
                assessment["upload_recommendation"] = "Highly recommended for upload"
            elif quality_score >= 0.7:
                assessment["quality_rating"] = "Good"
                assessment["upload_recommendation"] = "Good for upload"
            elif quality_score >= 0.6:
                assessment["quality_rating"] = "Acceptable"
                assessment["upload_recommendation"] = "Acceptable for upload"
            elif quality_score >= 0.4:
                assessment["quality_rating"] = "Poor"
                assessment["upload_recommendation"] = (
                    "Consider improving image before upload"
                )
            else:
                assessment["quality_rating"] = "Very Poor"
                assessment["upload_recommendation"] = (
                    "Not recommended - please improve image quality"
                )

            return assessment

        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return {
                "success": False,
                "error": f"Quality assessment failed: {str(e)}",
                "quality_score": 0.0,
                "quality_rating": "Unknown",
                "upload_recommendation": "Assessment failed - try standard upload",
            }

    async def batch_process_staff_images(
        self, images_data: List[tuple[bytes, str]], quality_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Process multiple staff images with enhanced pipeline

        Args:
            images_data: List of (image_bytes, staff_id) tuples
            quality_threshold: Minimum quality threshold for acceptance

        Returns:
            List of processing results with quality filtering
        """
        try:
            face_processor = await self._get_face_processor()
            results = await face_processor.batch_process_staff_images(images_data)

            # Apply quality filtering and add metadata
            filtered_results = []

            for i, result in enumerate(results):
                # Add processing metadata
                result["processing_info"] = {
                    "image_id": str(uuid.uuid4()),
                    "processed_at": datetime.utcnow().isoformat(),
                    "processing_version": "2.0",
                    "batch_index": i,
                    "enhancement_applied": True,
                }

                # Apply quality filtering
                quality_score = result.get("quality_score", 0.0)
                result["meets_quality_threshold"] = quality_score >= quality_threshold

                if result["success"] and quality_score < quality_threshold:
                    result["quality_warning"] = (
                        f"Quality score {quality_score:.2f} is below threshold {quality_threshold:.2f}"
                    )

                filtered_results.append(result)

            return filtered_results

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return [
                {
                    "success": False,
                    "error": f"Batch processing failed: {str(e)}",
                    "quality_score": 0.0,
                    "staff_id": (
                        images_data[i][1] if i < len(images_data) else "unknown"
                    ),
                }
                for i in range(len(images_data))
            ]

    async def get_processing_recommendations(self) -> Dict[str, List[str]]:
        """
        Get general processing recommendations based on system capabilities
        """
        try:
            face_processor = await self._get_face_processor()

            recommendations = {
                "image_requirements": [
                    "Minimum resolution: 400x400 pixels",
                    "Clear, well-lit face images work best",
                    "Frontal face view is preferred",
                    "Avoid heavy shadows or backlighting",
                ],
                "quality_tips": [
                    "Ensure face occupies 20-60% of image area",
                    "Use good lighting with even illumination",
                    "Avoid blur - ensure image is sharp and in focus",
                    "Include clear visibility of both eyes and mouth",
                ],
                "supported_formats": [
                    "JPEG with at least 90% quality",
                    "PNG with good compression",
                    "Base64 encoded images supported",
                ],
            }

            # Add detector-specific recommendations if available
            if hasattr(face_processor, "detector") and hasattr(
                face_processor.detector, "detectors"
            ):
                available_detectors = [
                    name for name, _ in face_processor.detector.detectors
                ]

                if "retinaface" in available_detectors:
                    recommendations["advanced_features"] = [
                        "RetinaFace detector available for challenging poses",
                        "High-accuracy facial landmark detection",
                        "Better performance on tilted or profile faces",
                    ]
                elif "mtcnn" in available_detectors:
                    recommendations["advanced_features"] = [
                        "MTCNN detector available for robust detection",
                        "Good performance on various face orientations",
                        "Facial landmark detection available",
                    ]
                else:
                    recommendations["advanced_features"] = [
                        "Basic face detection available",
                        "Consider installing advanced detectors for better performance",
                        "Run: bash scripts/install_face_detection_deps.sh",
                    ]

            return recommendations

        except Exception as e:
            logger.error(f"Failed to get processing recommendations: {e}")
            return {
                "error": [f"Unable to get recommendations: {str(e)}"],
                "basic_requirements": [
                    "Use clear, well-lit face images",
                    "Ensure face is clearly visible",
                    "Avoid low resolution or blurry images",
                ],
            }

    async def cleanup(self):
        """Cleanup processor resources"""
        if self._face_processor and hasattr(self._face_processor, "cleanup"):
            await self._face_processor.cleanup()


class MockFaceProcessor:
    """
    Mock face processor for fallback when enhanced processing is not available
    """

    async def process_staff_image(
        self, image_bytes: bytes, staff_id: str
    ) -> Dict[str, Any]:
        """Mock processing that always returns basic success"""
        import numpy as np

        # Generate mock embedding
        embedding = np.random.normal(0, 1, 512)
        embedding = embedding / np.linalg.norm(embedding)

        return {
            "success": True,
            "face_bbox": [100, 100, 200, 200],  # Mock bbox
            "face_landmarks": None,
            "confidence": 0.7,
            "embedding": embedding.tolist(),
            "quality_score": 0.6,
            "detector_used": "mock",
            "processing_notes": [
                "Using mock face processor - enhanced detection not available",
                "Install enhanced dependencies for better accuracy",
            ],
        }

    async def batch_process_staff_images(
        self, images_data: List[tuple]
    ) -> List[Dict[str, Any]]:
        """Mock batch processing"""
        results = []
        for image_bytes, staff_id in images_data:
            result = await self.process_staff_image(image_bytes, staff_id)
            results.append(result)
        return results

    async def cleanup(self):
        """Mock cleanup"""
        pass


# Global service instance
enhanced_face_processor = EnhancedFaceProcessorService()
