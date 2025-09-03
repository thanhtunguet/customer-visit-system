from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.security import get_current_user
from ..models.database import Visit
from ..schemas import FaceEventResponse, VisitResponse
from ..services.face_service import face_service
from common.models import FaceDetectedEvent

router = APIRouter(prefix="/v1", tags=["Events & Detection", "Visits & Analytics"])


def to_naive_utc(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to UTC and make timezone-naive for PostgreSQL compatibility."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@router.post("/events/face", response_model=FaceEventResponse)
async def process_face_event(
    event: FaceDetectedEvent,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await face_service.process_face_event(
        event=event,
        db_session=db_session,
        tenant_id=user["tenant_id"]
    )
    
    return FaceEventResponse(**result)


# ===============================
# Visits
# ===============================

@router.get("/visits", response_model=List[VisitResponse])
async def list_visits(
    site_id: Optional[str] = Query(None),
    person_id: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    from ..core.minio_client import minio_client
    
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    query = select(Visit).where(Visit.tenant_id == user["tenant_id"])
    
    if site_id:
        query = query.where(Visit.site_id == site_id)
    if person_id:
        query = query.where(Visit.person_id == person_id)
    if start_time:
        query = query.where(Visit.timestamp >= to_naive_utc(start_time))
    if end_time:
        query = query.where(Visit.timestamp <= to_naive_utc(end_time))
    
    query = query.order_by(Visit.timestamp.desc()).limit(limit).offset(offset)
    
    result = await db_session.execute(query)
    visits = result.scalars().all()
    
    # Convert visits to response format with presigned URLs
    visit_responses = []
    for visit in visits:
        # Convert MinIO path to presigned URL if image_path exists
        image_url = None
        if visit.image_path:
            try:
                # Check if it's a MinIO s3:// path or already a URL
                if visit.image_path.startswith('s3://'):
                    # Extract bucket and object name from s3://bucket/object format
                    path_parts = visit.image_path[5:].split('/', 1)  # Remove 's3://' prefix
                    if len(path_parts) == 2:
                        bucket, object_name = path_parts
                        image_url = minio_client.get_presigned_url(bucket, object_name)
                    else:
                        image_url = visit.image_path
                elif visit.image_path.startswith('http'):
                    # Already a URL, use as-is
                    image_url = visit.image_path
                else:
                    # Assume it's a path in the faces-raw bucket
                    image_url = minio_client.get_presigned_url('faces-raw', visit.image_path)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to generate presigned URL for {visit.image_path}: {e}")
                image_url = None
        
        visit_response = VisitResponse(
            tenant_id=visit.tenant_id,
            visit_id=visit.visit_id,
            person_id=visit.person_id,
            person_type=visit.person_type,
            site_id=visit.site_id,
            camera_id=visit.camera_id,
            timestamp=visit.timestamp,
            confidence_score=visit.confidence_score,
            image_path=image_url
        )
        visit_responses.append(visit_response)
    
    return visit_responses


# ===============================
# Reports
# ===============================

@router.get("/reports/visitors")
async def get_visitor_report(
    site_id: Optional[str] = Query(None),
    granularity: str = Query("day", regex="^(hour|day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Build time granularity function
    time_trunc = {
        "hour": func.date_trunc("hour", Visit.timestamp),
        "day": func.date_trunc("day", Visit.timestamp),
        "week": func.date_trunc("week", Visit.timestamp),
        "month": func.date_trunc("month", Visit.timestamp),
    }[granularity]
    
    query = (
        select(
            time_trunc.label("period"),
            func.count().label("total_visits"),
            func.count(func.distinct(Visit.person_id)).label("unique_visitors"),
            func.sum(case((Visit.person_type == "staff", 1), else_=0)).label("staff_visits"),
            func.sum(case((Visit.person_type == "customer", 1), else_=0)).label("customer_visits"),
        )
        .where(Visit.tenant_id == user["tenant_id"])
        .group_by(time_trunc)
        .order_by(time_trunc.desc())
    )
    
    if site_id:
        query = query.where(Visit.site_id == site_id)
    if start_date:
        query = query.where(Visit.timestamp >= to_naive_utc(start_date))
    if end_date:
        query = query.where(Visit.timestamp <= to_naive_utc(end_date))
    
    result = await db_session.execute(query)
    
    return [
        {
            "period": row.period.isoformat() if row.period else None,
            "total_visits": int(row.total_visits),
            "unique_visitors": int(row.unique_visitors),
            "staff_visits": int(row.staff_visits or 0),
            "customer_visits": int(row.customer_visits or 0),
        }
        for row in result
    ]