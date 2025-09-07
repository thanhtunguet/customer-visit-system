import logging
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select, and_, delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.milvus_client import milvus_client
from ..core.security import get_current_user
from ..core.config import settings
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
            logger.info(f"Customer {customer.customer_id}: Found face image path: {face_image}")
            if face_image:
                # Generate MinIO presigned URL for the avatar
                from ..core.minio_client import minio_client
                import asyncio
                
                try:
                    from datetime import timedelta
                    avatar_url = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        minio_client.get_presigned_url,
                        "faces-derived",  # Use derived bucket for processed face images
                        face_image,
                        timedelta(hours=1)  # 1 hour expiry
                    )
                except Exception as url_error:
                    logger.error(f"Could not generate avatar URL for customer {customer.customer_id}: {url_error}")
                    logger.error(f"Face image path was: {face_image}")
                    
        except Exception as e:
            logger.error(f"Could not fetch avatar for customer {customer.customer_id}: {e}")
        
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
                from datetime import timedelta
                avatar_url = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    minio_client.get_presigned_url,
                    "faces-derived",
                    face_image,
                    timedelta(hours=1)  # 1 hour expiry
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
            "gallery_limit": settings.max_face_images
        }
        
    except Exception as e:
        logger.error(f"Error getting customer face gallery stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get gallery statistics")


