from datetime import datetime, timezone
import logging
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status, File, UploadFile, Form
from sqlalchemy import select, func, and_, case, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.security import get_current_user
from ..models.database import Visit
from ..schemas import FaceEventResponse, VisitResponse, VisitsPaginatedResponse
from pydantic import BaseModel
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
    event_data: str = Form(..., description="JSON-encoded FaceDetectedEvent"),
    face_image: UploadFile = File(..., description="Cropped face image from worker"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Parse the event data
    try:
        event_dict = json.loads(event_data)
        event = FaceDetectedEvent(**event_dict)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event data: {str(e)}"
        )
    
    # Validate face image
    if not face_image.content_type or not face_image.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Face image must be a valid image file"
        )
    
    # Read the face image data
    face_image_data = await face_image.read()
    
    result = await face_service.process_face_event_with_image(
        event=event,
        face_image_data=face_image_data,
        face_image_filename=face_image.filename or "face.jpg",
        db_session=db_session,
        tenant_id=user["tenant_id"]
    )
    
    return FaceEventResponse(**result)


# ===============================
# Visits
# ===============================

@router.get("/visits", response_model=VisitsPaginatedResponse)
async def list_visits(
    site_id: Optional[str] = Query(None),
    person_id: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(50, le=100),  # Reduced max limit for better performance
    cursor: Optional[str] = Query(None, description="Cursor for pagination (visit timestamp)"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    from ..core.minio_client import minio_client
    
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    query = select(Visit).where(Visit.tenant_id == user["tenant_id"])
    
    # Apply filters
    if site_id:
        query = query.where(Visit.site_id == site_id)
    if person_id:
        query = query.where(Visit.person_id == person_id)
    if start_time:
        query = query.where(Visit.last_seen >= to_naive_utc(start_time))  # Use last_seen for better filtering
    if end_time:
        query = query.where(Visit.last_seen <= to_naive_utc(end_time))
    
    # Cursor-based pagination
    if cursor:
        try:
            cursor_time = datetime.fromisoformat(cursor.replace('Z', '+00:00')).replace(tzinfo=None)
            query = query.where(Visit.last_seen < cursor_time)
        except Exception as e:
            logger.warning(f"Invalid cursor format: {cursor}, error: {e}")
            # If cursor is invalid, ignore it and start from the beginning
    
    # Order by last_seen DESC for most recent visits first
    query = query.order_by(Visit.last_seen.desc()).limit(limit)
    
    result = await db_session.execute(query)
    visits = result.scalars().all()
    
    # Determine if there are more results
    has_more = len(visits) == limit
    next_cursor = None
    if has_more and visits:
        # Use the last visit's timestamp as cursor for next page
        next_cursor = visits[-1].last_seen.isoformat()
    
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
                    # Handle different image path types
                    if visit.image_path.startswith('visits-faces/'):
                        # API-generated face crops are in faces-derived bucket
                        object_path = visit.image_path.replace('visits-faces/', '')
                        image_url = minio_client.get_presigned_url('faces-derived', object_path)
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
            visit_session_id=visit.visit_session_id,
            person_id=visit.person_id,
            person_type=visit.person_type,
            site_id=visit.site_id,
            camera_id=visit.camera_id,
            timestamp=visit.timestamp,
            first_seen=visit.first_seen,
            last_seen=visit.last_seen,
            visit_duration_seconds=visit.visit_duration_seconds,
            detection_count=visit.detection_count,
            confidence_score=visit.confidence_score,
            highest_confidence=visit.highest_confidence,
            image_path=image_url
        )
        visit_responses.append(visit_response)
    
    return VisitsPaginatedResponse(
        visits=visit_responses,
        has_more=has_more,
        next_cursor=next_cursor
    )


# ===============================
# Visit Management
# ===============================

class DeleteVisitsRequest(BaseModel):
    visit_ids: List[str]

@router.delete("/visits")
async def delete_visits(
    request: DeleteVisitsRequest,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Delete multiple visits by their visit_ids"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    if not request.visit_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No visit IDs provided"
        )
    
    # Verify all visits exist and belong to the current tenant
    existing_visits_query = select(Visit.visit_id).where(
        and_(
            Visit.tenant_id == user["tenant_id"],
            Visit.visit_id.in_(request.visit_ids)
        )
    )
    result = await db_session.execute(existing_visits_query)
    existing_visit_ids = [row[0] for row in result]
    
    missing_visits = set(request.visit_ids) - set(existing_visit_ids)
    if missing_visits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit(s) not found: {', '.join(missing_visits)}"
        )
    
    # Delete the visits
    delete_query = delete(Visit).where(
        and_(
            Visit.tenant_id == user["tenant_id"],
            Visit.visit_id.in_(request.visit_ids)
        )
    )
    
    result = await db_session.execute(delete_query)
    await db_session.commit()
    
    deleted_count = result.rowcount
    
    return {
        "message": f"Successfully deleted {deleted_count} visit(s)",
        "deleted_count": deleted_count,
        "deleted_visit_ids": request.visit_ids
    }


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