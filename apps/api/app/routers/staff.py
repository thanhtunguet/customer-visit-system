import base64
import hashlib
import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import db, get_db_session
from ..core.milvus_client import milvus_client
from ..core.minio_client import minio_client
from ..core.security import get_current_user
from ..models.database import Staff, StaffFaceImage
from ..schemas import (
    FaceRecognitionTestRequest,
    FaceRecognitionTestResponse,
    StaffCreate,
    StaffFaceImageBulkCreate,
    StaffFaceImageCreate,
    StaffFaceImageResponse,
    StaffResponse,
    StaffWithFacesResponse,
)
from ..services.face_processing_service import face_processing_service
from ..services.face_service import staff_service

router = APIRouter(prefix="/v1", tags=["Staff Management"])
logger = logging.getLogger(__name__)


@router.get("/staff", response_model=List[StaffResponse])
async def list_staff(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])

    result = await db_session.execute(
        select(Staff).where(Staff.tenant_id == user["tenant_id"])
    )
    staff_members = result.scalars().all()
    return staff_members


@router.post("/staff", response_model=StaffResponse)
async def create_staff(
    staff: StaffCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Create staff member (ID will be auto-generated)
    new_staff = Staff(
        tenant_id=user["tenant_id"], name=staff.name, site_id=staff.site_id
    )
    db_session.add(new_staff)
    await db_session.commit()
    await db_session.refresh(new_staff)

    # Enroll with face embedding if provided
    if staff.face_embedding:
        await staff_service.enroll_staff_member(
            db_session=db_session,
            tenant_id=user["tenant_id"],
            staff_id=new_staff.staff_id,
            name=staff.name,
            face_embedding=staff.face_embedding,
            site_id=staff.site_id,
        )

    # Return the created staff member
    return new_staff


@router.get("/staff/{staff_id:int}", response_model=StaffResponse)
async def get_staff_member(
    staff_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])

    result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff_member = result.scalar_one_or_none()
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found")

    return staff_member


@router.put("/staff/{staff_id:int}", response_model=StaffResponse)
async def update_staff(
    staff_id: int,
    staff_update: StaffCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])

    result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff_member = result.scalar_one_or_none()
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # Update staff fields
    staff_member.name = staff_update.name
    staff_member.site_id = staff_update.site_id

    # Handle face embedding update
    if staff_update.face_embedding:
        # Delete existing embeddings and create new ones
        await staff_service.enroll_staff_member(
            db_session=db_session,
            tenant_id=user["tenant_id"],
            staff_id=staff_id,
            name=staff_update.name,
            face_embedding=staff_update.face_embedding,
            site_id=staff_update.site_id,
            update_existing=True,
        )

    await db_session.commit()
    await db_session.refresh(staff_member)
    return staff_member


@router.delete("/staff/{staff_id:int}")
async def delete_staff(
    staff_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])

    result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff_member = result.scalar_one_or_none()
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # Delete from Milvus as well
    try:
        await milvus_client.delete_person_embeddings(user["tenant_id"], staff_id)
    except Exception as e:
        logger.warning(f"Failed to delete staff embeddings from Milvus: {e}")

    await db_session.delete(staff_member)
    await db_session.commit()
    return {"message": "Staff member deleted successfully"}


# ===============================
# Staff Face Images API
# ===============================


@router.get("/staff/{staff_id:int}/faces", response_model=List[StaffFaceImageResponse])
async def get_staff_face_images(
    staff_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get all face images for a staff member."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    if not staff_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Staff member not found")

    # Get face images
    result = await db_session.execute(
        select(StaffFaceImage)
        .where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id,
            )
        )
        .order_by(StaffFaceImage.created_at.desc())
    )

    face_images = result.scalars().all()

    # Parse landmarks from JSON
    response_images = []
    for img in face_images:
        response_data = {
            "tenant_id": img.tenant_id,
            "image_id": img.image_id,
            "staff_id": img.staff_id,
            "image_path": img.image_path,
            "is_primary": img.is_primary,
            "created_at": img.created_at,
            "face_landmarks": (
                json.loads(img.face_landmarks) if img.face_landmarks else None
            ),
        }
        response_images.append(StaffFaceImageResponse(**response_data))

    return response_images