@router.get("/customers/face-images/debug")
async def debug_customer_face_images(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Debug endpoint to check customer face images status"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    try:
        from ..models.database import CustomerFaceImage
        
        # Count total face images
        total_result = await db_session.execute(
            select(func.count(CustomerFaceImage.image_id)).where(
                CustomerFaceImage.tenant_id == user["tenant_id"]
            )
        )
        total_images = total_result.scalar()
        
        # Count customers with face images
        customers_with_images_result = await db_session.execute(
            select(func.count(func.distinct(CustomerFaceImage.customer_id))).where(
                CustomerFaceImage.tenant_id == user["tenant_id"]
            )
        )
        customers_with_images = customers_with_images_result.scalar()
        
        # Get sample of recent images
        recent_images_result = await db_session.execute(
            select(
                CustomerFaceImage.customer_id,
                CustomerFaceImage.image_path,
                CustomerFaceImage.confidence_score,
                CustomerFaceImage.created_at
            ).where(
                CustomerFaceImage.tenant_id == user["tenant_id"]
            ).order_by(desc(CustomerFaceImage.created_at)).limit(5)
        )
        recent_images = recent_images_result.fetchall()
        
        return {
            "tenant_id": user["tenant_id"],
            "total_face_images": total_images,
            "customers_with_images": customers_with_images,
            "recent_images": [
                {
                    "customer_id": img.customer_id,
                    "image_path": img.image_path,
                    "confidence_score": img.confidence_score,
                    "created_at": img.created_at.isoformat()
                }
                for img in recent_images
            ],
            "message": f"Found {total_images} face images for {customers_with_images} customers"
        }
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@router.post("/customers/{customer_id:int}/face-images/backfill")
async def backfill_customer_face_images(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Backfill customer face images from existing visits"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    try:
        # Verify customer exists
        from ..models.database import Customer, Visit
        customer_result = await db_session.execute(
            select(Customer).where(
                Customer.tenant_id == user["tenant_id"],
                Customer.customer_id == customer_id
            )
        )
        customer = customer_result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Find recent visits with face images for this customer  
        from sqlalchemy import desc
        visits_result = await db_session.execute(
            select(Visit).where(
                Visit.tenant_id == user["tenant_id"],
                Visit.person_id == customer_id,
                Visit.person_type == "customer",
                Visit.image_path != None,
                Visit.confidence_score >= 0.7
            ).order_by(desc(Visit.confidence_score)).limit(3)
        )
        visits = visits_result.scalars().all()
        
        if not visits:
            return {
                "message": "No visits with face images found for backfilling",
                "customer_id": customer_id,
                "visits_processed": 0
            }
        
        # Process each visit and try to save face image
        from ..services.customer_face_service import customer_face_service
        from ..core.minio_client import minio_client
        import asyncio
        
        processed = 0
        for visit in visits:
            try:
                logger.info(f"Processing visit {visit.visit_id} for customer {customer_id}")
                
                # Download the face image from MinIO synchronously
                def download_sync():
                    try:
                        response = minio_client.client.get_object("faces-raw", visit.image_path)
                        data = response.read()
                        response.close()
                        response.release_conn()
                        return data
                    except Exception as e:
                        logger.warning(f"Failed to download face image from MinIO: {e}")
                        return None
                
                face_image_bytes = download_sync()
                
                if not face_image_bytes:
                    logger.warning(f"Could not download face image from {visit.image_path}")
                    continue
                
                # Construct bbox from individual components
                bbox = []
                if all(x is not None for x in [visit.bbox_x, visit.bbox_y, visit.bbox_w, visit.bbox_h]):
                    bbox = [visit.bbox_x, visit.bbox_y, visit.bbox_w, visit.bbox_h]
                else:
                    bbox = [0, 0, 100, 100]  # Default bbox if missing
                
                # Parse face embedding from JSON string
                embedding = []
                if visit.face_embedding:
                    try:
                        import json
                        embedding = json.loads(visit.face_embedding)
                    except Exception as e:
                        logger.warning(f"Failed to parse face embedding for visit {visit.visit_id}: {e}")
                        embedding = [0.0] * 512  # Default embedding
                else:
                    embedding = [0.0] * 512  # Default embedding
                
                # Try to save to customer face gallery
                result = await customer_face_service.add_face_image(
                    db=db_session,
                    tenant_id=user["tenant_id"],
                    customer_id=customer_id,
                    image_data=face_image_bytes,
                    confidence_score=visit.confidence_score,
                    face_bbox=bbox,
                    embedding=embedding,
                    visit_id=visit.visit_id,
                    metadata={
                        "source": "backfill_from_visit",
                        "visit_id": visit.visit_id
                    }
                )
                
                if result:
                    logger.info(f"✅ Successfully saved face image from visit {visit.visit_id}")
                    processed += 1
                else:
                    logger.warning(f"❌ Failed to save face image from visit {visit.visit_id}")
                    
            except Exception as e:
                logger.error(f"Error processing visit {visit.visit_id}: {e}")
                continue
        
        # Commit all changes
        if processed > 0:
            await db_session.commit()
        
        return {
            "message": f"Backfilled {processed} face images for customer {customer_id}",
            "customer_id": customer_id,
            "visits_processed": processed,
            "total_visits_found": len(visits)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backfill endpoint: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Backfill failed: {str(e)}")

# Customer Data Cleanup Endpoints

@router.get("/customers/{customer_id:int}/similar")
async def find_similar_customers(
    customer_id: int,
    threshold: float = Query(0.85, description="Similarity threshold for matching"),
    limit: int = Query(10, description="Maximum number of similar customers to return"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Find customers that are likely the same person based on face embeddings"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    try:
        from ..models.database import CustomerFaceImage
        from ..core.milvus_client import milvus_client
        import json
        
        # Get target customer
        customer_result = await db_session.execute(
            select(Customer).where(
                and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id)
            )
        )
        customer = customer_result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Get face images for target customer
        face_result = await db_session.execute(
            select(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id
                )
            ).limit(5)  # Use top 5 face images for comparison
        )
        face_images = face_result.scalars().all()
        
        if not face_images:
            return {
                "customer_id": customer_id,
                "similar_customers": [],
                "message": "No face images found for comparison"
            }
        
        similar_customers = []
        
        # For each face image, search for similar faces in Milvus
        for face_img in face_images:
            # Embedding is stored as JSON in CustomerFaceImage.embedding
            if not getattr(face_img, 'embedding', None):
                continue
                
            try:
                # Already a JSON array; ensure it's a list of floats
                embedding = face_img.embedding
                
                # Search similar faces in Milvus
                search_results = await milvus_client.search_similar_faces(
                    tenant_id=user["tenant_id"],
                    embedding=embedding,
                    limit=limit * 2,  # Get more results to filter out self
                    threshold=threshold,
                )
                
                for result in search_results:
                    # Filter to customer matches only
                    if result.get('person_type') != 'customer':
                        continue
                    result_customer_id = result.get('person_id')
                    similarity_score = float(result.get('similarity', 0))
                    
                    # Skip self-matches
                    if result_customer_id == customer_id:
                        continue
                    
                    # Add to similar customers if not already present
                    existing = next((c for c in similar_customers if c['customer_id'] == result_customer_id), None)
                    if not existing:
                        # Get customer details
                        other_customer_result = await db_session.execute(
                            select(Customer).where(
                                and_(
                                    Customer.tenant_id == user["tenant_id"],
                                    Customer.customer_id == result_customer_id
                                )
                            )
                        )
                        other_customer = other_customer_result.scalar_one_or_none()
                        
                        if other_customer:
                            similar_customers.append({
                                "customer_id": other_customer.customer_id,
                                "name": other_customer.name,
                                "visit_count": other_customer.visit_count,
                                "first_seen": other_customer.first_seen.isoformat() if other_customer.first_seen else None,
                                "last_seen": other_customer.last_seen.isoformat() if other_customer.last_seen else None,
                                "max_similarity": similarity_score,
                                "gender": other_customer.gender,
                                "estimated_age_range": other_customer.estimated_age_range
                            })
                    elif similarity_score > existing['max_similarity']:
                        existing['max_similarity'] = similarity_score
                        
            except Exception as e:
                logger.warning(f"Error searching similar faces for image {face_img.image_id}: {e}")
                continue
        
        # Sort by similarity score and limit results
        similar_customers.sort(key=lambda x: x['max_similarity'], reverse=True)
        similar_customers = similar_customers[:limit]
        
        return {
            "customer_id": customer_id,
            "customer_name": customer.name,
            "similar_customers": similar_customers,
            "threshold_used": threshold,
            "total_found": len(similar_customers)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar customers: {e}")
        raise HTTPException(status_code=500, detail="Failed to find similar customers")


@router.post("/customers/merge")
async def merge_customers(
    request: dict,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Merge two customers that are the same person"""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    primary_customer_id = request.get("primary_customer_id")
    secondary_customer_id = request.get("secondary_customer_id")
    merge_notes = request.get("notes", "")
    
    if not primary_customer_id or not secondary_customer_id:
        raise HTTPException(
            status_code=400, 
            detail="Both primary_customer_id and secondary_customer_id are required"
        )
    
    if primary_customer_id == secondary_customer_id:
        raise HTTPException(status_code=400, detail="Cannot merge customer with itself")
    
    try:
        # Get both customers
        customers_result = await db_session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id.in_([primary_customer_id, secondary_customer_id])
                )
            )
        )
        customers = {c.customer_id: c for c in customers_result.scalars().all()}
        
        if len(customers) != 2:
            raise HTTPException(status_code=404, detail="One or both customers not found")
        
        primary_customer = customers[primary_customer_id]
        secondary_customer = customers[secondary_customer_id]
        
        # Begin transaction for merge operation
        from ..models.database import Visit, CustomerFaceImage
        
        # Update all visits from secondary to primary customer
        visit_update_result = await db_session.execute(
            select(func.count(Visit.visit_id)).where(
                and_(
                    Visit.tenant_id == user["tenant_id"],
                    Visit.person_id == secondary_customer_id,
                    Visit.person_type == "customer"
                )
            )
        )
        visits_to_merge = visit_update_result.scalar()
        
        # Update visits
        await db_session.execute(
            select(Visit).where(
                and_(
                    Visit.tenant_id == user["tenant_id"],
                    Visit.person_id == secondary_customer_id,
                    Visit.person_type == "customer"
                )
            ).update({Visit.person_id: primary_customer_id})
        )
        
        # Update customer face images
        face_update_result = await db_session.execute(
            select(func.count(CustomerFaceImage.image_id)).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == secondary_customer_id
                )
            )
        )
        face_images_to_merge = face_update_result.scalar()
        
        # Update face images
        await db_session.execute(
            select(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == secondary_customer_id
                )
            ).update({CustomerFaceImage.customer_id: primary_customer_id})
        )
        
        # Update primary customer statistics
        new_visit_count = primary_customer.visit_count + secondary_customer.visit_count
        
        # Update first_seen to earliest date
        new_first_seen = primary_customer.first_seen
        if secondary_customer.first_seen and (
            not new_first_seen or secondary_customer.first_seen < new_first_seen
        ):
            new_first_seen = secondary_customer.first_seen
        
        # Update last_seen to latest date
        new_last_seen = primary_customer.last_seen
        if secondary_customer.last_seen and (
            not new_last_seen or secondary_customer.last_seen > new_last_seen
        ):
            new_last_seen = secondary_customer.last_seen
        
        # Merge customer details (keep primary, but fill in missing info from secondary)
        updates = {
            "visit_count": new_visit_count,
            "first_seen": new_first_seen,
            "last_seen": new_last_seen
        }
        
        # Fill in missing information from secondary customer
        if not primary_customer.name and secondary_customer.name:
            updates["name"] = secondary_customer.name
        if not primary_customer.gender and secondary_customer.gender:
            updates["gender"] = secondary_customer.gender
        if not primary_customer.estimated_age_range and secondary_customer.estimated_age_range:
            updates["estimated_age_range"] = secondary_customer.estimated_age_range
        if not primary_customer.phone and secondary_customer.phone:
            updates["phone"] = secondary_customer.phone
        if not primary_customer.email and secondary_customer.email:
            updates["email"] = secondary_customer.email
        
        # Update primary customer
        await db_session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == primary_customer_id
                )
            ).update(updates)
        )
        
        # Mark secondary customer as merged (soft delete)
        await db_session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == secondary_customer_id
                )
            ).update({
                "name": f"[MERGED] {secondary_customer.name or 'Unknown'}",
                "visit_count": 0,
                "phone": None,
                "email": None
            })
        )
        
        # Note: Face embeddings in Milvus are identified by visit_id, so they don't need updating
        # The visits now point to the primary customer, so the embeddings are effectively transferred
        
        await db_session.commit()
        
        # Attempt to clean up embeddings for the secondary customer to avoid ghost matches
        try:
            await milvus_client.delete_person_embeddings(user["tenant_id"], secondary_customer_id, "customer")
            logger.info(f"Deleted embeddings for merged secondary customer {secondary_customer_id}")
        except Exception as e:
            logger.warning(f"Failed to delete embeddings for secondary customer {secondary_customer_id}: {e}")
        
        return {
            "message": "Customers merged successfully",
            "primary_customer_id": primary_customer_id,
            "secondary_customer_id": secondary_customer_id,
            "merged_visits": visits_to_merge,
            "merged_face_images": face_images_to_merge,
            "new_visit_count": new_visit_count,
            "merge_notes": merge_notes
        }
        
    except HTTPException:
        await db_session.rollback()
        raise
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error merging customers: {e}")
        raise HTTPException(status_code=500, detail="Failed to merge customers")


@router.post("/customers/reassign-visit")
async def reassign_visit(
    request: dict = Body(..., description="{ visit_id, new_customer_id, update_embeddings?: bool }"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Reassign a single visit from one customer to another and optionally adjust embeddings.

    - Updates the visit's `person_id` to `new_customer_id`.
    - Recalculates visit_count/first_seen/last_seen for affected customers.
    - If `update_embeddings` is true, inserts the visit's embedding for the new customer,
      and deletes all embeddings for the old customer if they have no remaining visits.
    """
    await db.set_tenant_context(db_session, user["tenant_id"])

    visit_id = request.get("visit_id")
    new_customer_id = request.get("new_customer_id")
    update_embeddings = bool(request.get("update_embeddings", True))

    if not visit_id or not new_customer_id:
        raise HTTPException(status_code=400, detail="visit_id and new_customer_id are required")

    from ..models.database import Visit, Customer
    from ..core.milvus_client import milvus_client
    import json

    try:
        # Load visit
        visit_result = await db_session.execute(
            select(Visit).where(
                and_(
                    Visit.tenant_id == user["tenant_id"],
                    Visit.visit_id == visit_id,
                    Visit.person_type == "customer",
                )
            )
        )
        visit = visit_result.scalar_one_or_none()
        if not visit:
            raise HTTPException(status_code=404, detail="Visit not found or not a customer visit")

        old_customer_id = int(visit.person_id)
        new_customer_id = int(new_customer_id)
        if old_customer_id == new_customer_id:
            return {"message": "No changes: visit already assigned to this customer"}

        # Ensure new customer exists
        new_cust_res = await db_session.execute(
            select(Customer).where(
                and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == new_customer_id)
            )
        )
        new_customer = new_cust_res.scalar_one_or_none()
        if not new_customer:
            raise HTTPException(status_code=404, detail="New customer not found")

        # Perform reassignment
        await db_session.execute(
            update(Visit)
            .where(and_(Visit.tenant_id == user["tenant_id"], Visit.visit_id == visit_id))
            .values(person_id=new_customer_id)
        )

        # Recompute visit counts and seen times for old and new customers
        async def _recompute_customer_stats(customer_id: int):
            stats_res = await db_session.execute(
                select(
                    func.count(Visit.visit_id),
                    func.min(Visit.first_seen),
                    func.max(Visit.last_seen),
                ).where(
                    and_(
                        Visit.tenant_id == user["tenant_id"],
                        Visit.person_type == "customer",
                        Visit.person_id == customer_id,
                    )
                )
            )
            count, first_seen, last_seen = stats_res.first() or (0, None, None)
            await db_session.execute(
                update(Customer)
                .where(and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id))
                .values(visit_count=int(count), first_seen=first_seen, last_seen=last_seen)
            )
            return int(count)

        new_count = await _recompute_customer_stats(new_customer_id)
        old_count = await _recompute_customer_stats(old_customer_id)

        # Optional embedding maintenance
        embedding_action = "skipped"
        if update_embeddings:
            try:
                # Insert embedding for new customer if present on visit
                if visit.face_embedding:
                    try:
                        emb = json.loads(visit.face_embedding)
                    except Exception:
                        emb = None
                    if isinstance(emb, list) and len(emb) == 512:
                        await milvus_client.insert_embedding(
                            tenant_id=user["tenant_id"],
                            person_id=new_customer_id,
                            person_type="customer",
                            embedding=emb,
                            created_at=int(visit.timestamp.timestamp()),
                        )
                        embedding_action = "inserted_for_new"

                # If old customer has no more visits, delete their embeddings to avoid ghost matches
                if old_count == 0:
                    await milvus_client.delete_person_embeddings(user["tenant_id"], old_customer_id, "customer")
                    embedding_action += ", deleted_old"
            except Exception as e:
                logger.warning(f"Embedding maintenance during reassignment failed: {e}")
                embedding_action = "error"

        await db_session.commit()
        return {
            "message": "Visit reassigned",
            "visit_id": visit_id,
            "old_customer_id": old_customer_id,
            "new_customer_id": new_customer_id,
            "old_customer_remaining_visits": old_count,
            "new_customer_total_visits": new_count,
            "embedding_action": embedding_action,
        }

    except HTTPException:
        await db_session.rollback()
        raise
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error reassigning visit: {e}")
        raise HTTPException(status_code=500, detail="Failed to reassign visit")


@router.post("/customers/reassign-face-image")
async def reassign_face_image(
    request: dict = Body(..., description="{ image_id, new_customer_id }"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Reassign a face image record to a different customer.

    Does not directly modify Milvus since gallery images are not used for embedding insertions.
    """
    await db.set_tenant_context(db_session, user["tenant_id"])

    image_id = request.get("image_id")
    new_customer_id = request.get("new_customer_id")
    if not image_id or not new_customer_id:
        raise HTTPException(status_code=400, detail="image_id and new_customer_id are required")

    from ..models.database import CustomerFaceImage, Customer

    try:
        # Ensure image exists
        img_res = await db_session.execute(
            select(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.image_id == int(image_id),
                )
            )
        )
        face_image = img_res.scalar_one_or_none()
        if not face_image:
            raise HTTPException(status_code=404, detail="Face image not found")

        # Ensure new customer exists
        cust_res = await db_session.execute(
            select(Customer).where(
                and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == int(new_customer_id))
            )
        )
        if not cust_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="New customer not found")

        if face_image.customer_id == int(new_customer_id):
            return {"message": "No changes: image already assigned to this customer"}

        # Reassign
        await db_session.execute(
            update(CustomerFaceImage)
            .where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.image_id == int(image_id),
                )
            )
            .values(customer_id=int(new_customer_id))
        )

        await db_session.commit()
        return {
            "message": "Face image reassigned",
            "image_id": int(image_id),
            "new_customer_id": int(new_customer_id),
        }

    except HTTPException:
        await db_session.rollback()
        raise
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error reassigning face image: {e}")
        raise HTTPException(status_code=500, detail="Failed to reassign face image")
