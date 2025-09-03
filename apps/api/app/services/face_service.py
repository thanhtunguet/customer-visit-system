from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.milvus_client import milvus_client
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
        """Create a visit record"""
        visit_id = f"v_{uuid.uuid4().hex[:8]}"
        
        # Convert snapshot_url to string if present
        image_path = str(event.snapshot_url) if event.snapshot_url else None
        
        visit = Visit(
            tenant_id=tenant_id,
            visit_id=visit_id,
            person_id=person_id,
            person_type=person_type,
            site_id=event.site_id,
            camera_id=event.camera_id,
            timestamp=event.timestamp.replace(tzinfo=None) if event.timestamp.tzinfo else event.timestamp,
            confidence_score=confidence_score,
            face_embedding=json.dumps(event.embedding),
            image_path=image_path,  # Now properly setting the image path
            bbox_x=event.bbox[0] if len(event.bbox) >= 4 else None,
            bbox_y=event.bbox[1] if len(event.bbox) >= 4 else None,
            bbox_w=event.bbox[2] if len(event.bbox) >= 4 else None,
            bbox_h=event.bbox[3] if len(event.bbox) >= 4 else None,
        )
        
        db_session.add(visit)
        await db_session.commit()
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