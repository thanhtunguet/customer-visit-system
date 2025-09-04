from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.milvus_client import milvus_client
from ..core.config import settings
from ..models.database import Customer, Staff, Visit
from common.models import FaceDetectedEvent

logger = logging.getLogger(__name__)


class FaceMatchingService:
    def __init__(self):
        self.similarity_threshold = 0.6
        self.max_search_results = 5

    async def process_face_event(
        self, 
        event: FaceDetectedEvent, 
        db_session: AsyncSession,
        tenant_id: int
    ) -> Dict:
        """Process a face detection event and return matching results"""
        
        # Skip if it's already identified as staff locally
        if event.is_staff_local:
            return {
                "match": "staff",
                "person_id": None,
                "similarity": 1.0,
                "visit_id": None,
                "message": "Staff member identified locally"
            }

        # Search for similar faces in Milvus
        similar_faces = await milvus_client.search_similar_faces(
            tenant_id=tenant_id,
            embedding=event.embedding,
            limit=self.max_search_results,
            threshold=self.similarity_threshold,
        )

        person_id = None
        person_type = "customer"
        similarity = 0.0
        match_type = "new"

        if similar_faces:
            # Use the best match
            best_match = similar_faces[0]
            person_id = best_match["person_id"]
            person_type = best_match["person_type"]
            similarity = best_match["similarity"]
            match_type = "known"

            logger.info(f"Found match: {person_id} with similarity {similarity}")
        else:
            # Create new customer
            person_id = await self._create_new_customer(db_session, tenant_id)
            person_type = "customer"
            logger.info(f"Created new customer: {person_id}")

        # Store the embedding in Milvus
        current_time = int(time.time())
        await milvus_client.insert_embedding(
            tenant_id=tenant_id,
            person_id=person_id,
            person_type=person_type,
            embedding=event.embedding,
            created_at=current_time,
        )

        # Create visit record
        visit_id = await self._create_visit_record(
            db_session=db_session,
            tenant_id=tenant_id,
            event=event,
            person_id=person_id,
            person_type=person_type,
            confidence_score=similarity,
        )

        # Update customer last_seen
        if person_type == "customer":
            await self._update_customer_last_seen(db_session, tenant_id, person_id)

        return {
            "match": match_type,
            "person_id": person_id,
            "similarity": similarity,
            "visit_id": visit_id,
            "person_type": person_type
        }

    async def process_face_event_with_image(
        self, 
        event: FaceDetectedEvent, 
        face_image_data: bytes,
        face_image_filename: str,
        db_session: AsyncSession,
        tenant_id: int
    ) -> Dict:
        """Process a face detection event with uploaded face image and return matching results"""
        
        # First upload the face image to MinIO
        from ..core.minio_client import minio_client
        import uuid
        
        try:
            # Generate unique filename for the face image
            file_extension = face_image_filename.split('.')[-1] if '.' in face_image_filename else 'jpg'
            object_name = f"worker-faces/face-{uuid.uuid4().hex[:8]}.{file_extension}"
            
            # Upload to faces-raw bucket (will be cleaned up after 30 days)
            result = await asyncio.get_event_loop().run_in_executor(
                None, 
                minio_client.upload_image,
                "faces-raw", 
                object_name,
                face_image_data,
                f"image/{file_extension}"
            )
            
            if result:
                # Update the event with the uploaded image path
                event.snapshot_url = object_name
                logger.info(f"Successfully uploaded worker face image: {object_name}")
            else:
                logger.warning("Failed to upload worker face image, continuing without image")
                
        except Exception as e:
            logger.warning(f"Failed to upload worker face image: {e}")
            # Continue processing without the image - it's not critical
        
        # Now process the event normally
        return await self.process_face_event(event, db_session, tenant_id)

    async def _create_new_customer(
        self, 
        db_session: AsyncSession, 
        tenant_id: int
    ) -> int:
        """Create a new customer record and return the auto-generated customer_id"""
        customer = Customer(
            tenant_id=tenant_id,
            first_seen=datetime.utcnow(),
            visit_count=0,
        )
        db_session.add(customer)
        await db_session.flush()  # This will populate the customer_id
        return customer.customer_id

    async def _create_visit_record(
        self,
        db_session: AsyncSession,
        tenant_id: int,
        event: FaceDetectedEvent,
        person_id: int,
        person_type: str,
        confidence_score: float,
    ) -> str:
        """Create or update a visit record with session-based deduplication"""
        from datetime import timedelta
        
        visit_merge_window = timedelta(minutes=30)  # 30-minute merge window
        current_time = event.timestamp.replace(tzinfo=None) if event.timestamp.tzinfo else event.timestamp
        
        # Convert snapshot_url to string if present
        image_path = str(event.snapshot_url) if event.snapshot_url else None
        
        # Handle face image saving for customer gallery
        face_image_bytes = None
        if event.snapshot_url and person_type == "customer":
            # Try to download actual face crop from worker-provided snapshot
            try:
                from ..core.minio_client import minio_client
                if event.snapshot_url.startswith('worker-faces/'):
                    # Use the full path as stored in MinIO
                    face_image_bytes = await minio_client.download_file("faces-raw", event.snapshot_url)
                    logger.debug(f"Downloaded worker face image: {len(face_image_bytes)} bytes")
            except Exception as e:
                logger.warning(f"Failed to download worker face image: {e}")
        
        # If no snapshot URL provided, try to generate a fallback cropped face image
        logger.info(f"Processing event: snapshot_url={'Present' if event.snapshot_url else 'None'}, bbox={event.bbox}")
        if not image_path and event.bbox and len(event.bbox) >= 4:
            logger.info("Attempting to generate fallback face crop from bbox")
            try:
                from .image_processing import image_processor
                from ..core.minio_client import minio_client
                
                # Generate synthetic face crop from bbox
                face_crop_bytes = await image_processor.generate_face_crop_from_bbox(
                    bbox=event.bbox,
                    frame_width=640,  # Default camera resolution
                    frame_height=480,
                    padding_factor=0.3
                )
                
                if face_crop_bytes:
                    # Upload the generated image  
                    image_path = await image_processor.upload_generated_image(
                        image_bytes=face_crop_bytes,
                        minio_client=minio_client,
                        bucket="faces-derived"
                    )
                    
                    if image_path:
                        logger.info(f"✅ Generated fallback face crop for visit: {image_path}")
                        face_image_bytes = face_crop_bytes  # Use for customer gallery too
                    else:
                        logger.warning("❌ Failed to upload generated face crop")
                        
            except Exception as e:
                logger.error(f"❌ Failed to generate fallback face image: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Continue without image - not critical
        
        # Look for existing visit session within the merge window
        cutoff_time = current_time - visit_merge_window
        
        existing_visit_query = select(Visit).where(
            Visit.tenant_id == tenant_id,
            Visit.person_id == person_id,
            Visit.person_type == person_type,
            Visit.site_id == event.site_id,
            Visit.last_seen >= cutoff_time
        ).order_by(Visit.last_seen.desc()).limit(1)
        
        result = await db_session.execute(existing_visit_query)
        existing_visit = result.scalar_one_or_none()
        
        if existing_visit:
            # Update existing visit session
            duration_seconds = int((current_time - existing_visit.first_seen).total_seconds())
            
            # Update fields
            existing_visit.last_seen = current_time
            existing_visit.visit_duration_seconds = duration_seconds
            existing_visit.detection_count += 1
            
            # Store the original confidence for comparison
            original_confidence = existing_visit.confidence_score
            
            # Update confidence score if this detection is better
            if confidence_score > (existing_visit.highest_confidence or 0):
                existing_visit.highest_confidence = confidence_score
                existing_visit.confidence_score = confidence_score  # Update main confidence too
                
            # Update image path if this detection has an image and previous didn't, or if confidence is higher
            if image_path and (not existing_visit.image_path or confidence_score > original_confidence):
                existing_visit.image_path = image_path
                # Update bounding box info for the best detection
                existing_visit.bbox_x = event.bbox[0] if len(event.bbox) >= 4 else None
                existing_visit.bbox_y = event.bbox[1] if len(event.bbox) >= 4 else None
                existing_visit.bbox_w = event.bbox[2] if len(event.bbox) >= 4 else None
                existing_visit.bbox_h = event.bbox[3] if len(event.bbox) >= 4 else None
                existing_visit.face_embedding = json.dumps(event.embedding)
            
            await db_session.commit()
            
            # Save face image to customer gallery if we have high quality image
            if person_type == "customer" and face_image_bytes and confidence_score >= 0.7:
                try:
                    await self._save_customer_face_image(
                        db_session, tenant_id, person_id, face_image_bytes, 
                        confidence_score, event.bbox, event.embedding, existing_visit.visit_id
                    )
                except Exception as e:
                    # Don't let face gallery errors break the main transaction
                    logger.warning(f"Failed to save customer face image, continuing: {e}")
            
            logger.info(f"Updated existing visit session {existing_visit.visit_session_id}: "
                       f"duration={duration_seconds}s, detections={existing_visit.detection_count}, "
                       f"confidence={existing_visit.highest_confidence:.3f}, image_path={'Yes' if existing_visit.image_path else 'No'}")
            
            return existing_visit.visit_id
        else:
            # Create new visit session
            visit_id = f"v_{uuid.uuid4().hex[:8]}"
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            
            visit = Visit(
                tenant_id=tenant_id,
                visit_id=visit_id,
                visit_session_id=session_id,
                person_id=person_id,
                person_type=person_type,
                site_id=event.site_id,
                camera_id=event.camera_id,
                timestamp=current_time,
                first_seen=current_time,
                last_seen=current_time,
                visit_duration_seconds=0,
                detection_count=1,
                confidence_score=confidence_score,
                highest_confidence=confidence_score,
                face_embedding=json.dumps(event.embedding),
                image_path=image_path,
                bbox_x=event.bbox[0] if len(event.bbox) >= 4 else None,
                bbox_y=event.bbox[1] if len(event.bbox) >= 4 else None,
                bbox_w=event.bbox[2] if len(event.bbox) >= 4 else None,
                bbox_h=event.bbox[3] if len(event.bbox) >= 4 else None,
            )
            
            db_session.add(visit)
            await db_session.commit()
            
            # Save face image to customer gallery if we have high quality image
            if person_type == "customer" and face_image_bytes and confidence_score >= 0.7:
                try:
                    await self._save_customer_face_image(
                        db_session, tenant_id, person_id, face_image_bytes, 
                        confidence_score, event.bbox, event.embedding, visit_id
                    )
                except Exception as e:
                    # Don't let face gallery errors break the main transaction
                    logger.warning(f"Failed to save customer face image, continuing: {e}")
            
            logger.info(f"Created new visit session {session_id} for person {person_id}, image_path={'Yes' if image_path else 'No'}")
            
            return visit_id

    async def _update_customer_last_seen(
        self, 
        db_session: AsyncSession, 
        tenant_id: int, 
        customer_id: int
    ):
        """Update customer's last seen timestamp and visit count"""
        stmt = (
            update(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.customer_id == customer_id)
            .values(
                last_seen=datetime.utcnow(),
                visit_count=Customer.visit_count + 1,
            )
        )
        await db_session.execute(stmt)
        await db_session.commit()

    async def _save_customer_face_image(
        self,
        db_session: AsyncSession,
        tenant_id: str,
        customer_id: int,
        face_image_bytes: bytes,
        confidence_score: float,
        bbox: List[float],
        embedding: List[float],
        visit_id: str
    ):
        """Save face image to customer gallery"""
        try:
            from .customer_face_service import customer_face_service
            from ..core.database import get_db_session
            
            # Use the existing database session - customer face service will handle its own transactions
            # Extract metadata for quality assessment
            metadata = {
                'source': 'worker_detection',
                'visit_id': visit_id,
                'bbox': bbox
            }
            
            result = await customer_face_service.add_face_image(
                db=db_session,
                tenant_id=tenant_id,
                customer_id=customer_id,
                image_data=face_image_bytes,
                confidence_score=confidence_score,
                face_bbox=bbox,
                embedding=embedding,
                visit_id=visit_id,
                metadata=metadata
            )
            
            if result:
                logger.info(f"✅ Saved face image to customer {customer_id} gallery with confidence {confidence_score:.3f}")
            else:
                logger.debug(f"⚠️ Face image not saved to customer {customer_id} gallery (quality/duplicate)")
                
        except Exception as e:
            logger.error(f"❌ Error saving face image to customer gallery: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")


class StaffService:
    async def enroll_staff_member(
        self,
        db_session: AsyncSession,
        tenant_id: int,
        staff_id: int,
        name: str,
        face_embedding: List[float],
        site_id: Optional[int] = None,
        update_existing: bool = False,
    ) -> Staff:
        """Enroll a new staff member with face embedding"""
        
        # If updating, delete existing embeddings first
        if update_existing:
            try:
                await milvus_client.delete_person_embeddings(tenant_id, staff_id)
            except Exception as e:
                logger.warning(f"Failed to delete existing staff embeddings: {e}")
        
        # Store embedding in Milvus
        current_time = int(time.time())
        await milvus_client.insert_embedding(
            tenant_id=tenant_id,
            person_id=staff_id,
            person_type="staff",
            embedding=face_embedding,
            created_at=current_time,
        )

        if update_existing:
            # Update existing staff record
            result = await db_session.execute(
                select(Staff).where(
                    and_(Staff.tenant_id == tenant_id, Staff.staff_id == staff_id)
                )
            )
            staff = result.scalar_one()
            staff.face_embedding = json.dumps(face_embedding)
        else:
            # Create new staff record
            staff = Staff(
                tenant_id=tenant_id,
                staff_id=staff_id,
                name=name,
                site_id=site_id,
                face_embedding=json.dumps(face_embedding),
            )
            db_session.add(staff)
        
        await db_session.commit()
        return staff

    async def get_staff_embeddings_for_site(
        self,
        db_session: AsyncSession,
        tenant_id: int,
        site_id: int,
    ) -> List[Dict]:
        """Get all staff embeddings for a specific site"""
        stmt = select(Staff).where(
            Staff.tenant_id == tenant_id,
            Staff.site_id == site_id,
            Staff.is_active == True,
        )
        result = await db_session.execute(stmt)
        staff_members = result.scalars().all()
        
        return [
            {
                "staff_id": staff.staff_id,
                "name": staff.name,
                "embedding": json.loads(staff.face_embedding) if staff.face_embedding else [],
            }
            for staff in staff_members
            if staff.face_embedding
        ]


# Service instances
face_service = FaceMatchingService()
staff_service = StaffService()