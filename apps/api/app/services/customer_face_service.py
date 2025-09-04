"""
Customer face image management service for maintaining face galleries
"""

import hashlib
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, delete, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..core.minio_client import minio_client
from ..models.database import CustomerFaceImage, Customer
from ..services.image_processing import image_processor

logger = logging.getLogger(__name__)


class CustomerFaceService:
    """Service for managing customer face image galleries"""
    
    def __init__(self):
        self.max_images_per_customer = settings.max_face_images
        self.min_confidence_to_save = settings.min_face_confidence_to_save
    
    async def add_face_image(
        self,
        db: AsyncSession,
        tenant_id: str,
        customer_id: int,
        image_data: bytes,
        confidence_score: float,
        face_bbox: List[float],
        embedding: List[float],
        visit_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[CustomerFaceImage]:
        """
        Add a face image for a customer, managing gallery size and quality
        
        Args:
            db: Database session
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            image_data: Raw image bytes
            confidence_score: Face detection confidence
            face_bbox: Face bounding box [x, y, w, h]
            embedding: Face embedding vector
            visit_id: Optional source visit ID
            metadata: Additional metadata
            
        Returns:
            Created CustomerFaceImage or None if not saved
        """
        try:
            # Check if confidence meets minimum threshold
            if confidence_score < self.min_confidence_to_save:
                logger.debug(f"Face confidence {confidence_score:.3f} below threshold {self.min_confidence_to_save}, skipping")
                return None
            
            # Calculate image hash for duplicate detection
            image_hash = hashlib.sha256(image_data).hexdigest()
            
            # Check for duplicate image
            result = await db.execute(
                select(CustomerFaceImage).where(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.customer_id == customer_id,
                    CustomerFaceImage.image_hash == image_hash
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.debug(f"Duplicate face image detected for customer {customer_id}, skipping")
                return existing
            
            # Calculate quality score
            quality_score = await self._calculate_quality_score(image_data, face_bbox, metadata)
            
            # Upload image to MinIO
            image_path = await self._upload_face_image(tenant_id, customer_id, image_data)
            if not image_path:
                logger.error("Failed to upload face image to MinIO")
                return None
            
            # Create database record
            face_image = CustomerFaceImage(
                tenant_id=tenant_id,
                customer_id=customer_id,
                image_path=image_path,
                confidence_score=confidence_score,
                quality_score=quality_score,
                face_bbox=face_bbox,
                embedding=embedding,
                image_hash=image_hash,
                visit_id=visit_id,
                detection_metadata=metadata,
                created_at=datetime.utcnow()
            )
            
            db.add(face_image)
            
            # Manage gallery size - keep only the best images
            await self._manage_gallery_size(db, tenant_id, customer_id)
            
            # Don't flush here either - let the calling code handle everything
            
            logger.info(f"Added face image for customer {customer_id} with confidence {confidence_score:.3f}")
            return face_image
            
        except Exception as e:
            # Handle missing table gracefully - this can happen if migrations haven't been run
            if "relation \"customer_face_images\" does not exist" in str(e):
                logger.info(f"customer_face_images table does not exist - cannot save face image for customer {customer_id}")
                return None
            else:
                logger.error(f"Error adding face image for customer {customer_id}: {e}")
                # Don't rollback here - let the calling code handle the transaction
                return None
    
    async def _calculate_quality_score(
        self, 
        image_data: bytes, 
        face_bbox: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calculate overall quality score for a face image"""
        try:
            import numpy as np
            from PIL import Image
            import io
            
            # Open image
            image = Image.open(io.BytesIO(image_data))
            img_array = np.array(image)
            
            # Base quality factors
            quality_factors = []
            
            # Image resolution quality
            width, height = image.size
            resolution_score = min(1.0, (width * height) / (200 * 200))  # 200x200 as baseline
            quality_factors.append(resolution_score * 0.3)
            
            # Face size quality (larger faces generally better)
            if len(face_bbox) >= 4:
                face_w, face_h = face_bbox[2], face_bbox[3]
                face_size_score = min(1.0, min(face_w, face_h) / 100)  # 100px as baseline
                quality_factors.append(face_size_score * 0.3)
            
            # Metadata-based quality
            if metadata:
                # Detector quality bonus
                detector_quality = {
                    'retinaface': 1.0,
                    'mtcnn': 0.9,
                    'mediapipe': 0.85,
                    'opencv_dnn': 0.8,
                    'haar': 0.6
                }.get(metadata.get('detector', ''), 0.7)
                quality_factors.append(detector_quality * 0.2)
                
                # Landmarks bonus
                has_landmarks = 1.0 if metadata.get('landmarks') else 0.7
                quality_factors.append(has_landmarks * 0.2)
            else:
                quality_factors.extend([0.7 * 0.2, 0.7 * 0.2])  # Default values
            
            return sum(quality_factors)
            
        except Exception as e:
            logger.warning(f"Error calculating quality score: {e}")
            return 0.7  # Default quality
    
    async def _upload_face_image(
        self, 
        tenant_id: str, 
        customer_id: int, 
        image_data: bytes
    ) -> Optional[str]:
        """Upload face image to MinIO and return path"""
        try:
            import uuid
            import asyncio
            
            # Generate unique filename with proper path structure
            filename = f"customers/{tenant_id}/{customer_id}/face-{uuid.uuid4().hex[:8]}.jpg"
            
            # Upload to faces-derived bucket (run in executor to avoid blocking)
            def upload_sync():
                return minio_client.upload_image(
                    bucket="faces-derived",
                    object_name=filename,
                    data=image_data,
                    content_type="image/jpeg"
                )
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, upload_sync)
            
            if result:
                # Return the filename without adding extra prefix to avoid duplication
                return filename
            return None
            
        except Exception as e:
            logger.error(f"Error uploading face image: {e}")
            return None
    
    async def _manage_gallery_size(self, db: AsyncSession, tenant_id: str, customer_id: int) -> None:
        """Manage the size of customer face gallery, keeping only the best images"""
        try:
            # Count current committed images (excluding any pending in current transaction)
            # Use a separate query to get the actual committed count
            result = await db.execute(
                select(func.count(CustomerFaceImage.image_id)).where(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.customer_id == customer_id
                )
            )
            current_count = result.scalar()
            
            # The current count includes the newly added image in the session
            # We want to keep max_images_per_customer, so if current_count >= max_images_per_customer,
            # we need to remove (current_count - max_images_per_customer + 1) images
            if current_count < self.max_images_per_customer:
                return
            
            # Calculate excess images to remove  
            # Since current_count includes the new image, we need to remove enough to get back to the limit
            excess_count = current_count - self.max_images_per_customer + 1
            
            logger.info(f"Managing gallery size for customer {customer_id}: current={current_count}, max={self.max_images_per_customer}, removing={excess_count}")
            
            # Get worst images (lowest combined score) excluding the newly added one that's not committed yet
            # We need to get committed images only, so we'll flush first to see the new image, then select the worst
            await db.flush()  # Make sure the new image is visible in queries
            
            result = await db.execute(
                select(CustomerFaceImage).where(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.customer_id == customer_id
                ).order_by(
                    # Combined score: confidence + quality + recency bonus (lower is worse)
                    asc(
                        CustomerFaceImage.confidence_score + 
                        func.coalesce(CustomerFaceImage.quality_score, 0.5) +
                        func.extract('epoch', func.now() - CustomerFaceImage.created_at) / 86400 * 0.01  # Small recency bonus
                    )
                ).limit(excess_count)
            )
            worst_images = result.scalars().all()
            
            # Remove worst images
            for image in worst_images:
                await self._delete_face_image_content_only(image)
                await db.delete(image)
            
            logger.info(f"Removed {len(worst_images)} excess face images for customer {customer_id}")
            
        except Exception as e:
            logger.error(f"Error managing gallery size for customer {customer_id}: {e}")

    async def cleanup_excess_images_for_customer(self, db: AsyncSession, tenant_id: str, customer_id: int) -> int:
        """Clean up excess images for a specific customer, returning count of images removed"""
        try:
            # Get current count
            result = await db.execute(
                select(func.count(CustomerFaceImage.image_id)).where(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.customer_id == customer_id
                )
            )
            current_count = result.scalar()
            
            if current_count <= self.max_images_per_customer:
                return 0
                
            # Calculate how many to remove
            excess_count = current_count - self.max_images_per_customer
            
            # Get worst images to remove
            result = await db.execute(
                select(CustomerFaceImage).where(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.customer_id == customer_id
                ).order_by(
                    asc(
                        CustomerFaceImage.confidence_score + 
                        func.coalesce(CustomerFaceImage.quality_score, 0.5) +
                        func.extract('epoch', func.now() - CustomerFaceImage.created_at) / 86400 * 0.01
                    )
                ).limit(excess_count)
            )
            worst_images = result.scalars().all()
            
            # Remove excess images
            for image in worst_images:
                await self._delete_face_image_content_only(image)
                await db.delete(image)
            
            # Commit the deletions
            await db.commit()
            
            logger.info(f"Cleaned up {len(worst_images)} excess images for customer {customer_id} (had {current_count}, limit {self.max_images_per_customer})")
            return len(worst_images)
            
        except Exception as e:
            logger.error(f"Error cleaning up excess images for customer {customer_id}: {e}")
            await db.rollback()
            return 0

    async def cleanup_all_excess_images(self, db: AsyncSession, tenant_id: str, limit: int = 100) -> dict:
        """Clean up excess images for all customers in a tenant"""
        try:
            # Get customers with too many face images
            result = await db.execute(
                select(
                    CustomerFaceImage.customer_id,
                    func.count(CustomerFaceImage.image_id).label('image_count')
                ).where(
                    CustomerFaceImage.tenant_id == tenant_id
                ).group_by(
                    CustomerFaceImage.customer_id
                ).having(
                    func.count(CustomerFaceImage.image_id) > self.max_images_per_customer
                ).limit(limit)
            )
            
            customers_with_excess = result.all()
            
            total_cleaned = 0
            customers_processed = 0
            
            for customer_row in customers_with_excess:
                customer_id = customer_row.customer_id
                current_count = customer_row.image_count
                
                cleaned = await self.cleanup_excess_images_for_customer(db, tenant_id, customer_id)
                total_cleaned += cleaned
                customers_processed += 1
                
                logger.info(f"Customer {customer_id}: removed {cleaned} excess images (had {current_count})")
            
            return {
                "customers_processed": customers_processed,
                "total_images_cleaned": total_cleaned,
                "max_images_per_customer": self.max_images_per_customer
            }
            
        except Exception as e:
            logger.error(f"Error during bulk cleanup for tenant {tenant_id}: {e}")
            return {
                "customers_processed": 0,
                "total_images_cleaned": 0,
                "error": str(e)
            }
    
    async def _delete_face_image_content_only(self, face_image: CustomerFaceImage) -> None:
        """Delete face image content from MinIO only (not database record)"""
        try:
            # Delete from MinIO (run in executor to avoid blocking)
            if face_image.image_path:
                # Handle both old (customer-faces/ prefix) and new (direct path) formats
                if face_image.image_path.startswith('customer-faces/'):
                    # Legacy format - remove the prefix
                    object_path = face_image.image_path.replace('customer-faces/', '')
                else:
                    # New format - use path directly
                    object_path = face_image.image_path
                
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, 
                        lambda: minio_client.delete_file("faces-derived", object_path)
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete image from MinIO: {e}")
            
        except Exception as e:
            logger.error(f"Error deleting face image content {face_image.image_id}: {e}")

    async def _delete_face_image(self, db: AsyncSession, face_image: CustomerFaceImage) -> None:
        """Delete a face image from both MinIO and database"""
        try:
            # Delete content first
            await self._delete_face_image_content_only(face_image)
            
            # Delete from database
            db.delete(face_image)
            
        except Exception as e:
            logger.error(f"Error deleting face image {face_image.image_id}: {e}")
    
    async def get_customer_face_images(
        self, 
        db: AsyncSession, 
        tenant_id: str, 
        customer_id: int,
        limit: Optional[int] = None
    ) -> List[CustomerFaceImage]:
        """Get face images for a customer, ordered by quality"""
        try:
            query = select(CustomerFaceImage).where(
                CustomerFaceImage.tenant_id == tenant_id,
                CustomerFaceImage.customer_id == customer_id
            ).order_by(
                desc(CustomerFaceImage.confidence_score + 
                     func.coalesce(CustomerFaceImage.quality_score, 0.5))
            )
            
            if limit:
                query = query.limit(limit)
            
            result = await db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            # Handle missing table gracefully - this can happen if migrations haven't been run
            if "relation \"customer_face_images\" does not exist" in str(e):
                logger.info(f"customer_face_images table does not exist - returning empty list for customer {customer_id}")
                return []
            else:
                logger.error(f"Error getting face images for customer {customer_id}: {e}")
                return []
    
    async def get_best_customer_embeddings(
        self, 
        db: AsyncSession, 
        tenant_id: str, 
        customer_id: int,
        max_embeddings: int = 3
    ) -> List[List[float]]:
        """Get the best face embeddings for a customer for recognition comparison"""
        try:
            images = await self.get_customer_face_images(db, tenant_id, customer_id, limit=max_embeddings)
            return [img.embedding for img in images if img.embedding]
            
        except Exception as e:
            logger.error(f"Error getting best embeddings for customer {customer_id}: {e}")
            return []


# Global instance
customer_face_service = CustomerFaceService()