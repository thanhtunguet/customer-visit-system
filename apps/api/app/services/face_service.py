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
        # Read thresholds and knobs from settings
        self.max_search_results = 10
        self.staff_similarity_threshold = 0.8
        self.embedding_distance_thr = settings.embedding_distance_thr
        self.merge_distance_thr = settings.merge_distance_thr
        self.merge_margin = settings.merge_margin
        self.min_cluster_samples = settings.min_cluster_samples
        self.min_track_length = settings.min_track_length
        self.temporal_hysteresis_secs = settings.temporal_hysteresis_secs
        self.min_confidence_score = settings.quality_min_score

        # In-memory caches for smoothing / clustering (best-effort, per-process)
        # recent_assignments[(tenant_id, camera_id)] = (person_id, timestamp, similarity)
        self.recent_assignments: dict[tuple[str, int], tuple[int, float, float]] = {}
        # pending clusters keyed by coarse hash of embedding
        # pending[(tenant_id, site_id, camera_id, key)] = [(ts, embedding)]
        self.pending: dict[tuple[str, int, int, str], list[tuple[float, list[float]]]] = {}
        self.pending_window_secs = 5.0
        
        self.debug_mode = True

    async def process_face_event(
        self, 
        event: FaceDetectedEvent, 
        db_session: AsyncSession,
        tenant_id: int
    ) -> Dict:
        """Process a face detection event and return matching results"""
        
        # Enhanced logging for debugging
        is_manual_upload = hasattr(event, '_manual_face_data')
        filename = getattr(event, '_manual_filename', 'camera_stream')
        logger.info(f"🔍 Processing face event from {filename}: confidence={event.confidence:.3f}, bbox={event.bbox}, manual_upload={is_manual_upload}")
        logger.info(f"🔍 Thresholds: similarity={self.similarity_threshold}, customer_merge={self.customer_merge_threshold}, min_confidence={self.min_confidence_score}")
        
        # Skip if it's already identified as staff locally
        if event.is_staff_local:
            logger.info(f"Staff member identified locally: {event.staff_id}")
            return {
                "match": "staff",
                "person_id": event.staff_id,
                "similarity": 1.0,
                "visit_id": None,
                "message": "Staff member identified locally"
            }

        # Quality check - reject low confidence detections
        if event.confidence < self.min_confidence_score:
            logger.warning(f"Rejecting low confidence detection: {event.confidence:.3f} < {self.min_confidence_score}")
            return {
                "match": "rejected",
                "person_id": None,
                "similarity": 0.0,
                "visit_id": None,
                "message": f"Detection quality too low: {event.confidence:.3f}"
            }

        # Determine search and decision thresholds
        is_manual_upload = hasattr(event, '_manual_face_data')
        search_threshold = self.embedding_distance_thr if not is_manual_upload else max(self.merge_distance_thr, 0.95)
        logger.info(
            f"🔍 Thresholds: search={search_threshold:.3f}, merge={self.merge_distance_thr:.3f}, "
            f"margin={self.merge_margin:.3f}, min_conf={self.min_confidence_score:.2f}"
        )
        logger.info(f"🔍 Searching Milvus for similar faces (limit={self.max_search_results})")
        similar_faces = await milvus_client.search_similar_faces(
            tenant_id=tenant_id,
            embedding=event.embedding,
            limit=self.max_search_results,
            threshold=search_threshold,
        )
        logger.info(f"🔍 Milvus returned {len(similar_faces)} similar faces")
        for i, face in enumerate(similar_faces):
            logger.info(f"🔍   - Match {i+1}: Person {face['person_id']} (similarity: {face['similarity']:.3f})")

        person_id = None
        person_type = "customer"
        similarity = 0.0
        match_type = "new"

        if similar_faces:
            best_match = similar_faces[0]
            best_sim = float(best_match.get("similarity", 0.0))
            second_sim = float(similar_faces[1].get("similarity", 0.0)) if len(similar_faces) > 1 else 0.0
            logger.info(
                f"🔍 Best match: {best_match['person_type']} {best_match['person_id']} sim={best_sim:.3f} (second={second_sim:.3f})"
            )

            # Merge-on-recognition: strong match
            if best_match["person_type"] == "customer" and best_sim >= self.merge_distance_thr:
                person_id = best_match["person_id"]
                person_type = "customer"
                similarity = best_sim
                match_type = "known"
                logger.info(f"🟢 Strong match >= merge threshold: customer {person_id}")
            # Margin-based assignment: best above search threshold and clear margin over second best
            elif best_match["person_type"] == "customer" and best_sim >= self.embedding_distance_thr and (best_sim - second_sim) >= self.merge_margin:
                person_id = best_match["person_id"]
                person_type = "customer"
                similarity = best_sim
                match_type = "known"
                logger.info(f"🟢 Margin-based assignment to existing customer {person_id}")
            else:
                # Temporal hysteresis: prefer last identity for this camera if close
                cache_key = (str(tenant_id), int(event.camera_id))
                now_ts = time.time()
                last = self.recent_assignments.get(cache_key)
                if last:
                    last_person_id, last_ts, last_sim = last
                    if (now_ts - last_ts) <= self.temporal_hysteresis_secs and best_match["person_type"] == "customer" and best_sim >= self.embedding_distance_thr:
                        person_id = best_match["person_id"]
                        person_type = "customer"
                        similarity = best_sim
                        match_type = "known"
                        logger.info(f"🟡 Hysteresis kept identity {person_id} within {self.temporal_hysteresis_secs}s")

        if not person_id:
            # Cluster gating: require min samples within small window before creating a new customer
            def _coarse_key(vec: List[float]) -> str:
                # Round first 16 dims to 2 decimals as coarse signature
                return ",".join(f"{v:.2f}" for v in vec[:16])

            pkey = (str(tenant_id), int(event.site_id), int(event.camera_id), _coarse_key(event.embedding))
            now_ts = time.time()
            window = self.pending_window_secs
            lst = self.pending.get(pkey, [])
            # prune old
            lst = [(ts, emb) for ts, emb in lst if (now_ts - ts) <= window]
            lst.append((now_ts, event.embedding))
            self.pending[pkey] = lst

            if len(lst) >= self.min_cluster_samples:
                logger.info(f"🆕 Creating new customer after cluster min_samples={self.min_cluster_samples}")
                person_id = await self._create_new_customer(db_session, tenant_id)
                person_type = "customer"
            else:
                # Not enough evidence; treat as rejected to avoid over-segmentation
                logger.info(
                    f"⏳ Deferring new customer creation: {len(lst)}/{self.min_cluster_samples} samples in {window}s"
                )
                return {
                    "match": "rejected",
                    "person_id": None,
                    "similarity": 0.0,
                    "visit_id": None,
                    "person_type": "customer",
                    "message": "Insufficient samples for new identity"
                }

        # Store the embedding in Milvus (with quality check)
        if event.confidence >= self.min_confidence_score:
            current_time = int(time.time())
            await milvus_client.insert_embedding(
                tenant_id=tenant_id,
                person_id=person_id,
                person_type=person_type,
                embedding=event.embedding,
                created_at=current_time,
            )
            logger.info(f"Stored embedding for {person_type} {person_id} with confidence {event.confidence:.3f}")

        # Create visit record (this will commit the customer and visit together)
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

        # Update recent assignment cache for hysteresis
        try:
            self.recent_assignments[(str(tenant_id), int(event.camera_id))] = (
                int(person_id), time.time(), float(similarity)
            )
        except Exception:
            pass

        result = {
            "match": match_type,
            "person_id": person_id,
            "similarity": similarity,
            "visit_id": visit_id,
            "person_type": person_type
        }
        
        logger.info(f"Face processing complete: {result}")
        return result

    async def process_face_event_with_image(
        self, 
        event: FaceDetectedEvent, 
        face_image_data: bytes,
        face_image_filename: str,
        db_session: AsyncSession,
        tenant_id: int
    ) -> Dict:
        """Process a face detection event with uploaded face image and return matching results"""
        
        # Store the face image data directly on the event for later use
        # This avoids unnecessary upload/download cycles
        event._manual_face_data = face_image_data
        
        # Add filename for tracking
        event._manual_filename = face_image_filename
        
        # Process the event normally (this will handle face matching and visit creation)
        result = await self.process_face_event(event, db_session, tenant_id)
        
        # Clean up the temporary data
        delattr(event, '_manual_face_data')
        if hasattr(event, '_manual_filename'):
            delattr(event, '_manual_filename')
        
        return result

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
        await db_session.flush()  # This will populate the customer_id but not commit
        logger.info(f"Created new customer record (not yet committed): {customer.customer_id}")
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

        # Handle face image saving for customer gallery and visit snapshot
        face_image_bytes = None

        # Prefer manual uploaded crop when available (manual import flow)
        if hasattr(event, '_manual_face_data') and person_type == "customer":
            face_image_bytes = event._manual_face_data
            logger.debug(f"Using manual upload face data: {len(face_image_bytes)} bytes")
        elif event.snapshot_url and person_type == "customer":
            # Try to download actual face crop from worker-provided snapshot
            try:
                from ..core.minio_client import minio_client
                if event.snapshot_url.startswith('worker-faces/'):
                    face_image_bytes = await minio_client.download_file("faces-raw", event.snapshot_url)
                    logger.debug(f"Downloaded face image: {len(face_image_bytes)} bytes")
            except Exception as e:
                logger.warning(f"Failed to download face image: {e}")

        # If we have a real cropped face (manual or worker) but no visit image yet, upload it for the visit
        if not image_path and face_image_bytes:
            try:
                from ..core.minio_client import minio_client
                # Store visit snapshots in faces-derived bucket and reference with visits-faces/ prefix
                object_name = f"visits/{tenant_id}/{uuid.uuid4().hex[:8]}.jpg"

                # Run upload sync in default thread to avoid blocking event loop
                def _upload_sync():
                    return minio_client.upload_image(
                        bucket="faces-derived",
                        object_name=object_name,
                        data=face_image_bytes,
                        content_type="image/jpeg",
                    )

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _upload_sync)
                image_path = f"visits-faces/{object_name}"
                logger.info(f"✅ Uploaded visit face snapshot: {image_path}")
            except Exception as e:
                logger.warning(f"Failed to upload visit face snapshot, will try fallback: {e}")

        # If still no snapshot URL, try to generate a fallback cropped face image from bbox
        logger.info(f"Processing event: snapshot_url={'Present' if event.snapshot_url else 'None'}, bbox={event.bbox}")
        if not image_path and event.bbox and len(event.bbox) >= 4:
            logger.info("Attempting to generate fallback face crop from bbox")
            try:
                from .image_processing import image_processor
                from ..core.minio_client import minio_client

                face_crop_bytes = await image_processor.generate_face_crop_from_bbox(
                    bbox=event.bbox,
                    frame_width=640,  # Default camera resolution
                    frame_height=480,
                    padding_factor=0.3,
                )

                if face_crop_bytes:
                    image_path = await image_processor.upload_generated_image(
                        image_bytes=face_crop_bytes,
                        minio_client=minio_client,
                        bucket="faces-derived",
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
            
            # Save face image to customer gallery if we have image data
            # Use original detection confidence; allow manual uploads at lower threshold via service policy
            if person_type == "customer" and face_image_bytes:
                try:
                    await self._save_customer_face_image(
                        db_session, tenant_id, person_id, face_image_bytes, 
                        event.confidence, event.bbox, event.embedding, existing_visit.visit_id,
                        manual_upload=hasattr(event, '_manual_face_data')
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
            
            # Save face image to customer gallery if we have image data
            # Use original detection confidence; allow manual uploads at lower threshold via service policy
            if person_type == "customer" and face_image_bytes:
                try:
                    await self._save_customer_face_image(
                        db_session, tenant_id, person_id, face_image_bytes, 
                        event.confidence, event.bbox, event.embedding, visit_id,
                        manual_upload=hasattr(event, '_manual_face_data')
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
        visit_id: str,
        manual_upload: bool = False,
    ):
        """Save face image to customer gallery using a fresh database session"""
        fresh_session = None
        try:
            from .customer_face_service import customer_face_service
            from ..core.database import get_db_session
            import asyncio
            
            # Add a small delay to ensure the main transaction is fully committed
            # This helps avoid race conditions with fresh database sessions
            await asyncio.sleep(0.1)
            
            # Get a fresh database session to avoid rollback issues
            # The customer should already be committed at this point
            fresh_session_generator = get_db_session()
            fresh_session = await fresh_session_generator.__anext__()
            
            # Set tenant context for the fresh session
            from ..core.database import db
            await db.set_tenant_context(fresh_session, tenant_id)
            
            # Extract metadata for quality assessment
            metadata = {
                'source': 'manual_upload' if manual_upload else 'worker_detection',
                'visit_id': visit_id,
                'bbox': bbox,
            }
            
            logger.info(f"🖼️ Attempting to save face image to customer {customer_id} gallery: confidence={confidence_score:.3f}, manual_upload={manual_upload}, bytes={len(face_image_bytes)}")
            
            result = await customer_face_service.add_face_image(
                db=fresh_session,
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
                # Commit the fresh session
                await fresh_session.commit()
                logger.info(f"✅ Saved face image to customer {customer_id} gallery with confidence {confidence_score:.3f} (manual_upload={manual_upload})")
            else:
                logger.debug(f"⚠️ Face image not saved to customer {customer_id} gallery (quality/duplicate/below_threshold)")
                
        except Exception as e:
            logger.error(f"❌ Error saving face image to customer gallery: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Don't re-raise - this is a non-critical operation
        finally:
            # Clean up the fresh session
            if fresh_session:
                try:
                    await fresh_session.close()
                except Exception as cleanup_error:
                    logger.warning(f"Error closing fresh session: {cleanup_error}")
            # Don't re-raise - this is a non-critical operation
            # Don't re-raise - this is a non-critical operation

    async def cleanup_duplicate_embeddings(self, db_session: AsyncSession, tenant_id: int) -> Dict[str, int]:
        """
        Clean up duplicate embeddings for customers to improve accuracy
        This method identifies and removes embeddings that are too similar for the same customer
        """
        logger.info(f"Starting embedding cleanup for tenant {tenant_id}")
        
        cleanup_stats = {
            "customers_processed": 0,
            "embeddings_removed": 0,
            "customers_merged": 0
        }
        
        try:
            # Get all customer IDs for this tenant
            customer_query = select(Customer.customer_id).where(Customer.tenant_id == tenant_id)
            result = await db_session.execute(customer_query)
            customer_ids = [row[0] for row in result.scalars().all()]
            
            logger.info(f"Found {len(customer_ids)} customers to process")
            
            for customer_id in customer_ids:
                # This is a placeholder for the cleanup logic
                # In production, you'd implement logic to:
                # 1. Get all embeddings for this customer from Milvus
                # 2. Calculate similarities between embeddings
                # 3. Remove duplicates that are too similar (>0.95 similarity)
                # 4. Keep the highest quality embedding
                cleanup_stats["customers_processed"] += 1
                
            logger.info(f"Cleanup complete: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Embedding cleanup failed: {e}")
            return cleanup_stats

    async def debug_customer_embeddings(self, tenant_id: int, customer_id: int) -> Dict:
        """
        Debug function to analyze embeddings for a specific customer
        """
        try:
            # Search for all embeddings for this customer
            debug_info = {
                "customer_id": customer_id,
                "tenant_id": tenant_id,
                "embedding_count": 0,
                "similarity_analysis": []
            }
            
            # Use Milvus to get embeddings for this specific customer
            # This would require extending MilvusClient with a query by person_id method
            logger.info(f"Debug analysis for customer {customer_id}: {debug_info}")
            
            return debug_info
            
        except Exception as e:
            logger.error(f"Debug analysis failed for customer {customer_id}: {e}")
            return {"error": str(e)}


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
