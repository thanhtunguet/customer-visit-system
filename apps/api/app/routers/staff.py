import json
import logging
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.milvus_client import milvus_client
from ..core.minio_client import minio_client
from ..core.security import get_current_user
from ..models.database import Staff, StaffFaceImage
from ..schemas import (
    StaffCreate, StaffResponse, StaffFaceImageCreate, StaffFaceImageResponse,
    StaffWithFacesResponse, FaceRecognitionTestRequest, FaceRecognitionTestResponse
)
from ..services.face_service import staff_service
from ..services.face_processing_service import face_processing_service

router = APIRouter(prefix="/v1", tags=["Staff Management"])
logger = logging.getLogger(__name__)


@router.get("/staff", response_model=List[StaffResponse])
async def list_staff(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
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
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Generate staff ID
    staff_id = f"staff-{uuid.uuid4().hex[:8]}"
    
    # Create staff member
    new_staff = Staff(
        tenant_id=user["tenant_id"],
        staff_id=staff_id,
        name=staff.name,
        site_id=staff.site_id
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
            site_id=staff.site_id
        )
    
    # Return the created staff member
    return new_staff


@router.get("/staff/{staff_id}", response_model=StaffResponse)
async def get_staff_member(
    staff_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
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


@router.put("/staff/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: str,
    staff_update: StaffCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
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
            update_existing=True
        )
    
    await db_session.commit()
    await db_session.refresh(staff_member)
    return staff_member


@router.delete("/staff/{staff_id}")
async def delete_staff(
    staff_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
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

@router.get("/staff/{staff_id}/faces", response_model=List[StaffFaceImageResponse])
async def get_staff_face_images(
    staff_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
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
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id
            )
        ).order_by(StaffFaceImage.created_at.desc())
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
            "face_landmarks": json.loads(img.face_landmarks) if img.face_landmarks else None
        }
        response_images.append(StaffFaceImageResponse(**response_data))
    
    return response_images


@router.get("/staff/{staff_id}/details", response_model=StaffWithFacesResponse)
async def get_staff_with_faces(
    staff_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
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
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id
            )
        ).order_by(StaffFaceImage.created_at.desc())
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
            "face_landmarks": json.loads(img.face_landmarks) if img.face_landmarks else None
        }
        response_images.append(StaffFaceImageResponse(**response_data))
    
    staff_data = {
        "tenant_id": staff.tenant_id,
        "staff_id": staff.staff_id,
        "name": staff.name,
        "site_id": staff.site_id,
        "is_active": staff.is_active,
        "created_at": staff.created_at,
        "face_images": response_images
    }
    
    return StaffWithFacesResponse(**staff_data)


@router.post("/staff/{staff_id}/faces", response_model=StaffFaceImageResponse)
async def upload_staff_face_image(
    staff_id: str,
    face_data: StaffFaceImageCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
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
        # Process face image
        processing_result = await face_processing_service.process_staff_face_image(
            base64_image=face_data.image_data,
            tenant_id=user["tenant_id"],
            staff_id=staff_id
        )
        
        if not processing_result['success']:
            raise HTTPException(
                status_code=400, 
                detail=f"Face processing failed: {processing_result.get('error', 'Unknown error')}"
            )
        
        # If this is set as primary, update existing primary images
        if face_data.is_primary:
            await db_session.execute(
                update(StaffFaceImage)
                .where(
                    and_(
                        StaffFaceImage.tenant_id == user["tenant_id"],
                        StaffFaceImage.staff_id == staff_id,
                        StaffFaceImage.is_primary == True
                    )
                )
                .values(is_primary=False)
            )
        
        # Create face image record
        face_image = StaffFaceImage(
            tenant_id=user["tenant_id"],
            image_id=processing_result['image_id'],
            staff_id=staff_id,
            image_path=processing_result['image_path'],
            face_landmarks=json.dumps(processing_result['landmarks']),
            face_embedding=json.dumps(processing_result['embedding']),
            is_primary=face_data.is_primary
        )
        
        db_session.add(face_image)
        
        # Store embedding in Milvus
        await milvus_client.insert_embedding(
            tenant_id=user["tenant_id"],
            person_id=staff_id,
            person_type="staff",
            embedding=processing_result['embedding'],
            created_at=int(datetime.utcnow().timestamp())
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
            "face_landmarks": json.loads(face_image.face_landmarks) if face_image.face_landmarks else None
        }
        
        return StaffFaceImageResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload staff face image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/staff/{staff_id}/faces/{image_id}")
async def delete_staff_face_image(
    staff_id: str,
    image_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Delete a staff face image."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Get the face image
    result = await db_session.execute(
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id,
                StaffFaceImage.image_id == image_id
            )
        )
    )
    
    face_image = result.scalar_one_or_none()
    if not face_image:
        raise HTTPException(status_code=404, detail="Face image not found")
    
    try:
        # Delete from MinIO
        await minio_client.delete_file("faces-derived", face_image.image_path)
        
        # Delete embedding from Milvus 
        # Note: Since we don't have metadata support, we delete by person_id
        # This will delete all embeddings for this staff member
        await milvus_client.delete_person_embeddings(user["tenant_id"], staff_id)
        
        # Delete from database
        await db_session.delete(face_image)
        await db_session.commit()
        
        return {"message": "Face image deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete face image: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete face image")


