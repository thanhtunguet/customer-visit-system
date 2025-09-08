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
        select(Customer)
        .where(
            and_(
                Customer.tenant_id == user["tenant_id"],
                Customer.customer_id == customer_id
            )
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer@router.post("/customers/reassign-visit")

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