@router.get("/staff/{staff_id:int}/details", response_model=StaffWithFacesResponse)
async def get_staff_with_faces(
    staff_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get staff details with all face images."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Get staff member
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff = staff_result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # Get face images
    images_result = await db_session.execute(
        select(StaffFaceImage)
        .where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id,
            )
        )
        .order_by(StaffFaceImage.created_at.desc())
    )

    face_images = images_result.scalars().all()

    # Build response
    response_images = []
    for img in face_images:
        response_data = {
            "tenant_id": img.tenant_id,
            "image_id": img.image_id,
            "staff_id": img.staff_id,
            "image_path": img.image_path,
            "is_primary": img.is_primary,
            "created_at": img.created_at,
            "face_landmarks": (
                json.loads(img.face_landmarks) if img.face_landmarks else None
            ),
        }
        response_images.append(StaffFaceImageResponse(**response_data))

    staff_data = {
        "tenant_id": staff.tenant_id,
        "staff_id": staff.staff_id,
        "name": staff.name,
        "site_id": staff.site_id,
        "is_active": staff.is_active,
        "created_at": staff.created_at,
        "face_images": response_images,
    }

    return StaffWithFacesResponse(**staff_data)


@router.post("/staff/{staff_id:int}/faces", response_model=StaffFaceImageResponse)
async def upload_staff_face_image(
    staff_id: int,
    face_data: StaffFaceImageCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Upload a new face image for a staff member."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    if not staff_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Staff member not found")

    try:
        # Check for duplicate images first
        image_bytes = base64.b64decode(face_data.image_data.split(",")[-1])
        image_hash = hashlib.sha256(image_bytes).hexdigest()

        existing_result = await db_session.execute(
            select(StaffFaceImage).where(
                and_(
                    StaffFaceImage.tenant_id == user["tenant_id"],
                    StaffFaceImage.staff_id == staff_id,
                    StaffFaceImage.image_hash == image_hash,
                )
            )
        )

        existing_image = existing_result.scalar_one_or_none()
        if existing_image:
            raise HTTPException(
                status_code=409,  # Conflict status for duplicates
                detail=f"Duplicate image detected. Existing image ID: {existing_image.image_id}",
            )

        # Process face image
        processing_result = await face_processing_service.process_staff_face_image(
            base64_image=face_data.image_data,
            tenant_id=user["tenant_id"],
            staff_id=staff_id,
        )

        if not processing_result["success"]:
            # Check if it's a duplicate image
            if processing_result.get("duplicate"):
                raise HTTPException(
                    status_code=409,  # Conflict status for duplicates
                    detail=f"Duplicate image detected. Existing image ID: {processing_result.get('existing_image_id', 'unknown')}",
                )
            raise HTTPException(
                status_code=400,
                detail=f"Face processing failed: {processing_result.get('error', 'Unknown error')}",
            )

        # If this is set as primary, update existing primary images
        if face_data.is_primary:
            await db_session.execute(
                update(StaffFaceImage)
                .where(
                    and_(
                        StaffFaceImage.tenant_id == user["tenant_id"],
                        StaffFaceImage.staff_id == staff_id,
                        StaffFaceImage.is_primary,
                    )
                )
                .values(is_primary=False)
            )

        # Create face image record
        face_image = StaffFaceImage(
            tenant_id=user["tenant_id"],
            image_id=processing_result["image_id"],
            staff_id=staff_id,
            image_path=processing_result["image_path"],
            face_landmarks=json.dumps(processing_result["landmarks"]),
            face_embedding=json.dumps(processing_result["embedding"]),
            image_hash=processing_result.get("image_hash"),
            is_primary=face_data.is_primary,
        )

        db_session.add(face_image)

        # Store embedding in Milvus
        await milvus_client.insert_embedding(
            tenant_id=user["tenant_id"],
            person_id=staff_id,
            person_type="staff",
            embedding=processing_result["embedding"],
            created_at=int(datetime.utcnow().timestamp()),
        )

        await db_session.commit()
        await db_session.refresh(face_image)

        # Build response
        response_data = {
            "tenant_id": face_image.tenant_id,
            "image_id": face_image.image_id,
            "staff_id": face_image.staff_id,
            "image_path": face_image.image_path,
            "is_primary": face_image.is_primary,
            "created_at": face_image.created_at,
            "face_landmarks": (
                json.loads(face_image.face_landmarks)
                if face_image.face_landmarks
                else None
            ),
        }

        return StaffFaceImageResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload staff face image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/staff/{staff_id:int}/faces/bulk", response_model=List[StaffFaceImageResponse]
)
async def upload_multiple_staff_face_images(
    staff_id: int,
    face_data: StaffFaceImageBulkCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Upload multiple face images for a staff member with optimized processing."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    if not staff_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Staff member not found")

    if not face_data.images:
        raise HTTPException(status_code=400, detail="No images provided")

    # Limit batch size to prevent timeouts
    if len(face_data.images) > 10:
        raise HTTPException(
            status_code=400, detail="Maximum 10 images allowed per batch"
        )

    uploaded_images = []
    errors = []

    # Check if we need to reset primary flag for first image
    has_primary = any(img.is_primary for img in face_data.images)

    try:
        # Process images in parallel for better performance
        import asyncio

        async def process_single_image(
            i: int, image_data
        ) -> tuple[int, StaffFaceImageResponse | str]:
            try:
                # Check for duplicate images first
                image_bytes = base64.b64decode(image_data.image_data.split(",")[-1])
                image_hash = hashlib.sha256(image_bytes).hexdigest()

                existing_result = await db_session.execute(
                    select(StaffFaceImage).where(
                        and_(
                            StaffFaceImage.tenant_id == user["tenant_id"],
                            StaffFaceImage.staff_id == staff_id,
                            StaffFaceImage.image_hash == image_hash,
                        )
                    )
                )

                existing_image = existing_result.scalar_one_or_none()
                if existing_image:
                    return (
                        i,
                        f"Image {i+1}: Duplicate image detected (existing ID: {existing_image.image_id[:8]}...)",
                    )

                # Process face image
                processing_result = (
                    await face_processing_service.process_staff_face_image(
                        base64_image=image_data.image_data,
                        tenant_id=user["tenant_id"],
                        staff_id=staff_id,
                    )
                )

                if not processing_result["success"]:
                    # Check if it's a duplicate image
                    if processing_result.get("duplicate"):
                        return (
                            i,
                            f"Image {i+1}: Duplicate image detected (existing ID: {processing_result.get('existing_image_id', 'unknown')[:8]}...)",
                        )
                    return (
                        i,
                        f"Image {i+1}: Face processing failed - {processing_result.get('error', 'Unknown error')}",
                    )

                # Create face image record
                face_image = StaffFaceImage(
                    tenant_id=user["tenant_id"],
                    image_id=processing_result["image_id"],
                    staff_id=staff_id,
                    image_path=processing_result["image_path"],
                    face_landmarks=json.dumps(processing_result["landmarks"]),
                    face_embedding=json.dumps(processing_result["embedding"]),
                    image_hash=processing_result.get("image_hash"),
                    is_primary=image_data.is_primary or (i == 0 and has_primary),
                )

                return i, (face_image, processing_result["embedding"])

            except Exception as e:
                logger.error(f"Failed to process image {i+1} for staff {staff_id}: {e}")
                return i, f"Image {i+1}: {str(e)}"

        # Process all images concurrently
        processing_tasks = [
            process_single_image(i, image_data)
            for i, image_data in enumerate(face_data.images)
        ]

        results = await asyncio.gather(*processing_tasks, return_exceptions=True)

        # Handle primary image updates (only once)
        if has_primary:
            await db_session.execute(
                update(StaffFaceImage)
                .where(
                    and_(
                        StaffFaceImage.tenant_id == user["tenant_id"],
                        StaffFaceImage.staff_id == staff_id,
                        StaffFaceImage.is_primary,
                    )
                )
                .values(is_primary=False)
            )

        # Process results and add to database
        milvus_embeddings = []
        for index, result in results:
            if isinstance(result, Exception):
                errors.append(f"Image {index+1}: {str(result)}")
                continue

            if isinstance(result, str):
                errors.append(result)
                continue

            face_image, embedding = result
            db_session.add(face_image)

            # Prepare for batch Milvus insertion
            milvus_embeddings.append(
                {
                    "tensor_id": face_image.image_id,
                    "embedding": embedding,
                    "tenant_id": user["tenant_id"],
                    "person_id": staff_id,
                    "person_type": "staff",
                    "created_at": int(datetime.utcnow().timestamp()),
                }
            )

        # Batch insert into Milvus for better performance
        if milvus_embeddings:
            try:
                for emb_data in milvus_embeddings:
                    await milvus_client.insert_embedding(
                        tenant_id=emb_data["tenant_id"],
                        person_id=emb_data["person_id"],
                        person_type=emb_data["person_type"],
                        embedding=emb_data["embedding"],
                        created_at=emb_data["created_at"],
                    )
            except Exception as e:
                logger.error(f"Failed to batch insert embeddings: {e}")
                # Don't fail the entire request for Milvus errors

        # Flush and get IDs
        await db_session.flush()

        # Build response data for successful uploads
        for index, result in results:
            if isinstance(result, str) or isinstance(result, Exception):
                continue

            face_image, _ = result
            await db_session.refresh(face_image)

            response_data = {
                "tenant_id": face_image.tenant_id,
                "image_id": face_image.image_id,
                "staff_id": face_image.staff_id,
                "image_path": face_image.image_path,
                "is_primary": face_image.is_primary,
                "created_at": face_image.created_at,
                "face_landmarks": (
                    json.loads(face_image.face_landmarks)
                    if face_image.face_landmarks
                    else None
                ),
            }

            uploaded_images.append(StaffFaceImageResponse(**response_data))

        await db_session.commit()

        # Return results even with partial failures
        if not uploaded_images and errors:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to upload all images: {'; '.join(errors)}",
            )

        if errors:
            logger.warning(
                f"Bulk upload completed with errors for staff {staff_id}: {errors}"
            )

        return uploaded_images

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload multiple staff face images: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/staff/{staff_id:int}/faces/{image_id}")
async def delete_staff_face_image(
    staff_id: int,
    image_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Delete a staff face image."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Get the face image
    result = await db_session.execute(
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id,
                StaffFaceImage.image_id == image_id,
            )
        )
    )

    face_image = result.scalar_one_or_none()
    if not face_image:
        raise HTTPException(status_code=404, detail="Face image not found")

    try:
        # Delete from database first (this removes the hash constraint immediately)
        await db_session.delete(face_image)

        # Clean up external resources (best effort - don't let failures block DB deletion)
        minio_success = False
        milvus_success = False

        try:
            # Delete from MinIO
            minio_success = await minio_client.delete_file(
                "faces-derived", face_image.image_path
            )
            if not minio_success:
                logger.warning(f"Failed to delete MinIO file: {face_image.image_path}")
        except Exception as e:
            logger.warning(f"MinIO deletion failed: {e}")

        try:
            # Delete embedding from Milvus
            await milvus_client.delete_person_embeddings(user["tenant_id"], staff_id)
            milvus_success = True

            # Re-insert embeddings for remaining images if deletion was successful
            remaining_images = await db_session.execute(
                select(StaffFaceImage).where(
                    and_(
                        StaffFaceImage.tenant_id == user["tenant_id"],
                        StaffFaceImage.staff_id == staff_id,
                        StaffFaceImage.image_id
                        != image_id,  # Exclude the one being deleted
                    )
                )
            )

            for remaining_image in remaining_images.scalars():
                if remaining_image.face_embedding:
                    embedding = json.loads(remaining_image.face_embedding)
                    await milvus_client.insert_embedding(
                        tenant_id=user["tenant_id"],
                        person_id=staff_id,
                        person_type="staff",
                        embedding=embedding,
                        created_at=int(remaining_image.created_at.timestamp()),
                    )
        except Exception as e:
            logger.warning(f"Milvus operations failed: {e}")

        # Commit the database deletion regardless of external cleanup success
        await db_session.commit()

        return {
            "message": "Face image deleted successfully",
            "cleanup_status": {"minio": minio_success, "milvus": milvus_success},
        }

    except Exception as e:
        await db_session.rollback()
        logger.error(f"Failed to delete face image: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete face image")


