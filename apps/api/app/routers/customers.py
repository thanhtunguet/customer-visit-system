import logging
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.milvus_client import milvus_client
from ..core.security import get_current_user
from ..models.database import Customer
from ..schemas import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter(prefix="/v1", tags=["Customer Management"])
logger = logging.getLogger(__name__)


@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Customer)
        .where(Customer.tenant_id == user["tenant_id"])
        .order_by(Customer.last_seen.desc())
        .limit(limit)
        .offset(offset)
    )
    customers = result.scalars().all()
    return customers


@router.post("/customers", response_model=CustomerResponse)
async def create_customer(
    customer: CustomerCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    new_customer = Customer(
        tenant_id=user["tenant_id"],
        name=customer.name,
        gender=customer.gender,
        estimated_age_range=customer.estimated_age_range,
        phone=customer.phone,
        email=customer.email
    )
    db_session.add(new_customer)
    await db_session.commit()
    await db_session.refresh(new_customer)
    return new_customer


@router.get("/customers/{customer_id:int}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Customer).where(
            and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id)
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return customer


@router.put("/customers/{customer_id:int}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_update: CustomerUpdate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Customer).where(
            and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id)
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Update customer fields
    if customer_update.name is not None:
        customer.name = customer_update.name
    if customer_update.gender is not None:
        customer.gender = customer_update.gender
    if customer_update.estimated_age_range is not None:
        customer.estimated_age_range = customer_update.estimated_age_range
    if customer_update.phone is not None:
        customer.phone = customer_update.phone
    if customer_update.email is not None:
        customer.email = customer_update.email
    
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


@router.delete("/customers/{customer_id:int}")
async def delete_customer(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Customer).where(
            and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id)
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Delete customer embeddings from Milvus
    try:
        await milvus_client.delete_person_embeddings(user["tenant_id"], customer_id)
    except Exception as e:
        logger.warning(f"Failed to delete customer embeddings from Milvus: {e}")
    
    await db_session.delete(customer)
    await db_session.commit()
    return {"message": "Customer deleted successfully"}


# Customer Face Gallery Endpoints

@router.get("/customers/{customer_id:int}/face-images")
async def get_customer_face_images(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get face images for a customer"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Verify customer exists
    customer = await db_session.execute(
        select(Customer).where(
            and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id)
        )
    )
    if not customer.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer not found")
    
    try:
        from ..services.customer_face_service import customer_face_service
        
        face_images = await customer_face_service.get_customer_face_images(
            db_session, user["tenant_id"], customer_id
        )
        
        # Convert to response format
        images = []
        for img in face_images:
            images.append({
                "image_id": img.image_id,
                "image_path": img.image_path,
                "confidence_score": img.confidence_score,
                "quality_score": img.quality_score,
                "created_at": img.created_at.isoformat(),
                "visit_id": img.visit_id,
                "face_bbox": img.face_bbox,
                "detection_metadata": img.detection_metadata
            })
        
        return {
            "customer_id": customer_id,
            "total_images": len(images),
            "images": images
        }
        
    except Exception as e:
        logger.error(f"Error getting customer face images: {e}")
        raise HTTPException(status_code=500, detail="Failed to get customer face images")


@router.delete("/customers/{customer_id:int}/face-images/{image_id:int}")
async def delete_customer_face_image(
    customer_id: int,
    image_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Delete a specific face image for a customer"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    try:
        from ..models.database import CustomerFaceImage
        
        # Find and delete the face image
        result = await db_session.execute(
            select(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id,
                    CustomerFaceImage.image_id == image_id
                )
            )
        )
        
        face_image = result.scalar_one_or_none()
        if not face_image:
            raise HTTPException(status_code=404, detail="Face image not found")
        
        # Delete from MinIO
        from ..services.customer_face_service import customer_face_service
        await customer_face_service._delete_face_image(db_session, face_image)
        
        await db_session.commit()
        
        return {"message": "Face image deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer face image: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete face image")

@router.delete("/customers/{customer_id:int}/face-images")
async def delete_customer_face_images_batch(
    customer_id: int,
    image_ids: List[int] = Query(..., description="List of image IDs to delete"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Delete multiple face images for a customer"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    if not image_ids:
        raise HTTPException(status_code=400, detail="No image IDs provided")
    
    try:
        from ..models.database import CustomerFaceImage
        
        # Find all face images to delete
        result = await db_session.execute(
            select(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id,
                    CustomerFaceImage.image_id.in_(image_ids)
                )
            )
        )
        
        face_images = result.scalars().all()
        if not face_images:
            raise HTTPException(status_code=404, detail="No face images found")
        
        # Delete each image
        from ..services.customer_face_service import customer_face_service
        deleted_count = 0
        
        for face_image in face_images:
            try:
                await customer_face_service._delete_face_image(db_session, face_image)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete face image {face_image.image_id}: {e}")
        
        await db_session.commit()
        
        return {
            "message": f"Successfully deleted {deleted_count} face images",
            "deleted_count": deleted_count,
            "requested_count": len(image_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer face images: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete face images")


@router.get("/customers/{customer_id:int}/face-gallery-stats")
async def get_customer_face_gallery_stats(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get statistics about a customer's face gallery"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    try:
        from ..models.database import CustomerFaceImage
        from sqlalchemy import func
        
        # Get gallery statistics
        stats_query = await db_session.execute(
            select(
                func.count(CustomerFaceImage.image_id).label('total_images'),
                func.avg(CustomerFaceImage.confidence_score).label('avg_confidence'),
                func.max(CustomerFaceImage.confidence_score).label('max_confidence'),
                func.min(CustomerFaceImage.confidence_score).label('min_confidence'),
                func.avg(CustomerFaceImage.quality_score).label('avg_quality'),
                func.min(CustomerFaceImage.created_at).label('first_image'),
                func.max(CustomerFaceImage.created_at).label('latest_image')
            ).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id
                )
            )
        )
        
        stats = stats_query.first()
        
        return {
            "customer_id": customer_id,
            "total_images": stats.total_images or 0,
            "avg_confidence": round(float(stats.avg_confidence or 0), 3),
            "max_confidence": round(float(stats.max_confidence or 0), 3),
            "min_confidence": round(float(stats.min_confidence or 0), 3),
            "avg_quality": round(float(stats.avg_quality or 0), 3),
            "first_image_date": stats.first_image.isoformat() if stats.first_image else None,
            "latest_image_date": stats.latest_image.isoformat() if stats.latest_image else None,
            "gallery_limit": settings.max_customer_face_images
        }
        
    except Exception as e:
        logger.error(f"Error getting customer face gallery stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get gallery statistics")