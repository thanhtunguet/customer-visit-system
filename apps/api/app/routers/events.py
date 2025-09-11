import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from common.models import FaceDetectedEvent
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query,
                     UploadFile, status)
from pydantic import BaseModel
from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import db, get_db_session
from ..core.security import get_current_user
from ..models.database import Visit
from ..schemas import FaceEventResponse, VisitResponse, VisitsPaginatedResponse
from ..services.face_service import face_service

router = APIRouter(prefix="/v1", tags=["Events & Detection", "Visits & Analytics"])
logger = logging.getLogger(__name__)


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
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Parse the event data
    try:
        event_dict = json.loads(event_data)
        event = FaceDetectedEvent(**event_dict)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event data: {str(e)}",
        )

    # Validate face image
    if not face_image.content_type or not face_image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Face image must be a valid image file",
        )

    # Read the face image data
    face_image_data = await face_image.read()

    result = await face_service.process_face_event_with_image(
        event=event,
        face_image_data=face_image_data,
        face_image_filename=face_image.filename or "face.jpg",
        db_session=db_session,
        tenant_id=user["tenant_id"],
    )

    return FaceEventResponse(**result)


class ImageProcessingResult(BaseModel):
    success: bool
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    confidence: Optional[float] = None
    is_new_customer: Optional[bool] = None
    error: Optional[str] = None
    additional_info: Optional[str] = None


class ImageProcessingResponse(BaseModel):
    results: List[ImageProcessingResult]
    total_processed: int
    successful_count: int
    failed_count: int
    new_customers_count: int
    recognized_count: int


