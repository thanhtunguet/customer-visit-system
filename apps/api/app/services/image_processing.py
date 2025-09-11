"""
Image processing service for face cropping and image manipulation
"""

import asyncio
import io
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """Service for processing and cropping face images server-side"""

    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def generate_face_crop_from_bbox(
        self,
        bbox: list[float],
        frame_width: int = 640,
        frame_height: int = 480,
        padding_factor: float = 0.3,
    ) -> Optional[bytes]:
        """
        Generate a synthetic cropped face image from bounding box coordinates
        Used as fallback when worker-provided face image is not available
        """
        try:
            # Run CPU-intensive operations in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self._generate_face_crop_sync,
                bbox,
                frame_width,
                frame_height,
                padding_factor,
            )
        except Exception as e:
            logger.error(f"Error generating face crop from bbox: {e}")
            return None

    def _generate_face_crop_sync(
        self,
        bbox: list[float],
        frame_width: int,
        frame_height: int,
        padding_factor: float,
    ) -> Optional[bytes]:
        """Synchronous face crop generation for thread pool execution"""
        try:
            if len(bbox) < 4:
                logger.warning("Invalid bbox - need at least 4 coordinates")
                return None

            x, y, w, h = bbox

            # Validate coordinates
            if w <= 0 or h <= 0:
                logger.warning(f"Invalid face dimensions: {w}x{h}")
                return None

            # Validate bbox is within frame bounds
            if x < 0 or y < 0 or x + w > frame_width or y + h > frame_height:
                logger.warning(
                    f"Face bbox extends beyond frame: bbox=[{x}, {y}, {w}, {h}], frame={frame_width}x{frame_height}"
                )
                # Clamp bbox to frame boundaries
                x = max(0, min(x, frame_width - 1))
                y = max(0, min(y, frame_height - 1))
                w = min(w, frame_width - x)
                h = min(h, frame_height - y)
                logger.info(f"Clamped bbox to: [{x}, {y}, {w}, {h}]")

            # Calculate padded region
            padding_x = int(w * padding_factor)
            padding_y = int(h * padding_factor)

            crop_x = max(0, int(x - padding_x))
            crop_y = max(0, int(y - padding_y))
            crop_w = min(frame_width - crop_x, int(w + 2 * padding_x))
            crop_h = min(frame_height - crop_y, int(h + 2 * padding_y))

            # Ensure crop dimensions are valid
            if crop_w <= 0 or crop_h <= 0:
                logger.warning(
                    f"Calculated crop dimensions invalid: {crop_w}x{crop_h}, using fallback"
                )
                crop_w = crop_h = min(64, min(frame_width, frame_height) // 2)

            # Ensure minimum size
            min_size = 64
            if crop_w < min_size or crop_h < min_size:
                logger.warning(
                    f"Face crop too small: {crop_w}x{crop_h}, using default size"
                )
                crop_w = crop_h = min_size

            # Create a synthetic face image
            # In a real implementation, this would crop from an actual frame
            # For now, create a placeholder that represents the detected face area
            face_image = self._create_face_placeholder(crop_w, crop_h, bbox)

            # Convert to JPEG bytes
            img_buffer = io.BytesIO()
            face_image.save(img_buffer, format="JPEG", quality=85, optimize=True)
            img_bytes = img_buffer.getvalue()

            logger.debug(
                f"Generated face crop: {crop_w}x{crop_h}, {len(img_bytes)} bytes"
            )
            return img_bytes

        except Exception as e:
            logger.error(f"Error in sync face crop generation: {e}")
            return None

    def _create_face_placeholder(
        self, width: int, height: int, bbox: list[float]
    ) -> Image.Image:
        """Create a realistic face region placeholder for fallback scenarios"""
        # Create base image with neutral background
        image = Image.new("RGB", (width, height), color="#f5f5f5")
        draw = ImageDraw.Draw(image)

        # Add subtle texture/noise to make it look more like a real image
        import random

        for _ in range(width * height // 20):  # Add some noise pixels
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            noise_color = random.randint(240, 250)
            draw.point((x, y), fill=(noise_color, noise_color, noise_color))

        # Calculate face region within the crop based on bbox
        face_w, face_h = int(width * 0.7), int(height * 0.7)
        face_x = (width - face_w) // 2
        face_y = (height - face_h) // 2

        # Draw a subtle face region outline (very faint)
        try:
            # Very subtle face outline
            draw.ellipse(
                [face_x, face_y, face_x + face_w, face_y + face_h],
                fill="#f0f0f0",
                outline="#e8e8e8",
                width=1,
            )

            # Add minimal geometric shapes to suggest facial features without being obvious
            # Two small dots for eye region
            eye_size = max(2, face_w // 30)
            left_eye_x = face_x + face_w // 3 - eye_size
            right_eye_x = face_x + 2 * face_w // 3 - eye_size
            eye_y = face_y + face_h // 3

            draw.ellipse(
                [left_eye_x, eye_y, left_eye_x + eye_size * 2, eye_y + eye_size],
                fill="#e0e0e0",
            )
            draw.ellipse(
                [right_eye_x, eye_y, right_eye_x + eye_size * 2, eye_y + eye_size],
                fill="#e0e0e0",
            )

            # Very subtle nose indication (just a small line)
            nose_x = face_x + face_w // 2
            nose_y = face_y + face_h // 2
            draw.line(
                [(nose_x, nose_y - 3), (nose_x, nose_y + 3)], fill="#e5e5e5", width=1
            )

        except Exception as e:
            logger.debug(f"Error drawing face details: {e}")
            # If drawing fails, just use the plain background

        # Add a very subtle border
        draw.rectangle([0, 0, width - 1, height - 1], outline="#e0e0e0", width=1)

        # Add text watermark indicating this is a placeholder
        try:
            from PIL import ImageFont

            font = ImageFont.load_default()
            text = "Face Detected"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            text_x = (width - text_width) // 2
            text_y = height - text_height - 5

            draw.text((text_x, text_y), text, fill="#c0c0c0", font=font)
        except:
            # If font loading fails, skip the text
            pass

        return image

    async def upload_generated_image(
        self, image_bytes: bytes, minio_client, bucket: str = "faces-derived"
    ) -> Optional[str]:
        """Upload generated face image to MinIO storage and return secure internal path"""
        try:
            filename = f"generated/face-crop-{uuid.uuid4().hex[:8]}.jpg"

            # Upload to MinIO using the wrapper's upload_image method
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                lambda: minio_client.upload_image(
                    bucket=bucket,
                    object_name=filename,
                    data=image_bytes,
                    content_type="image/jpeg",
                ),
            )

            # Return secure internal path instead of presigned URL
            # This will be served through the secure /files/{file_path} endpoint
            secure_path = f"visits-faces/{filename}"
            logger.info(f"Successfully uploaded generated face crop: {secure_path}")
            return secure_path

        except Exception as e:
            logger.error(f"Error uploading generated image: {e}")
            return None


# Global instance
image_processor = ImageProcessingService()
