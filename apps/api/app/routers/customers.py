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
    
    # Get customers first
    result = await db_session.execute(
        select(Customer)
        .where(Customer.tenant_id == user["tenant_id"])
        .order_by(Customer.last_seen.desc())
        .limit(limit)
        .offset(offset)
    )
    customers = result.scalars().all()
    
    # Get avatar URLs for each customer by fetching their best face image
    customer_responses = []
    for customer in customers:
        avatar_url = None
        
        try:
            # Get the best face image for this customer (highest confidence + quality)
            from ..models.database import CustomerFaceImage
            from sqlalchemy import func, desc
            
            face_result = await db_session.execute(
                select(CustomerFaceImage.image_path)
                .where(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer.customer_id
                )
                .order_by(
                    desc(CustomerFaceImage.confidence_score + 
                         func.coalesce(CustomerFaceImage.quality_score, 0.5))
                )
                .limit(1)
            )
            
            face_image = face_result.scalar_one_or_none()
            if face_image:
                # Generate MinIO presigned URL for the avatar
                from ..core.minio_client import minio_client
                import asyncio
                
                try:
                    avatar_url = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        minio_client.get_presigned_url,
                        "faces-derived",  # Use derived bucket for processed face images
                        face_image,
                        3600  # 1 hour expiry
                    )
                except Exception as url_error:
                    logger.debug(f"Could not generate avatar URL for customer {customer.customer_id}: {url_error}")
                    
        except Exception as e:
            logger.debug(f"Could not fetch avatar for customer {customer.customer_id}: {e}")
        
        # Create customer response with avatar URL
        customer_response = CustomerResponse(
            customer_id=customer.customer_id,
            tenant_id=customer.tenant_id,
            name=customer.name,
            gender=customer.gender,
            estimated_age_range=customer.estimated_age_range,
            phone=customer.phone,
            email=customer.email,
            first_seen=customer.first_seen,
            last_seen=customer.last_seen,
            visit_count=customer.visit_count,
            avatar_url=avatar_url
        )
        customer_responses.append(customer_response)
    
    return customer_responses


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
    
    # Get avatar URL for this customer
    avatar_url = None
    try:
        from ..models.database import CustomerFaceImage
        from sqlalchemy import func, desc
        
        face_result = await db_session.execute(
            select(CustomerFaceImage.image_path)
            .where(
                CustomerFaceImage.tenant_id == user["tenant_id"],
                CustomerFaceImage.customer_id == customer_id
            )
            .order_by(
                desc(CustomerFaceImage.confidence_score + 
                     func.coalesce(CustomerFaceImage.quality_score, 0.5))
            )
            .limit(1)
        )
        
        face_image = face_result.scalar_one_or_none()
        if face_image:
            from ..core.minio_client import minio_client
            import asyncio
            
            try:
                avatar_url = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    minio_client.get_presigned_url,
                    "faces-derived",
                    face_image,
                    3600  # 1 hour expiry
                )
            except Exception as url_error:
                logger.debug(f"Could not generate avatar URL for customer {customer_id}: {url_error}")
                
    except Exception as e:
        logger.debug(f"Could not fetch avatar for customer {customer_id}: {e}")
    
    return CustomerResponse(
        customer_id=customer.customer_id,
        tenant_id=customer.tenant_id,
        name=customer.name,
        gender=customer.gender,
        estimated_age_range=customer.estimated_age_range,
        phone=customer.phone,
        email=customer.email,
        first_seen=customer.first_seen,
        last_seen=customer.last_seen,
        visit_count=customer.visit_count,
        avatar_url=avatar_url
    )


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
    
    logger.info(f"🗑️ Starting comprehensive deletion of customer {customer_id}")
    
    try:
        # 1. Delete customer face images from storage and database
        logger.info(f"🗑️ Deleting customer face images for customer {customer_id}")
        from ..models.database import CustomerFaceImage
        from ..core.minio_client import minio_client
        import asyncio
        
        # Get all face images for this customer
        face_images_result = await db_session.execute(
            select(CustomerFaceImage).where(
                CustomerFaceImage.tenant_id == user["tenant_id"],
                CustomerFaceImage.customer_id == customer_id
            )
        )
        face_images = face_images_result.scalars().all()
        
        # Delete images from MinIO storage
        deleted_images_count = 0
        for face_image in face_images:
            try:
                # Delete from faces-derived bucket
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    minio_client.remove_object,
                    "faces-derived",
                    face_image.image_path
                )
                deleted_images_count += 1
            except Exception as storage_error:
                logger.warning(f"Failed to delete face image {face_image.image_path} from storage: {storage_error}")
        
        # Delete face image records from database
        await db_session.execute(
            delete(CustomerFaceImage).where(
                CustomerFaceImage.tenant_id == user["tenant_id"],
                CustomerFaceImage.customer_id == customer_id
            )
        )
        logger.info(f"🗑️ Deleted {deleted_images_count} face images from storage and {len(face_images)} records from database")
        
        # 2. Delete customer visits
        logger.info(f"🗑️ Deleting visits for customer {customer_id}")
        from ..models.database import Visit
        
        # Get visit count before deletion
        visits_result = await db_session.execute(
            select(func.count(Visit.visit_id)).where(
                Visit.tenant_id == user["tenant_id"],
                Visit.person_id == customer_id,
                Visit.person_type == "customer"
            )
        )
        visits_count = visits_result.scalar() or 0
        
        # Delete visits
        await db_session.execute(
            delete(Visit).where(
                Visit.tenant_id == user["tenant_id"],
                Visit.person_id == customer_id,
                Visit.person_type == "customer"
            )
        )
        logger.info(f"🗑️ Deleted {visits_count} visit records")
        
        # 3. Delete customer embeddings from Milvus
        logger.info(f"🗑️ Deleting customer embeddings from Milvus for customer {customer_id}")
        try:
            await milvus_client.delete_person_embeddings(user["tenant_id"], customer_id, "customer")
            logger.info(f"🗑️ Successfully deleted customer embeddings from Milvus")
        except Exception as e:
            logger.warning(f"Failed to delete customer embeddings from Milvus: {e}")
        
        # 4. Finally, delete the customer record
        logger.info(f"🗑️ Deleting customer record {customer_id}")
        await db_session.delete(customer)
        
        # Commit all changes
        await db_session.commit()
        
        logger.info(f"✅ Successfully deleted customer {customer_id} and all related data:")
        logger.info(f"   - Customer record: 1")
        logger.info(f"   - Face images: {len(face_images)} records, {deleted_images_count} files")
        logger.info(f"   - Visit records: {visits_count}")
        logger.info(f"   - Milvus embeddings: cleaned up")
        
        return {
            "message": "Customer deleted successfully", 
            "details": {
                "customer_id": customer_id,
                "deleted_face_images": len(face_images),
                "deleted_face_files": deleted_images_count,
                "deleted_visits": visits_count,
                "embeddings_cleaned": True
            }
        }
        
    except Exception as e:
        # Rollback on error
        await db_session.rollback()
        logger.error(f"❌ Error during customer deletion: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to delete customer: {str(e)}"
        )


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
        
        # Convert to response format with presigned URLs
        from ..core.minio_client import minio_client
        import logging
        
        logger = logging.getLogger(__name__)
        images = []
        for img in face_images:
            # Generate presigned URL for the image
            image_url = None
            if img.image_path:
                try:
                    # Handle both old (customer-faces/ prefix) and new (direct path) formats
                    if img.image_path.startswith('customer-faces/'):
                        # Legacy format - remove the prefix
                        object_path = img.image_path.replace('customer-faces/', '')
                    else:
                        # New format - use path directly
                        object_path = img.image_path
                    image_url = minio_client.get_presigned_url('faces-derived', object_path)
                except Exception as e:
                    logger.warning(f"Failed to generate presigned URL for {img.image_path}: {e}")
                    image_url = None
            
            images.append({
                "image_id": img.image_id,
                "image_path": image_url,  # Return presigned URL instead of raw path
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

@router.post("/customers/{customer_id:int}/face-images/cleanup")
async def cleanup_customer_face_images(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Clean up excess face images for a specific customer"""
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
        
        cleaned_count = await customer_face_service.cleanup_excess_images_for_customer(
            db_session, user["tenant_id"], customer_id
        )
        
        return {
            "customer_id": customer_id,
            "images_cleaned": cleaned_count,
            "message": f"Cleaned up {cleaned_count} excess face image(s) for customer {customer_id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup customer face images: {str(e)}")


@router.post("/customers/face-images/cleanup-all")
async def cleanup_all_customer_face_images(
    limit: int = Query(100, description="Maximum number of customers to process"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Clean up excess face images for all customers in the tenant"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    try:
        from ..services.customer_face_service import customer_face_service
        
        result = await customer_face_service.cleanup_all_excess_images(
            db_session, user["tenant_id"], limit
        )
        
        return {
            "tenant_id": user["tenant_id"],
            **result,
            "message": f"Processed {result['customers_processed']} customers, cleaned {result['total_images_cleaned']} excess images"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup customer face images: {str(e)}")


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

@router.post("/customers/{customer_id:int}/face-images/batch-delete")
async def delete_customer_face_images_batch(
    customer_id: int,
    request: dict,  # Accept JSON body instead of query params
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Delete multiple face images for a customer"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Extract image_ids from JSON body
    image_ids = request.get("image_ids", [])
    
    if not image_ids:
        raise HTTPException(status_code=400, detail="No image IDs provided")
    
    # Validate that all IDs are integers
    try:
        image_ids = [int(id) for id in image_ids]
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="All image IDs must be valid integers")
    
    logger.info(f"Batch deleting face images: customer_id={customer_id}, image_ids={image_ids}")
    
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
        found_ids = [img.image_id for img in face_images]
        logger.info(f"Found {len(face_images)} images to delete: {found_ids}")
        
        if not face_images:
            logger.warning(f"No face images found for deletion: requested={image_ids}")
            raise HTTPException(status_code=404, detail="No face images found")
        
        # Delete each image with individual transaction handling
        from ..services.customer_face_service import customer_face_service
        deleted_count = 0
        failed_deletions = []
        
        for face_image in face_images:
            try:
                logger.info(f"Deleting face image {face_image.image_id}")
                
                # Delete content from MinIO first
                await customer_face_service._delete_face_image_content_only(face_image)
                
                # Delete from database
                await db_session.delete(face_image)
                deleted_count += 1
                logger.info(f"✅ Successfully marked image {face_image.image_id} for deletion")
                
            except Exception as e:
                logger.error(f"❌ Failed to delete face image {face_image.image_id}: {e}")
                failed_deletions.append((face_image.image_id, str(e)))
        
        # Commit all deletions at once
        if deleted_count > 0:
            await db_session.commit()
            logger.info(f"✅ Committed deletion of {deleted_count} face images")
        else:
            logger.warning("No images were successfully deleted")
        
        # Report results
        if failed_deletions:
            logger.warning(f"Failed to delete {len(failed_deletions)} images: {failed_deletions}")
        
        return {
            "message": f"Successfully deleted {deleted_count} face images" + 
                      (f" ({len(failed_deletions)} failed)" if failed_deletions else ""),
            "deleted_count": deleted_count,
            "requested_count": len(image_ids),
            "failed_deletions": [{"image_id": img_id, "error": error} for img_id, error in failed_deletions] if failed_deletions else []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Critical error during batch deletion: {e}")
        # Ensure rollback on error
        await db_session.rollback()
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