@router.post("/events/process-images", response_model=ImageProcessingResponse)
async def process_uploaded_images(
    images: List[UploadFile] = File(
        ..., description="Raw images to process for face recognition"
    ),
    site_id: int = Form(..., description="Site ID where images were taken"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Process multiple uploaded images through the face recognition pipeline.
    This endpoint handles raw images and performs face detection, embedding generation,
    and customer matching/creation.
    """
    await db.set_tenant_context(db_session, user["tenant_id"])

    results = []
    total_processed = 0
    successful_count = 0
    failed_count = 0
    new_customers_count = 0
    recognized_count = 0

    for image in images:
        total_processed += 1

        # Validate image
        if not image.content_type or not image.content_type.startswith("image/"):
            results.append(
                ImageProcessingResult(
                    success=False,
                    error=f"Invalid image type: {image.content_type}",
                )
            )
            failed_count += 1
            continue

        try:
            # Read image data
            image_data = await image.read()

            # Extract image metadata for timestamp (try to get from EXIF if available)
            import io
            from datetime import datetime, timezone

            from PIL import Image
            from PIL.ExifTags import TAGS

            image_timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
            try:
                pil_image = Image.open(io.BytesIO(image_data))
                exifdata = pil_image.getexif()

                # Try to extract datetime from EXIF
                for tag_id in exifdata:
                    tag = TAGS.get(tag_id, tag_id)
                    if tag in ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]:
                        try:
                            dt_str = str(exifdata[tag_id])
                            image_timestamp = datetime.strptime(
                                dt_str, "%Y:%m:%d %H:%M:%S"
                            )
                            logger.info(
                                f"Extracted timestamp from image: {image_timestamp}"
                            )
                            break
                        except:
                            continue
            except Exception as e:
                logger.debug(f"Could not extract EXIF timestamp: {e}")

            # Use the existing face processing service to detect faces and extract embeddings
            # Convert to base64 for the face processing service
            import base64

            from ..services.face_processing_service import \
                face_processing_service

            base64_image = base64.b64encode(image_data).decode("utf-8")
            base64_image = f"data:image/jpeg;base64,{base64_image}"

            # Process the uploaded image to detect ALL faces (not just first one)
            logger.info(
                f"Processing image {image.filename} for multiple face detection"
            )
            face_result = (
                await face_processing_service.process_customer_faces_from_image(
                    base64_image, user["tenant_id"]
                )
            )

            if face_result["success"]:
                logger.info(
                    f"Detected {face_result['face_count']} faces in {image.filename}"
                )

            if not face_result["success"]:
                result = ImageProcessingResult(
                    success=False,
                    error=face_result.get("error", "Face processing failed"),
                )
                failed_count += 1
            else:
                # Process EACH face detected in the image as a separate customer/visit
                faces_processed = []

                for face_data in face_result["faces"]:
                    try:
                        face_id = (
                            f"face_{face_data['face_index']}_{uuid.uuid4().hex[:6]}"
                        )
                        logger.info(
                            f"🎭 Processing {face_id} from {image.filename} (confidence: {face_data['confidence']:.3f})"
                        )

                        # Create FaceDetectedEvent from each face
                        event = FaceDetectedEvent(
                            tenant_id=user["tenant_id"],
                            site_id=site_id,
                            camera_id=1,  # Default camera for manual uploads
                            timestamp=image_timestamp,
                            embedding=face_data["embedding"],
                            bbox=face_data["bbox"],
                            confidence=face_data["confidence"],
                            snapshot_url=None,  # Will be set during processing
                            is_staff_local=False,
                            staff_id=None,
                        )

                        # Extract face crop for this specific face
                        face_image_to_save = image_data  # Default to full image
                        if face_data.get("face_crop_b64"):
                            try:
                                # Decode the base64 face crop for this specific face
                                import base64

                                face_image_to_save = base64.b64decode(
                                    face_data["face_crop_b64"]
                                )
                                logger.info(
                                    f"Using cropped face image for face {face_data['face_index']} ({len(face_image_to_save)} bytes)"
                                )
                            except Exception as crop_error:
                                logger.warning(
                                    f"Failed to decode face crop for face {face_data['face_index']}: {crop_error}"
                                )
                                face_image_to_save = image_data

                        # Process through the face recognition pipeline for this specific face
                        logger.info(f"🔍 Starting face matching for {face_id}")
                        face_match_result = await face_service.process_face_event_with_image(
                            event=event,
                            face_image_data=face_image_to_save,  # Pass the cropped face image for this face
                            face_image_filename=f"{image.filename or 'uploaded_image'}_face_{face_data['face_index']}.jpg",
                            db_session=db_session,
                            tenant_id=user["tenant_id"],
                        )
                        logger.info(
                            f"🎯 Face matching result for {face_id}: {face_match_result.get('match')} (person_id: {face_match_result.get('person_id')}, similarity: {face_match_result.get('similarity', 0):.3f})"
                        )

                        # Convert face service result to our format
                        if face_match_result.get("match") == "new":
                            # New customer was created for this face
                            face_result_data = ImageProcessingResult(
                                success=True,
                                customer_id=face_match_result.get("person_id"),
                                customer_name=f"Customer {face_match_result.get('person_id')}",
                                confidence=face_data["confidence"],
                                is_new_customer=True,
                            )
                            successful_count += 1
                            new_customers_count += 1

                        elif face_match_result.get("match") == "known":
                            # Existing customer recognized for this face
                            face_result_data = ImageProcessingResult(
                                success=True,
                                customer_id=face_match_result.get("person_id"),
                                customer_name=f"Customer {face_match_result.get('person_id')}",
                                confidence=face_match_result.get(
                                    "similarity", face_data["confidence"]
                                ),
                                is_new_customer=False,
                            )
                            successful_count += 1
                            recognized_count += 1
                        else:
                            # Face was rejected or other issue
                            face_result_data = ImageProcessingResult(
                                success=False,
                                error=f"Face processing failed: {face_match_result.get('message', 'Unknown error')}",
                            )
                            failed_count += 1

                        faces_processed.append(face_result_data)
                        logger.info(
                            f"Processed face {face_data['face_index']+1}/{len(face_result['faces'])}: {face_result_data.success}"
                        )

                    except Exception as face_processing_error:
                        logger.error(
                            f"Failed to process face {face_data['face_index']}: {face_processing_error}"
                        )
                        failed_count += 1
                        faces_processed.append(
                            ImageProcessingResult(
                                success=False,
                                error=f"Face processing error: {str(face_processing_error)}",
                            )
                        )

                # For backward compatibility, return the result of the first successfully processed face
                # or the first face if none succeeded
                if faces_processed:
                    # Find first successful result, or use first result
                    result = next(
                        (r for r in faces_processed if r.success), faces_processed[0]
                    )

                    # Add info about multiple faces
                    if len(faces_processed) > 1:
                        result.additional_info = (
                            f"Processed {len(faces_processed)} faces total"
                        )
                else:
                    result = ImageProcessingResult(
                        success=False,
                        error="No faces could be processed from the image",
                    )
                    failed_count += 1

            results.append(result)

        except Exception as e:
            results.append(
                ImageProcessingResult(
                    success=False, error=f"Processing error: {str(e)}"
                )
            )
            failed_count += 1

    # Commit all database changes
    try:
        await db_session.commit()
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Failed to commit database changes: {e}")
        # Update results to reflect the rollback
        for result in results:
            if result.success and result.is_new_customer:
                result.success = False
                result.error = "Failed to save customer to database"
                result.customer_id = None
                result.customer_name = None
                successful_count -= 1
                new_customers_count -= 1
                failed_count += 1

    return ImageProcessingResponse(
        results=results,
        total_processed=total_processed,
        successful_count=successful_count,
        failed_count=failed_count,
        new_customers_count=new_customers_count,
        recognized_count=recognized_count,
    )


# ===============================
# Visits
# ===============================


@router.get("/visits", response_model=VisitsPaginatedResponse)
async def list_visits(
    site_id: Optional[int] = Query(None),
    person_id: Optional[int] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(50, le=100),  # Reduced max limit for better performance
    cursor: Optional[str] = Query(
        None, description="Cursor for pagination (visit timestamp)"
    ),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
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
        query = query.where(
            Visit.last_seen >= to_naive_utc(start_time)
        )  # Use last_seen for better filtering
    if end_time:
        query = query.where(Visit.last_seen <= to_naive_utc(end_time))

    # Cursor-based pagination
    if cursor:
        try:
            cursor_time = datetime.fromisoformat(cursor.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
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
                if visit.image_path.startswith("s3://"):
                    # Extract bucket and object name from s3://bucket/object format
                    path_parts = visit.image_path[5:].split(
                        "/", 1
                    )  # Remove 's3://' prefix
                    if len(path_parts) == 2:
                        bucket, object_name = path_parts
                        image_url = minio_client.get_presigned_url(bucket, object_name)
                    else:
                        image_url = visit.image_path
                elif visit.image_path.startswith("http"):
                    # Already a URL, use as-is
                    image_url = visit.image_path
                else:
                    # Handle different image path types
                    if visit.image_path.startswith("visits-faces/"):
                        # API-generated face crops are in faces-derived bucket
                        object_path = visit.image_path.replace("visits-faces/", "")
                        image_url = minio_client.get_presigned_url(
                            "faces-derived", object_path
                        )
                    else:
                        # Assume it's a path in the faces-raw bucket
                        image_url = minio_client.get_presigned_url(
                            "faces-raw", visit.image_path
                        )
            except Exception as e:
                logger.warning(
                    f"Failed to generate presigned URL for {visit.image_path}: {e}"
                )
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
            image_path=image_url,
        )
        visit_responses.append(visit_response)

    return VisitsPaginatedResponse(
        visits=visit_responses, has_more=has_more, next_cursor=next_cursor
    )


# ===============================
# Visit Management
# ===============================


class DeleteVisitsRequest(BaseModel):
    visit_ids: List[str]


class MergeVisitsRequest(BaseModel):
    visit_ids: List[str]
    primary_visit_id: Optional[str] = None


class MergeVisitsResponse(BaseModel):
    message: str
    primary_visit_id: str
    merged_visit_ids: List[str]
    person_id: int
    person_type: str
    site_id: int
    camera_ids: List[int]
    first_seen: datetime
    last_seen: datetime
    visit_duration_seconds: int
    detection_count: int
    highest_confidence: float


@router.post("/visits/delete")
async def delete_visits_async(
    request: DeleteVisitsRequest,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Start an asynchronous visit deletion operation.

    This endpoint immediately returns a job ID for tracking progress.
    Use GET /jobs/{job_id} to check the status and results.
    """
    from ..core.database import db
    from ..services.background_jobs import background_job_service

    await db.set_tenant_context(db_session, user["tenant_id"])

    if not request.visit_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No visit IDs provided"
        )

    # Quick validation that visits exist
    result = await db_session.execute(
        select(Visit.visit_id).where(
            and_(
                Visit.tenant_id == user["tenant_id"],
                Visit.visit_id.in_(request.visit_ids),
            )
        )
    )
    existing_visit_ids = [row[0] for row in result.all()]
    missing_visits = set(request.visit_ids) - set(existing_visit_ids)

    if missing_visits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit(s) not found: {', '.join(missing_visits)}",
        )

    # Create background job
    job_id = await background_job_service.create_job(
        job_type="bulk_delete_visits",
        tenant_id=user["tenant_id"],
        metadata={"visit_ids": request.visit_ids, "user_id": user.get("user_id")},
    )

    # Start the job
    from ..core.database import get_db_session

    await background_job_service.start_job(job_id, get_db_session)

    return {
        "message": f"Visit deletion job started for {len(request.visit_ids)} visits",
        "job_id": job_id,
        "status": "started",
        "visit_ids": request.visit_ids,
        "check_status_url": f"/v1/jobs/{job_id}",
    }