@router.put("/staff/{staff_id:int}/faces/{image_id}/recalculate")
async def recalculate_face_embedding(
    staff_id: int,
    image_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Recalculate face landmarks and embedding for an existing image."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Get the face image
    result = await db_session.execute(
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id,
                StaffFaceImage.image_id == image_id,
            )
        )
    )

    face_image = result.scalar_one_or_none()
    if not face_image:
        raise HTTPException(status_code=404, detail="Face image not found")

    try:
        # Download image from MinIO
        image_data = await minio_client.download_file(
            "faces-derived", face_image.image_path
        )

        # Convert to base64 for processing
        import base64

        image_b64 = base64.b64encode(image_data).decode("utf-8")

        # Reprocess the image
        processing_result = await face_processing_service.process_staff_face_image(
            base64_image=image_b64, tenant_id=user["tenant_id"], staff_id=staff_id
        )

        if not processing_result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"Face reprocessing failed: {processing_result.get('error', 'Unknown error')}",
            )

        # Update the face image record
        face_image.face_landmarks = json.dumps(processing_result["landmarks"])
        face_image.face_embedding = json.dumps(processing_result["embedding"])
        face_image.updated_at = datetime.utcnow()

        # Update embedding in Milvus
        # Note: Since we don't have metadata support, we delete by person_id and recreate
        await milvus_client.delete_person_embeddings(user["tenant_id"], staff_id)

        await milvus_client.insert_embedding(
            tenant_id=user["tenant_id"],
            person_id=staff_id,
            person_type="staff",
            embedding=processing_result["embedding"],
            created_at=int(datetime.utcnow().timestamp()),
        )

        await db_session.commit()
        await db_session.refresh(face_image)

        return {
            "message": "Face landmarks and embedding recalculated successfully",
            "processing_info": {
                "face_count": processing_result["face_count"],
                "confidence": processing_result["confidence"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recalculate face embedding: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to recalculate face embedding"
        )


@router.post(
    "/staff/{staff_id:int}/test-recognition", response_model=FaceRecognitionTestResponse
)
async def test_face_recognition(
    staff_id: int,
    test_data: FaceRecognitionTestRequest,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Test face recognition accuracy by uploading a test image."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff = staff_result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    try:
        # Get all staff embeddings for comparison
        all_staff_result = await db_session.execute(
            select(StaffFaceImage).where(StaffFaceImage.tenant_id == user["tenant_id"])
        )

        staff_embeddings = []
        for img in all_staff_result.scalars().all():
            if img.face_embedding:
                # Get staff name
                staff_name_result = await db_session.execute(
                    select(Staff.name).where(
                        and_(
                            Staff.tenant_id == user["tenant_id"],
                            Staff.staff_id == img.staff_id,
                        )
                    )
                )
                staff_name = staff_name_result.scalar_one_or_none() or "Unknown"

                staff_embeddings.append(
                    {
                        "staff_id": img.staff_id,
                        "image_id": img.image_id,
                        "name": staff_name,
                        "embedding": json.loads(img.face_embedding),
                    }
                )

        # Test recognition
        recognition_result = await face_processing_service.test_face_recognition(
            test_image_b64=test_data.test_image,
            tenant_id=user["tenant_id"],
            staff_embeddings=staff_embeddings,
        )

        if not recognition_result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"Recognition test failed: {recognition_result.get('error', 'Unknown error')}",
            )

        return FaceRecognitionTestResponse(
            matches=recognition_result["matches"],
            best_match=recognition_result["best_match"],
            processing_info=recognition_result["processing_info"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Face recognition test failed: {e}")
        raise HTTPException(status_code=500, detail="Recognition test failed")


@router.post(
    "/staff/{staff_id:int}/faces/enhanced-upload", response_model=StaffFaceImageResponse
)
async def enhanced_upload_staff_face_image(
    staff_id: int,
    face_data: StaffFaceImageCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Upload a staff face image using enhanced processing pipeline with detailed quality assessment."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    if not staff_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Staff member not found")

    try:
        # Import enhanced face processor
        # Decode base64 image
        import base64

        from ..services.enhanced_face_processor import enhanced_face_processor

        image_bytes = base64.b64decode(face_data.image_data.split(",")[-1])

        # Process with enhanced pipeline
        result = await enhanced_face_processor.process_staff_image(
            image_bytes, staff_id
        )

        if not result["success"]:
            # Return detailed error information
            raise HTTPException(
                status_code=400,
                detail={
                    "error": result.get("error", "Unknown error"),
                    "quality_score": result.get("quality_score", 0.0),
                    "issues": result.get("issues", []),
                    "suggestions": result.get("suggestions", []),
                },
            )

        # Upload processed image to MinIO
        image_filename = f"staff/{user['tenant_id']}/{staff_id}/{result['processing_info']['image_id']}.jpg"

        # Get the processed face crop for storage
        face_crop_b64 = result.get("face_crop_b64")
        if face_crop_b64:
            face_crop_bytes = base64.b64decode(face_crop_b64)
        else:
            face_crop_bytes = image_bytes  # Fallback to original

        await minio_client.upload_file(
            bucket="faces-derived", object_name=image_filename, data=face_crop_bytes
        )

        # If this is set as primary, update existing primary images
        if face_data.is_primary:
            await db_session.execute(
                update(StaffFaceImage)
                .where(
                    and_(
                        StaffFaceImage.tenant_id == user["tenant_id"],
                        StaffFaceImage.staff_id == staff_id,
                        StaffFaceImage.is_primary,
                    )
                )
                .values(is_primary=False)
            )

        # Create face image record with enhanced metadata
        face_image = StaffFaceImage(
            tenant_id=user["tenant_id"],
            image_id=result["processing_info"]["image_id"],
            staff_id=staff_id,
            image_path=image_filename,
            face_landmarks=json.dumps(result.get("face_landmarks")),
            face_embedding=json.dumps(result["embedding"]),
            is_primary=face_data.is_primary,
            # Store enhanced processing metadata
            processing_metadata=json.dumps(
                {
                    "quality_score": result["quality_score"],
                    "confidence": result["confidence"],
                    "detector_used": result.get("detector_used"),
                    "processing_notes": result.get("processing_notes", []),
                    "enhancement_applied": True,
                    "processing_version": "2.0",
                }
            ),
        )

        db_session.add(face_image)

        # Store embedding in Milvus
        await milvus_client.insert_embedding(
            tenant_id=user["tenant_id"],
            person_id=staff_id,
            person_type="staff",
            embedding=result["embedding"],
            created_at=int(datetime.utcnow().timestamp()),
        )

        await db_session.commit()
        await db_session.refresh(face_image)

        # Build enhanced response
        response_data = {
            "tenant_id": face_image.tenant_id,
            "image_id": face_image.image_id,
            "staff_id": face_image.staff_id,
            "image_path": face_image.image_path,
            "is_primary": face_image.is_primary,
            "created_at": face_image.created_at,
            "face_landmarks": (
                json.loads(face_image.face_landmarks)
                if face_image.face_landmarks
                else None
            ),
            # Add enhanced processing information
            "processing_info": {
                "quality_score": result["quality_score"],
                "confidence": result["confidence"],
                "detector_used": result.get("detector_used"),
                "processing_notes": result.get("processing_notes", []),
                "face_bbox": result.get("face_bbox"),
            },
        }

        return StaffFaceImageResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced face image upload failed for staff {staff_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Enhanced processing failed: {str(e)}"
        )


@router.post("/staff/{staff_id:int}/quality-assessment")
async def assess_face_image_quality(
    staff_id: int,
    face_data: StaffFaceImageCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Assess the quality of a face image without uploading it."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    if not staff_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Staff member not found")

    try:
        # Decode base64 image
        import base64

        from ..services.enhanced_face_processor import enhanced_face_processor

        image_bytes = base64.b64decode(face_data.image_data.split(",")[-1])

        # Assess quality only (no storage)
        result = await enhanced_face_processor.assess_image_quality_only(image_bytes)

        return {
            "success": result["success"],
            "quality_score": result.get("quality_score", 0.0),
            "issues": result.get("issues", []),
            "suggestions": result.get("suggestions", []),
            "processing_notes": result.get("processing_notes", []),
            "face_detected": result.get("face_detected", False),
            "detector_used": result.get("detector_used"),
            "confidence": result.get("confidence", 0.0),
            "has_landmarks": result.get("has_landmarks", False),
            "recommended_for_upload": result.get("quality_score", 0.0) >= 0.6,
        }

    except Exception as e:
        logger.error(f"Quality assessment failed for staff {staff_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Quality assessment failed: {str(e)}"
        )
