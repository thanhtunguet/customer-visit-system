"""
Enhanced Face Cropping Utility

Provides robust face cropping with:
- Configurable margins and aspect ratio handling
- Support for large and small faces
- Multi-face selection strategies
- Edge case handling for faces near frame boundaries
- Canonical output sizing with letterboxing
"""

import logging
import os
from enum import Enum
from typing import Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class PrimaryFaceStrategy(Enum):
    """Strategy for selecting primary face when multiple faces are detected"""

    LARGEST = "largest"  # Choose the largest face by area
    MOST_CENTERED = "most_centered"  # Choose the face closest to center
    HIGHEST_CONFIDENCE = "highest_confidence"  # Choose highest confidence face
    BEST_QUALITY = "best_quality"  # Choose face with best overall quality score


class FaceCropper:
    """
    Enhanced face cropping utility with configurable parameters
    """

    def __init__(
        self,
        min_face_size: Optional[int] = None,
        crop_margin_pct: Optional[float] = None,
        target_size: Optional[int] = None,
        primary_face_strategy: Optional[str] = None,
        max_face_ratio: Optional[float] = None,
        preserve_aspect: Optional[bool] = None,
    ):
        """
        Initialize face cropper with configurable parameters

        Args:
            min_face_size: Minimum face size in pixels (default from env or 40)
            crop_margin_pct: Margin around face as percentage (default from env or 0.15)
            target_size: Target output size for cropped faces (default from env or 224)
            primary_face_strategy: Strategy for selecting primary face (default from env or 'best_quality')
            max_face_ratio: Maximum face-to-frame ratio before special handling (default from env or 0.6)
            preserve_aspect: Whether to preserve aspect ratio with letterboxing (default from env or True)
        """
        # Load configuration from environment with fallbacks
        self.min_face_size = min_face_size or int(os.getenv("MIN_FACE_SIZE", "40"))
        self.crop_margin_pct = crop_margin_pct or float(
            os.getenv("CROP_MARGIN_PCT", "0.15")
        )
        self.target_size = target_size or int(os.getenv("TARGET_SIZE", "224"))
        self.max_face_ratio = max_face_ratio or float(
            os.getenv("MAX_FACE_RATIO", "0.6")
        )
        self.preserve_aspect = (
            preserve_aspect
            if preserve_aspect is not None
            else os.getenv("PRESERVE_ASPECT", "true").lower() == "true"
        )

        # Parse primary face strategy
        strategy_str = primary_face_strategy or os.getenv(
            "PRIMARY_FACE_STRATEGY", "best_quality"
        )
        try:
            self.primary_face_strategy = PrimaryFaceStrategy(strategy_str)
        except ValueError:
            logger.warning(
                f"Invalid primary face strategy: {strategy_str}, using 'best_quality'"
            )
            self.primary_face_strategy = PrimaryFaceStrategy.BEST_QUALITY

        logger.info(
            f"FaceCropper initialized: min_face_size={self.min_face_size}, "
            f"crop_margin_pct={self.crop_margin_pct}, target_size={self.target_size}, "
            f"strategy={self.primary_face_strategy.value}, max_face_ratio={self.max_face_ratio}, "
            f"preserve_aspect={self.preserve_aspect}"
        )

    def crop_face(
        self, image: np.ndarray, face_info: Dict, debug: bool = False
    ) -> Dict:
        """
        Crop a single face from image with enhanced handling

        Args:
            image: Input image (BGR)
            face_info: Face detection info with 'bbox' [x, y, w, h]
            debug: Whether to include debug information

        Returns:
            Dict with cropped face and metadata
        """
        bbox = face_info["bbox"]
        x, y, w, h = bbox

        # Calculate face area ratio
        face_area = w * h
        image_area = image.shape[0] * image.shape[1]
        face_ratio = face_area / image_area

        # Determine crop strategy based on face size
        if face_ratio > self.max_face_ratio:
            # Very large face - use conservative cropping
            crop_result = self._crop_large_face(image, bbox, debug)
        elif min(w, h) < self.min_face_size:
            # Very small face - use expanded cropping
            crop_result = self._crop_small_face(image, bbox, debug)
        else:
            # Normal face - standard cropping
            crop_result = self._crop_standard_face(image, bbox, debug)

        # Resize to target size with aspect preservation
        final_crop = self._resize_to_target(crop_result["cropped_face"], debug)

        return {
            "cropped_face": final_crop,
            "original_bbox": bbox,
            "crop_bbox": crop_result["crop_bbox"],
            "face_ratio": face_ratio,
            "crop_strategy": crop_result["strategy"],
            "resize_info": crop_result.get("resize_info", {}),
            "debug_info": crop_result.get("debug_info", {}) if debug else {},
        }

    def crop_multiple_faces(
        self, image: np.ndarray, faces: List[Dict], debug: bool = False
    ) -> Dict:
        """
        Handle multiple faces using configured strategy

        Args:
            image: Input image
            faces: List of face detection results
            debug: Include debug information

        Returns:
            Dict with primary face crop and metadata
        """
        if not faces:
            raise ValueError("No faces provided for cropping")

        if len(faces) == 1:
            return self.crop_face(image, faces[0], debug)

        # Select primary face using configured strategy
        primary_face = self._select_primary_face(image, faces)

        result = self.crop_face(image, primary_face, debug)
        result["total_faces"] = len(faces)
        result["selection_strategy"] = self.primary_face_strategy.value
        result["selected_face_index"] = faces.index(primary_face)

        if debug:
            result["all_faces"] = [self.crop_face(image, face, debug) for face in faces]

        return result

    def _crop_large_face(self, image: np.ndarray, bbox: List[int], debug: bool) -> Dict:
        """Handle very large faces that occupy most of the frame"""
        x, y, w, h = bbox
        img_h, img_w = image.shape[:2]

        # For large faces, use smaller margin to avoid cutting off features
        conservative_margin = min(self.crop_margin_pct, 0.05)  # Max 5% margin

        # Calculate margins in pixels
        margin_x = int(w * conservative_margin)
        margin_y = int(h * conservative_margin)

        # Ensure we don't go outside image bounds
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(img_w, x + w + margin_x)
        y2 = min(img_h, y + h + margin_y)

        cropped_face = image[y1:y2, x1:x2]

        debug_info = {}
        if debug:
            debug_info = {
                "strategy": "large_face",
                "original_margin_pct": self.crop_margin_pct,
                "applied_margin_pct": conservative_margin,
                "margin_pixels": (margin_x, margin_y),
                "bbox_after_margin": [x1, y1, x2 - x1, y2 - y1],
            }

        return {
            "cropped_face": cropped_face,
            "crop_bbox": [x1, y1, x2 - x1, y2 - y1],
            "strategy": "large_face",
            "debug_info": debug_info,
        }

    def _crop_small_face(self, image: np.ndarray, bbox: List[int], debug: bool) -> Dict:
        """Handle very small faces with expanded context"""
        x, y, w, h = bbox
        img_h, img_w = image.shape[:2]

        # For small faces, use larger margin to capture more context
        expanded_margin = max(self.crop_margin_pct, 0.25)  # At least 25% margin

        # Calculate margins in pixels
        margin_x = int(w * expanded_margin)
        margin_y = int(h * expanded_margin)

        # Ensure minimum crop size
        min_crop_size = max(self.min_face_size * 2, self.target_size // 2)
        current_crop_w = w + 2 * margin_x
        current_crop_h = h + 2 * margin_y

        if current_crop_w < min_crop_size:
            additional_margin_x = (min_crop_size - current_crop_w) // 2
            margin_x += additional_margin_x

        if current_crop_h < min_crop_size:
            additional_margin_y = (min_crop_size - current_crop_h) // 2
            margin_y += additional_margin_y

        # Calculate crop bounds
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(img_w, x + w + margin_x)
        y2 = min(img_h, y + h + margin_y)

        cropped_face = image[y1:y2, x1:x2]

        debug_info = {}
        if debug:
            debug_info = {
                "strategy": "small_face",
                "original_margin_pct": self.crop_margin_pct,
                "applied_margin_pct": expanded_margin,
                "margin_pixels": (margin_x, margin_y),
                "min_crop_size": min_crop_size,
                "final_crop_size": (x2 - x1, y2 - y1),
                "bbox_after_margin": [x1, y1, x2 - x1, y2 - y1],
            }

        return {
            "cropped_face": cropped_face,
            "crop_bbox": [x1, y1, x2 - x1, y2 - y1],
            "strategy": "small_face",
            "debug_info": debug_info,
        }

    def _crop_standard_face(
        self, image: np.ndarray, bbox: List[int], debug: bool
    ) -> Dict:
        """Handle normal-sized faces with standard margin"""
        x, y, w, h = bbox
        img_h, img_w = image.shape[:2]

        # Calculate margins in pixels
        margin_x = int(w * self.crop_margin_pct)
        margin_y = int(h * self.crop_margin_pct)

        # Calculate crop bounds
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(img_w, x + w + margin_x)
        y2 = min(img_h, y + h + margin_y)

        cropped_face = image[y1:y2, x1:x2]

        debug_info = {}
        if debug:
            debug_info = {
                "strategy": "standard",
                "margin_pct": self.crop_margin_pct,
                "margin_pixels": (margin_x, margin_y),
                "bbox_after_margin": [x1, y1, x2 - x1, y2 - y1],
            }

        return {
            "cropped_face": cropped_face,
            "crop_bbox": [x1, y1, x2 - x1, y2 - y1],
            "strategy": "standard",
            "debug_info": debug_info,
        }

    def _resize_to_target(self, cropped_face: np.ndarray, debug: bool) -> np.ndarray:
        """
        Resize cropped face to target size with aspect preservation
        """
        if cropped_face.size == 0:
            # Return black image if crop failed
            return np.zeros((self.target_size, self.target_size, 3), dtype=np.uint8)

        h, w = cropped_face.shape[:2]

        if not self.preserve_aspect:
            # Simple resize without preserving aspect ratio
            return cv2.resize(cropped_face, (self.target_size, self.target_size))

        # Preserve aspect ratio with letterboxing
        scale = min(self.target_size / w, self.target_size / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        # Resize to fit within target size
        resized = cv2.resize(cropped_face, (new_w, new_h))

        # Create letterboxed image
        result = np.zeros((self.target_size, self.target_size, 3), dtype=np.uint8)

        # Calculate padding
        pad_x = (self.target_size - new_w) // 2
        pad_y = (self.target_size - new_h) // 2

        # Place resized image in center
        result[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

        return result

    def _select_primary_face(self, image: np.ndarray, faces: List[Dict]) -> Dict:
        """
        Select primary face using configured strategy
        """
        if self.primary_face_strategy == PrimaryFaceStrategy.LARGEST:
            return max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])

        elif self.primary_face_strategy == PrimaryFaceStrategy.HIGHEST_CONFIDENCE:
            return max(faces, key=lambda f: f.get("confidence", 0))

        elif self.primary_face_strategy == PrimaryFaceStrategy.MOST_CENTERED:
            img_center_x, img_center_y = image.shape[1] / 2, image.shape[0] / 2

            def distance_from_center(face):
                x, y, w, h = face["bbox"]
                face_center_x = x + w / 2
                face_center_y = y + h / 2
                return (
                    (face_center_x - img_center_x) ** 2
                    + (face_center_y - img_center_y) ** 2
                ) ** 0.5

            return min(faces, key=distance_from_center)

        elif self.primary_face_strategy == PrimaryFaceStrategy.BEST_QUALITY:

            def quality_score(face):
                # Combine multiple factors for quality
                confidence = face.get("confidence", 0.5)
                area = face["bbox"][2] * face["bbox"][3]
                has_landmarks = 1.0 if face.get("landmarks") else 0.7

                # Normalize area (prefer medium-sized faces)
                img_area = image.shape[0] * image.shape[1]
                area_ratio = area / img_area
                area_score = 1.0 - abs(area_ratio - 0.15)  # Optimal around 15% of image
                area_score = max(0.1, area_score)

                return confidence * 0.4 + area_score * 0.3 + has_landmarks * 0.3

            return max(faces, key=quality_score)

        # Fallback to largest face
        return max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])

    def validate_crop_result(self, crop_result: Dict) -> bool:
        """
        Validate that crop result is usable
        """
        if "cropped_face" not in crop_result:
            return False

        cropped_face = crop_result["cropped_face"]

        if cropped_face is None or cropped_face.size == 0:
            return False

        h, w = cropped_face.shape[:2]
        if h < self.min_face_size // 2 or w < self.min_face_size // 2:
            return False

        return True

    def get_config_info(self) -> Dict:
        """
        Get current configuration information
        """
        return {
            "min_face_size": self.min_face_size,
            "crop_margin_pct": self.crop_margin_pct,
            "target_size": self.target_size,
            "primary_face_strategy": self.primary_face_strategy.value,
            "max_face_ratio": self.max_face_ratio,
            "preserve_aspect": self.preserve_aspect,
        }