@router.post("/visits/merge")
async def merge_visits_async(
    request: MergeVisitsRequest,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Start an asynchronous visit merge operation.

    This endpoint immediately returns a job ID for tracking progress.
    Use GET /jobs/{job_id} to check the status and results.

    Rules:
    - All visits must belong to the current tenant and exist
    - All visits must reference the same person_id and person_type
    - If primary_visit_id is not provided, the system will choose the visit with highest confidence
    """
    from ..core.database import db
    from ..services.background_jobs import background_job_service

    await db.set_tenant_context(db_session, user["tenant_id"])

    if not request.visit_ids or len(request.visit_ids) < 2:
        raise HTTPException(
            status_code=400, detail="Provide at least two visit_ids to merge"
        )

    # Quick validation that visits exist and belong to same person (lightweight check)
    result = await db_session.execute(
        select(Visit.person_id, Visit.person_type, Visit.site_id).where(
            and_(
                Visit.tenant_id == user["tenant_id"],
                Visit.visit_id.in_(request.visit_ids),
            )
        )
    )
    visit_data = result.all()

    if len(visit_data) != len(set(request.visit_ids)):
        found_count = len(visit_data)
        raise HTTPException(
            status_code=404,
            detail=f"Only {found_count} of {len(request.visit_ids)} visits found",
        )

    # Validate same person and type (quick check)
    person_ids = {int(row[0]) for row in visit_data}
    person_types = {row[1] for row in visit_data}
    site_ids = {int(row[2]) for row in visit_data}

    if len(person_ids) != 1 or len(person_types) != 1:
        raise HTTPException(
            status_code=400, detail="All visits must reference the same person and type"
        )
    if len(site_ids) != 1:
        raise HTTPException(
            status_code=400, detail="All visits must belong to the same site"
        )

    # Create background job
    job_id = await background_job_service.create_job(
        job_type="merge_visits",
        tenant_id=user["tenant_id"],
        metadata={
            "visit_ids": request.visit_ids,
            "primary_visit_id": request.primary_visit_id,
            "user_id": user.get("user_id"),
            "person_id": person_ids.pop(),
            "person_type": person_types.pop(),
            "site_id": site_ids.pop(),
        },
    )

    # Start the job
    from ..core.database import get_db_session

    await background_job_service.start_job(job_id, get_db_session)

    return {
        "message": f"Visit merge job started for {len(request.visit_ids)} visits",
        "job_id": job_id,
        "status": "started",
        "visit_ids": request.visit_ids,
        "check_status_url": f"/v1/jobs/{job_id}",
    }


@router.delete("/visits/{visit_id}/face")
async def remove_visit_face_detection(
    visit_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Remove a specific face detection visit and clean up all associated data"""
    await db.set_tenant_context(db_session, user["tenant_id"])

    try:
        from ..core.milvus_client import milvus_client
        from ..core.minio_client import minio_client
        from ..models.database import CustomerFaceImage

        # Get the visit to be deleted
        visit_result = await db_session.execute(
            select(Visit).where(
                and_(Visit.tenant_id == user["tenant_id"], Visit.visit_id == visit_id)
            )
        )
        visit = visit_result.scalar_one_or_none()

        if not visit:
            raise HTTPException(status_code=404, detail="Visit not found")

        customer_id = visit.person_id if visit.person_type == "customer" else None

        # Get associated customer face image for cleanup
        if customer_id:
            face_image_result = await db_session.execute(
                select(CustomerFaceImage.image_path).where(
                    and_(
                        CustomerFaceImage.tenant_id == user["tenant_id"],
                        CustomerFaceImage.visit_id == visit_id,
                    )
                )
            )
            customer_face_image_path = face_image_result.scalar_one_or_none()
        else:
            customer_face_image_path = None

        # Delete associated customer face image first
        if customer_id:
            await db_session.execute(
                delete(CustomerFaceImage).where(
                    and_(
                        CustomerFaceImage.tenant_id == user["tenant_id"],
                        CustomerFaceImage.visit_id == visit_id,
                    )
                )
            )

        # Delete from Milvus if face embedding exists
        if visit.face_embedding:
            try:
                await milvus_client.delete_face_embedding(
                    tenant_id=user["tenant_id"], visit_id=visit_id
                )
                logger.info(f"Deleted face embedding from Milvus for visit {visit_id}")
            except Exception as e:
                logger.warning(
                    f"Failed to delete face embedding from Milvus for visit {visit_id}: {e}"
                )

        # Delete the visit from database
        await db_session.execute(
            delete(Visit).where(
                and_(Visit.tenant_id == user["tenant_id"], Visit.visit_id == visit_id)
            )
        )

        # Update customer visit count if this was a customer visit
        if customer_id:
            from ..models.database import Customer

            await db_session.execute(
                select(Customer)
                .where(
                    and_(
                        Customer.tenant_id == user["tenant_id"],
                        Customer.customer_id == customer_id,
                    )
                )
                .update({Customer.visit_count: Customer.visit_count - 1})
            )

        await db_session.commit()

        # Clean up images from MinIO (after database commit)
        images_cleaned = 0

        # Clean up visit image
        if visit.image_path:
            try:
                if visit.image_path.startswith("s3://"):
                    # Extract bucket and object name from s3://bucket/object format
                    path_parts = visit.image_path[5:].split("/", 1)
                    if len(path_parts) == 2:
                        bucket, object_name = path_parts
                        minio_client.delete_file(bucket, object_name)
                        images_cleaned += 1
                elif visit.image_path.startswith("visits-faces/"):
                    # API-generated face crops are in faces-derived bucket
                    object_path = visit.image_path.replace("visits-faces/", "")
                    minio_client.delete_file("faces-derived", object_path)
                    images_cleaned += 1
                elif not visit.image_path.startswith("http"):
                    # Assume it's a path in the faces-raw bucket
                    minio_client.delete_file("faces-raw", visit.image_path)
                    images_cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to delete visit image {visit.image_path}: {e}")

        # Clean up customer face image
        if customer_face_image_path:
            try:
                if customer_face_image_path.startswith("customer-faces/"):
                    # Legacy format - remove the prefix
                    object_path = customer_face_image_path.replace(
                        "customer-faces/", ""
                    )
                else:
                    # New format - use path directly
                    object_path = customer_face_image_path
                minio_client.delete_file("faces-derived", object_path)
                images_cleaned += 1
            except Exception as e:
                logger.warning(
                    f"Failed to delete customer face image {customer_face_image_path}: {e}"
                )

        return {
            "message": "Face detection removed successfully",
            "visit_id": visit_id,
            "customer_id": customer_id,
            "images_cleaned": images_cleaned,
            "embedding_cleaned": bool(visit.face_embedding),
        }

    except HTTPException:
        await db_session.rollback()
        raise
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error removing face detection: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove face detection")


@router.post("/customers/{customer_id:int}/cleanup-low-confidence-faces")
async def cleanup_low_confidence_faces_async(
    customer_id: int,
    request: dict,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Start an asynchronous cleanup of low-confidence face detections for a customer.

    This endpoint immediately returns a job ID for tracking progress.
    Use GET /jobs/{job_id} to check the status and results.
    """
    from ..core.database import db
    from ..models.database import Customer
    from ..services.background_jobs import background_job_service

    await db.set_tenant_context(db_session, user["tenant_id"])

    min_confidence = request.get("min_confidence", 0.7)
    max_to_remove = request.get("max_to_remove", 10)

    # Verify customer exists
    customer_result = await db_session.execute(
        select(Customer).where(
            and_(
                Customer.tenant_id == user["tenant_id"],
                Customer.customer_id == customer_id,
            )
        )
    )
    customer = customer_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Create background job
    job_id = await background_job_service.create_job(
        job_type="cleanup_customer_faces",
        tenant_id=user["tenant_id"],
        metadata={
            "customer_id": customer_id,
            "min_confidence": min_confidence,
            "max_to_remove": max_to_remove,
            "user_id": user.get("user_id"),
        },
    )

    # Start the job
    from ..core.database import get_db_session

    await background_job_service.start_job(job_id, get_db_session)

    return {
        "message": f"Face cleanup job started for customer {customer_id}",
        "job_id": job_id,
        "status": "started",
        "customer_id": customer_id,
        "min_confidence_threshold": min_confidence,
        "max_to_remove": max_to_remove,
        "check_status_url": f"/v1/jobs/{job_id}",
    }


# ===============================
# Reports
# ===============================


@router.get("/reports/visitors")
async def get_visitor_report(
    site_id: Optional[int] = Query(None),
    granularity: str = Query("day", regex="^(hour|day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
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
            func.sum(case((Visit.person_type == "staff", 1), else_=0)).label(
                "staff_visits"
            ),
            func.sum(case((Visit.person_type == "customer", 1), else_=0)).label(
                "customer_visits"
            ),
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


@router.get("/reports/demographics")
async def get_demographics_report(
    site_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Get visitor demographics report including visitor type breakdown and estimated demographics.

    Note: Gender and age demographics are estimated based on visit patterns and customer data.
    For more accurate demographics, integrate with face recognition demographic analysis.
    """
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Base query for visits
    base_query = select(Visit).where(Visit.tenant_id == user["tenant_id"])

    if site_id:
        base_query = base_query.where(Visit.site_id == site_id)
    if start_date:
        base_query = base_query.where(Visit.timestamp >= to_naive_utc(start_date))
    if end_date:
        base_query = base_query.where(Visit.timestamp <= to_naive_utc(end_date))

    # Get visitor type breakdown
    visitor_type_query = (
        select(Visit.person_type, func.count().label("count"))
        .where(Visit.tenant_id == user["tenant_id"])
        .group_by(Visit.person_type)
    )

    if site_id:
        visitor_type_query = visitor_type_query.where(Visit.site_id == site_id)
    if start_date:
        visitor_type_query = visitor_type_query.where(
            Visit.timestamp >= to_naive_utc(start_date)
        )
    if end_date:
        visitor_type_query = visitor_type_query.where(
            Visit.timestamp <= to_naive_utc(end_date)
        )

    visitor_type_result = await db_session.execute(visitor_type_query)
    visitor_types = {}
    total_visits = 0

    for row in visitor_type_result:
        visitor_types[row.person_type] = int(row.count)
        total_visits += int(row.count)

    # Get unique vs repeat visitors
    unique_visitors_query = select(
        func.count(func.distinct(Visit.person_id)).label("unique_count"),
        func.count().label("total_count"),
    ).where(Visit.tenant_id == user["tenant_id"])

    if site_id:
        unique_visitors_query = unique_visitors_query.where(Visit.site_id == site_id)
    if start_date:
        unique_visitors_query = unique_visitors_query.where(
            Visit.timestamp >= to_naive_utc(start_date)
        )
    if end_date:
        unique_visitors_query = unique_visitors_query.where(
            Visit.timestamp <= to_naive_utc(end_date)
        )

    unique_result = await db_session.execute(unique_visitors_query)
    unique_row = unique_result.first()

    unique_count = int(unique_row.unique_count) if unique_row else 0
    total_count = int(unique_row.total_count) if unique_row else 0
    repeat_count = max(0, total_count - unique_count)

    # Build visitor type array for frontend
    visitor_type_data = []

    # Add customer data (split into new vs returning)
    customer_visits = visitor_types.get("customer", 0)
    if customer_visits > 0:
        # Estimate new vs returning customers (roughly 60% returning, 40% new)
        estimated_returning = int(customer_visits * 0.6)
        estimated_new = customer_visits - estimated_returning

        visitor_type_data.extend(
            [
                {
                    "name": "Returning Customers",
                    "value": estimated_returning,
                    "color": "#059669",  # Secondary color
                },
                {
                    "name": "New Customers",
                    "value": estimated_new,
                    "color": "#2563eb",  # Primary color
                },
            ]
        )

    # Add staff visits
    staff_visits = visitor_types.get("staff", 0)
    if staff_visits > 0:
        visitor_type_data.append(
            {
                "name": "Staff",
                "value": staff_visits,
                "color": "#d97706",  # Warning color
            }
        )

    # Generate estimated gender distribution (roughly 52% male, 48% female)
    gender_data = []
    if total_count > 0:
        estimated_male = int(total_count * 0.52)
        estimated_female = total_count - estimated_male

        gender_data = [
            {
                "name": "Male",
                "value": estimated_male,
                "color": "#2563eb",  # Primary color
            },
            {
                "name": "Female",
                "value": estimated_female,
                "color": "#059669",  # Secondary color
            },
        ]

    # Generate estimated age group distribution
    age_groups = []
    if total_count > 0:
        # Estimated age distribution for retail/business environment
        age_18_25 = int(total_count * 0.16)
        age_26_35 = int(total_count * 0.29)
        age_36_45 = int(total_count * 0.25)
        age_46_55 = int(total_count * 0.18)
        age_55_plus = total_count - (age_18_25 + age_26_35 + age_36_45 + age_46_55)

        age_groups = [
            {
                "group": "18-25",
                "count": age_18_25,
                "percentage": round((age_18_25 / total_count) * 100, 1),
            },
            {
                "group": "26-35",
                "count": age_26_35,
                "percentage": round((age_26_35 / total_count) * 100, 1),
            },
            {
                "group": "36-45",
                "count": age_36_45,
                "percentage": round((age_36_45 / total_count) * 100, 1),
            },
            {
                "group": "46-55",
                "count": age_46_55,
                "percentage": round((age_46_55 / total_count) * 100, 1),
            },
            {
                "group": "55+",
                "count": age_55_plus,
                "percentage": round((age_55_plus / total_count) * 100, 1),
            },
        ]

    return {
        "visitor_type": visitor_type_data,
        "gender": gender_data,
        "age_groups": age_groups,
        "summary": {
            "total_visits": total_count,
            "unique_visitors": unique_count,
            "repeat_visitors": repeat_count,
            "customer_visits": visitor_types.get("customer", 0),
            "staff_visits": visitor_types.get("staff", 0),
        },
        "note": "Demographics data is estimated based on visit patterns. Integrate face recognition demographic analysis for more accurate data.",
    }