@router.put("/staff/{staff_id}/faces/{image_id}/recalculate")
async def recalculate_face_embedding(
    staff_id: str,
    image_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Recalculate face landmarks and embedding for an existing image."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Get the face image
    result = await db_session.execute(
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id,
                StaffFaceImage.image_id == image_id
            )
        )
    )
    
    face_image = result.scalar_one_or_none()
    if not face_image:
        raise HTTPException(status_code=404, detail="Face image not found")
    
    try:
        # Download image from MinIO
        image_data = await minio_client.download_file("faces-derived", face_image.image_path)
        
        # Convert to base64 for processing
        import base64
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        # Reprocess the image
        processing_result = await face_processing_service.process_staff_face_image(
            base64_image=image_b64,
            tenant_id=user["tenant_id"],
            staff_id=staff_id
        )
        
        if not processing_result['success']:
            raise HTTPException(
                status_code=400, 
                detail=f"Face reprocessing failed: {processing_result.get('error', 'Unknown error')}"
            )
        
        # Update the face image record
        face_image.face_landmarks = json.dumps(processing_result['landmarks'])
        face_image.face_embedding = json.dumps(processing_result['embedding'])
        face_image.updated_at = datetime.utcnow()
        
        # Update embedding in Milvus
        # Note: Since we don't have metadata support, we delete by person_id and recreate
        await milvus_client.delete_person_embeddings(user["tenant_id"], staff_id)
        
        await milvus_client.insert_embedding(
            tenant_id=user["tenant_id"],
            person_id=staff_id,
            person_type="staff",
            embedding=processing_result['embedding'],
            created_at=int(datetime.utcnow().timestamp())
        )
        
        await db_session.commit()
        await db_session.refresh(face_image)
        
        return {
            "message": "Face landmarks and embedding recalculated successfully",
            "processing_info": {
                "face_count": processing_result['face_count'],
                "confidence": processing_result['confidence']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recalculate face embedding: {e}")
        raise HTTPException(status_code=500, detail="Failed to recalculate face embedding")


@router.post("/staff/{staff_id}/test-recognition", response_model=FaceRecognitionTestResponse)
async def test_face_recognition(
    staff_id: str,
    test_data: FaceRecognitionTestRequest,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
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
            select(StaffFaceImage).where(
                StaffFaceImage.tenant_id == user["tenant_id"]
            )
        )
        
        staff_embeddings = []
        for img in all_staff_result.scalars().all():
            if img.face_embedding:
                # Get staff name
                staff_name_result = await db_session.execute(
                    select(Staff.name).where(
                        and_(
                            Staff.tenant_id == user["tenant_id"],
                            Staff.staff_id == img.staff_id
                        )
                    )
                )
                staff_name = staff_name_result.scalar_one_or_none() or "Unknown"
                
                staff_embeddings.append({
                    'staff_id': img.staff_id,
                    'image_id': img.image_id,
                    'name': staff_name,
                    'embedding': json.loads(img.face_embedding)
                })
        
        # Test recognition
        recognition_result = await face_processing_service.test_face_recognition(
            test_image_b64=test_data.test_image,
            tenant_id=user["tenant_id"],
            staff_embeddings=staff_embeddings
        )
        
        if not recognition_result['success']:
            raise HTTPException(
                status_code=400,
                detail=f"Recognition test failed: {recognition_result.get('error', 'Unknown error')}"
            )
        
        return FaceRecognitionTestResponse(
            matches=recognition_result['matches'],
            best_match=recognition_result['best_match'],
            processing_info=recognition_result['processing_info']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Face recognition test failed: {e}")
        raise HTTPException(status_code=500, detail="Recognition test failed")