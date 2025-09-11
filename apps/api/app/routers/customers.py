import logging
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import db, get_db_session
from ..core.milvus_client import milvus_client
from ..core.security import get_current_user
from ..models.database import Customer
from ..schemas import CustomerCreate, CustomerResponse
from ..services.event_broadcaster import tenant_event_broadcaster

router = APIRouter(prefix="/v1", tags=["Customer Management"])
logger = logging.getLogger(__name__)


@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
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
            from sqlalchemy import desc, func

            from ..models.database import CustomerFaceImage

            face_result = await db_session.execute(
                select(CustomerFaceImage.image_path)
                .where(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer.customer_id,
                )
                .order_by(
                    desc(
                        CustomerFaceImage.confidence_score
                        + func.coalesce(CustomerFaceImage.quality_score, 0.5)
                    )
                )
                .limit(1)
            )

            face_image = face_result.scalar_one_or_none()
            if face_image:
                # Generate MinIO presigned URL for the avatar
                import asyncio

                from ..core.minio_client import minio_client

                try:
                    from datetime import timedelta

                    avatar_url = await asyncio.get_event_loop().run_in_executor(
                        None,
                        minio_client.get_presigned_url,
                        "faces-derived",  # Use derived bucket for processed face images
                        face_image,
                        timedelta(hours=1),  # 1 hour expiry
                    )
                except Exception as url_error:
                    logger.warning(
                        f"Could not generate avatar URL for customer {customer.customer_id}: {url_error}"
                    )
                    avatar_url = None  # Continue without avatar

        except Exception as e:
            logger.warning(
                f"Could not fetch avatar for customer {customer.customer_id}: {e}"
            )
            avatar_url = None  # Continue without avatar

        try:
            # Create customer response with proper null handling
            customer_response = CustomerResponse(
                customer_id=customer.customer_id,
                tenant_id=customer.tenant_id,
                name=customer.name,
                gender=customer.gender,
                estimated_age_range=customer.estimated_age_range,
                phone=customer.phone,
                email=customer.email,
                first_seen=customer.first_seen or datetime.utcnow(),  # Fallback if null
                last_seen=customer.last_seen,
                visit_count=customer.visit_count or 0,  # Fallback if null
                avatar_url=avatar_url,
            )
            customer_responses.append(customer_response)
        except Exception as customer_error:
            logger.error(
                f"Failed to create response for customer {customer.customer_id}: {customer_error}"
            )
            logger.error(
                f"Customer data: first_seen={customer.first_seen}, last_seen={customer.last_seen}, visit_count={customer.visit_count}"
            )
            # Skip this customer to prevent entire API from failing
            continue

    return customer_responses


@router.post("/customers", response_model=CustomerResponse)
async def create_customer(
    customer: CustomerCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])

    new_customer = Customer(
        tenant_id=user["tenant_id"],
        name=customer.name,
        gender=customer.gender,
        estimated_age_range=customer.estimated_age_range,
        phone=customer.phone,
        email=customer.email,
    )
    db_session.add(new_customer)
    await db_session.commit()
    await db_session.refresh(new_customer)
    return new_customer


@router.get("/customers/{customer_id:int}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    result = await db_session.execute(
        select(Customer).where(
            and_(
                Customer.tenant_id == user["tenant_id"],
                Customer.customer_id == customer_id,
            )
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("/customers/merge")
async def merge_customers(
    request: dict,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Trigger a background merge of two customers; returns immediately.

    Request: { primary_customer_id: int, secondary_customer_id: int, notes?: str }

    Behavior:
    - Reassign all references (visits, face images) from secondary to primary
    - Deduplicate face images on primary by image_hash keeping best quality
    - Delete the secondary customer record
    - Recompute primary stats from visits
    - Rebuild Milvus embeddings for the primary from gallery and visits (best-effort)
    - Idempotent if secondary is already missing
    """
    await db.set_tenant_context(db_session, user["tenant_id"])

    try:
        primary_customer_id = int(request.get("primary_customer_id"))
        secondary_customer_id = int(request.get("secondary_customer_id"))
        merge_notes = request.get("notes", "")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request payload")

    if primary_customer_id == secondary_customer_id:
        return {"message": "No-op: same customer", "status": "accepted"}

    # Validate existence quickly (lightweight checks)
    res = await db_session.execute(
        select(Customer.customer_id).where(
            and_(
                Customer.tenant_id == user["tenant_id"],
                Customer.customer_id.in_([primary_customer_id, secondary_customer_id]),
            )
        )
    )
    found = [row[0] for row in res.fetchall()]
    if primary_customer_id not in found:
        raise HTTPException(status_code=404, detail="Primary customer not found")
    if secondary_customer_id not in found:
        # Already merged previously
        return {"message": "Already merged", "status": "accepted"}

    # Fire-and-forget background task using a fresh DB session
    operation_id = f"merge_{uuid.uuid4().hex[:12]}"
    tenant_id = user["tenant_id"]

    async def _bg_merge():
        from ..core.database import db as _db
        from ..models.database import Customer, CustomerFaceImage, Visit

        async with _db.get_session() as session:
            try:
                await _db.set_tenant_context(session, tenant_id)
                # Broadcast start
                await tenant_event_broadcaster.broadcast(
                    tenant_id,
                    {
                        "type": "customer_merge_started",
                        "operation_id": operation_id,
                        "primary_customer_id": primary_customer_id,
                        "secondary_customer_id": secondary_customer_id,
                        "notes": merge_notes,
                    },
                )

                # Reassign visits
                await session.execute(
                    update(Visit)
                    .where(
                        and_(
                            Visit.tenant_id == tenant_id,
                            Visit.person_type == "customer",
                            Visit.person_id == secondary_customer_id,
                        )
                    )
                    .values(person_id=primary_customer_id)
                )

                # Reassign face images
                await session.execute(
                    update(CustomerFaceImage)
                    .where(
                        and_(
                            CustomerFaceImage.tenant_id == tenant_id,
                            CustomerFaceImage.customer_id == secondary_customer_id,
                        )
                    )
                    .values(customer_id=primary_customer_id)
                )

                # Dedup gallery by image_hash
                images_res = await session.execute(
                    select(CustomerFaceImage).where(
                        and_(
                            CustomerFaceImage.tenant_id == tenant_id,
                            CustomerFaceImage.customer_id == primary_customer_id,
                            CustomerFaceImage.image_hash.is_not(None),
                        )
                    )
                )
                imgs = images_res.scalars().all()
                by_hash = {}
                to_delete = []

                def score(img):
                    return float(
                        (img.confidence_score or 0.0) + (img.quality_score or 0.5)
                    )

                for im in imgs:
                    if not im.image_hash:
                        continue
                    ex = by_hash.get(im.image_hash)
                    if not ex:
                        by_hash[im.image_hash] = im
                    else:
                        keep, drop = (im, ex) if score(im) >= score(ex) else (ex, im)
                        by_hash[im.image_hash] = keep
                        to_delete.append(int(drop.image_id))
                if to_delete:
                    await session.execute(
                        delete(CustomerFaceImage).where(
                            and_(
                                CustomerFaceImage.tenant_id == tenant_id,
                                CustomerFaceImage.customer_id == primary_customer_id,
                                CustomerFaceImage.image_id.in_(to_delete),
                            )
                        )
                    )

                # Recompute stats and copy missing attributes
                stats_res = await session.execute(
                    select(
                        func.count(Visit.visit_id),
                        func.min(Visit.first_seen),
                        func.max(Visit.last_seen),
                    ).where(
                        and_(
                            Visit.tenant_id == tenant_id,
                            Visit.person_type == "customer",
                            Visit.person_id == primary_customer_id,
                        )
                    )
                )
                count, first_seen, last_seen = stats_res.first() or (0, None, None)

                # Load secondary for attribute copying, then delete it
                custs = await session.execute(
                    select(Customer).where(
                        and_(
                            Customer.tenant_id == tenant_id,
                            Customer.customer_id.in_(
                                [primary_customer_id, secondary_customer_id]
                            ),
                        )
                    )
                )
                m = {c.customer_id: c for c in custs.scalars().all()}
                prim = m.get(primary_customer_id)
                sec = m.get(secondary_customer_id)

                updates = {
                    "visit_count": int(count or 0),
                    "first_seen": first_seen or (prim.first_seen if prim else None),
                    "last_seen": last_seen or (prim.last_seen if prim else None),
                }
                if prim and sec:
                    if not prim.name and sec.name:
                        updates["name"] = sec.name
                    if not prim.gender and sec.gender:
                        updates["gender"] = sec.gender
                    if not prim.estimated_age_range and sec.estimated_age_range:
                        updates["estimated_age_range"] = sec.estimated_age_range
                    if not prim.phone and sec.phone:
                        updates["phone"] = sec.phone
                    if not prim.email and sec.email:
                        updates["email"] = sec.email

                await session.execute(
                    update(Customer)
                    .where(
                        and_(
                            Customer.tenant_id == tenant_id,
                            Customer.customer_id == primary_customer_id,
                        )
                    )
                    .values(**updates)
                )

                await session.execute(
                    delete(Customer).where(
                        and_(
                            Customer.tenant_id == tenant_id,
                            Customer.customer_id == secondary_customer_id,
                        )
                    )
                )

                await session.commit()

                # Embeddings maintenance (best-effort)
                try:
                    try:
                        await milvus_client.delete_person_embeddings(
                            tenant_id, secondary_customer_id, "customer"
                        )
                    except Exception as e:
                        logger.info("Secondary embedding cleanup skipped/failed: %s", e)

                    # Aggregate vectors for primary (same as earlier version)
                    import hashlib
                    import json

                    aggregated = []
                    inserted_keys = set()
                    from datetime import datetime

                    gres = await session.execute(
                        select(
                            CustomerFaceImage.embedding,
                            CustomerFaceImage.created_at,
                            CustomerFaceImage.image_hash,
                        ).where(
                            and_(
                                CustomerFaceImage.tenant_id == tenant_id,
                                CustomerFaceImage.customer_id == primary_customer_id,
                                CustomerFaceImage.embedding.is_not(None),
                            )
                        )
                    )
                    for emb, created_at, ih in gres.all():
                        if not emb or not isinstance(emb, list) or len(emb) != 512:
                            continue
                        key = (
                            f"img:{ih}"
                            if ih
                            else f"vec:{hashlib.sha256(str(emb).encode()).hexdigest()}"
                        )
                        if key in inserted_keys:
                            continue
                        inserted_keys.add(key)
                        ts = int((created_at or datetime.utcnow()).timestamp())
                        aggregated.append((emb, ts))

                    vres = await session.execute(
                        select(Visit.face_embedding, Visit.timestamp).where(
                            and_(
                                Visit.tenant_id == tenant_id,
                                Visit.person_type == "customer",
                                Visit.person_id == primary_customer_id,
                                Visit.face_embedding.is_not(None),
                            )
                        )
                    )
                    for emb_text, ts_dt in vres.all():
                        if not emb_text:
                            continue
                        try:
                            emb = json.loads(emb_text)
                        except Exception:
                            emb = None
                        if not isinstance(emb, list) or len(emb) != 512:
                            continue
                        key = f"vis:{hashlib.sha256(str(emb).encode()).hexdigest()}"
                        if key in inserted_keys:
                            continue
                        inserted_keys.add(key)
                        ts = int((ts_dt or datetime.utcnow()).timestamp())
                        aggregated.append((emb, ts))

                    if aggregated:
                        await milvus_client.delete_person_embeddings(
                            tenant_id, primary_customer_id, "customer"
                        )
                        for emb, ts in aggregated:
                            await milvus_client.insert_embedding(
                                tenant_id, primary_customer_id, "customer", emb, ts
                            )

                except Exception as e:
                    logger.warning("Embedding maintenance failed in background: %s", e)

                await tenant_event_broadcaster.broadcast(
                    tenant_id,
                    {
                        "type": "customer_merge_completed",
                        "operation_id": operation_id,
                        "primary_customer_id": primary_customer_id,
                        "secondary_customer_id": secondary_customer_id,
                        "status": "success",
                    },
                )
            except Exception as e:
                await tenant_event_broadcaster.broadcast(
                    tenant_id,
                    {
                        "type": "customer_merge_completed",
                        "operation_id": operation_id,
                        "primary_customer_id": primary_customer_id,
                        "secondary_customer_id": secondary_customer_id,
                        "status": "error",
                        "error": str(e),
                    },
                )

    import asyncio as _asyncio

    _asyncio.create_task(_bg_merge())

    return {"status": "accepted", "operation_id": operation_id}


@router.get("/customers/{customer_id:int}/similar")
async def find_similar_customers(
    customer_id: int,
    threshold: float = Query(None, ge=0.0, le=1.0),
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Return similar customers based on face embeddings using Milvus."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    try:
        # Verify customer exists
        result = await db_session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == customer_id,
                )
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        # Load this customer's embeddings from gallery
        from ..models.database import CustomerFaceImage

        images_res = await db_session.execute(
            select(CustomerFaceImage.embedding, CustomerFaceImage.image_id).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id,
                )
            )
        )
        images = images_res.all()
        if not images:
            return {
                "customer_id": customer_id,
                "customer_name": customer.name,
                "similar_customers": [],
                "threshold_used": float(
                    threshold
                    if threshold is not None
                    else settings.face_similarity_threshold
                ),
                "total_found": 0,
            }

        used_threshold = float(
            threshold if threshold is not None else settings.face_similarity_threshold
        )
        similar_map: dict[int, float] = {}

        # Query Milvus for each embedding and aggregate by max similarity per customer
        for emb, _img_id in images:
            if not emb or not isinstance(emb, list) or len(emb) != 512:
                continue
            try:
                matches = await milvus_client.search_similar_faces(
                    tenant_id=user["tenant_id"],
                    embedding=emb,
                    limit=limit,
                    threshold=used_threshold,
                )
                for m in matches:
                    if m.get("person_type") != "customer":
                        continue
                    other_id = int(m.get("person_id"))
                    if other_id == customer_id:
                        continue
                    sim = float(m.get("similarity", 0.0))
                    if other_id not in similar_map or sim > similar_map[other_id]:
                        similar_map[other_id] = sim
            except Exception as e:
                logger.warning(f"Milvus search failed for customer {customer_id}: {e}")
                continue

        if not similar_map:
            return {
                "customer_id": customer_id,
                "customer_name": customer.name,
                "similar_customers": [],
                "threshold_used": used_threshold,
                "total_found": 0,
            }

        # Fetch details for found customers
        other_ids = list(similar_map.keys())
        details_res = await db_session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id.in_(other_ids),
                )
            )
        )
        others = {c.customer_id: c for c in details_res.scalars().all()}

        similar_customers = []
        for cid, score in similar_map.items():
            c = others.get(cid)
            if not c:
                continue
            similar_customers.append(
                {
                    "customer_id": c.customer_id,
                    "name": c.name,
                    "visit_count": c.visit_count,
                    "first_seen": c.first_seen.isoformat() if c.first_seen else None,
                    "last_seen": c.last_seen.isoformat() if c.last_seen else None,
                    "max_similarity": float(score),
                    "gender": c.gender,
                    "estimated_age_range": c.estimated_age_range,
                }
            )

        # Sort and limit
        similar_customers.sort(key=lambda x: x["max_similarity"], reverse=True)
        similar_customers = similar_customers[:limit]

        return {
            "customer_id": customer_id,
            "customer_name": customer.name,
            "similar_customers": similar_customers,
            "threshold_used": used_threshold,
            "total_found": len(similar_customers),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar customers: {e}")
        raise HTTPException(status_code=500, detail="Failed to find similar customers")


@router.post("/customers/reconcile")
async def reconcile_customers(
    request: dict = Body({}, description="{ limit?: int }"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Re-cluster and reconcile duplicate customers created by over-segmentation.

    Strategy:
    - For each customer, query Milvus for similar customers using MERGE_DISTANCE_THR
    - Merge pairs where similarity >= MERGE_DISTANCE_THR (idempotent via merge endpoint)
    - Stop at configured limit per run
    """
    await db.set_tenant_context(db_session, user["tenant_id"])
    from ..core.config import settings

    tenant_id = user["tenant_id"]
    try:
        # Fetch recent customers ordered by last_seen desc
        limit = int(request.get("limit", 100))
        res = await db_session.execute(
            select(Customer)
            .where(Customer.tenant_id == tenant_id)
            .order_by(Customer.last_seen.desc())
            .limit(limit)
        )
        customers = res.scalars().all()
        merges = []
        examined = 0

        for c in customers:
            examined += 1
            # Use best embeddings from gallery; fallback to visits
            from ..models.database import CustomerFaceImage, Visit

            img_res = await db_session.execute(
                select(CustomerFaceImage.embedding)
                .where(
                    and_(
                        CustomerFaceImage.tenant_id == tenant_id,
                        CustomerFaceImage.customer_id == c.customer_id,
                    )
                )
                .limit(3)
            )
            embs = [row[0] for row in img_res if row[0]]
            if not embs:
                vres = await db_session.execute(
                    select(Visit.face_embedding)
                    .where(
                        and_(
                            Visit.tenant_id == tenant_id,
                            Visit.person_type == "customer",
                            Visit.person_id == c.customer_id,
                            Visit.face_embedding.is_not(None),
                        )
                    )
                    .limit(3)
                )
                import json as _json

                embs = []
                for (etxt,) in vres.all():
                    try:
                        vec = _json.loads(etxt) if etxt else None
                        if isinstance(vec, list) and len(vec) == 512:
                            embs.append(vec)
                    except Exception:
                        pass
            if not embs:
                continue

            # Search for similar customers
            best_pair = None
            best_sim = 0.0
            for emb in embs:
                try:
                    matches = await milvus_client.search_similar_faces(
                        tenant_id=tenant_id,
                        embedding=emb,
                        limit=5,
                        threshold=settings.embedding_distance_thr,
                    )
                    for m in matches:
                        if m.get("person_type") != "customer":
                            continue
                        other_id = int(m.get("person_id"))
                        if other_id == c.customer_id:
                            continue
                        sim = float(m.get("similarity", 0.0))
                        if sim > best_sim:
                            best_sim = sim
                            best_pair = other_id
                except Exception as se:
                    logger.warning(
                        f"Milvus search failed during reconcile for {c.customer_id}: {se}"
                    )
                    continue

            if best_pair and best_sim >= settings.merge_distance_thr:
                primary_id = min(int(c.customer_id), int(best_pair))
                secondary_id = max(int(c.customer_id), int(best_pair))
                # Call the existing merge endpoint logic (idempotent)
                try:
                    merge_req = {
                        "primary_customer_id": primary_id,
                        "secondary_customer_id": secondary_id,
                        "notes": "reconcile",
                    }
                    result = await merge_customers(merge_req, user, db_session)
                    merges.append(
                        {
                            "primary": primary_id,
                            "secondary": secondary_id,
                            "similarity": best_sim,
                            "result": (
                                result.get("message")
                                if isinstance(result, dict)
                                else "ok"
                            ),
                        }
                    )
                except Exception as me:
                    logger.warning(
                        f"Merge failed for {primary_id}<-{secondary_id}: {me}"
                    )
                    continue

        return {"examined": examined, "merges": merges, "merge_count": len(merges)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during reconciliation: {e}")
        raise HTTPException(status_code=500, detail="Failed to reconcile customers")


@router.get("/customers/{customer_id:int}/face-images")
async def get_customer_face_images(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    try:
        # Verify customer exists
        res = await db_session.execute(
            select(Customer.customer_id).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == customer_id,
                )
            )
        )
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Customer not found")

        from ..services.customer_face_service import customer_face_service

        images = await customer_face_service.get_customer_face_images(
            db_session, user["tenant_id"], customer_id
        )
        return {
            "customer_id": customer_id,
            "total_images": len(images),
            "images": [
                {
                    "image_id": int(img.image_id),
                    "image_path": img.image_path,
                    "confidence_score": float(img.confidence_score or 0.0),
                    "quality_score": float(img.quality_score or 0.0),
                    "created_at": (
                        img.created_at.isoformat() if img.created_at else None
                    ),
                    "visit_id": img.visit_id,
                    "face_bbox": img.face_bbox,
                    "detection_metadata": img.detection_metadata,
                }
                for img in images
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching customer face images: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch face images")


@router.get("/customers/{customer_id:int}/face-gallery-stats")
async def get_customer_face_gallery_stats(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    try:
        from ..models.database import CustomerFaceImage

        # Verify customer
        res = await db_session.execute(
            select(Customer.customer_id).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == customer_id,
                )
            )
        )
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Customer not found")

        # Aggregates
        agg_res = await db_session.execute(
            select(
                func.count(CustomerFaceImage.image_id),
                func.avg(CustomerFaceImage.confidence_score),
                func.max(CustomerFaceImage.confidence_score),
                func.min(CustomerFaceImage.confidence_score),
                func.avg(func.coalesce(CustomerFaceImage.quality_score, 0.0)),
                func.min(CustomerFaceImage.created_at),
                func.max(CustomerFaceImage.created_at),
            ).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id,
                )
            )
        )
        (
            total_images,
            avg_conf,
            max_conf,
            min_conf,
            avg_quality,
            first_date,
            latest_date,
        ) = agg_res.first() or (0, None, None, None, None, None, None)

        from ..core.config import settings as app_settings

        return {
            "customer_id": customer_id,
            "total_images": int(total_images or 0),
            "avg_confidence": float(avg_conf or 0.0),
            "max_confidence": float(max_conf or 0.0),
            "min_confidence": float(min_conf or 0.0),
            "avg_quality": float(avg_quality or 0.0),
            "first_image_date": first_date.isoformat() if first_date else None,
            "latest_image_date": latest_date.isoformat() if latest_date else None,
            "gallery_limit": int(app_settings.max_face_images),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching face gallery stats: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch face gallery stats"
        )


@router.post("/customers/{customer_id:int}/face-images/batch-delete")
async def delete_customer_face_images_batch(
    customer_id: int,
    request: dict,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    image_ids = request.get("image_ids") or []
    if not isinstance(image_ids, list) or not all(
        isinstance(x, int) for x in image_ids
    ):
        raise HTTPException(
            status_code=400, detail="image_ids must be a list of integers"
        )
    try:
        from ..models.database import CustomerFaceImage
        from ..services.customer_face_service import customer_face_service

        # Load images for this customer and tenant only
        res = await db_session.execute(
            select(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id,
                    CustomerFaceImage.image_id.in_(image_ids),
                )
            )
        )
        images = res.scalars().all()
        for img in images:
            await customer_face_service._delete_face_image(db_session, img)
        deleted_count = len(images)
        await db_session.commit()
        return {
            "message": "Deleted customer face images",
            "deleted_count": deleted_count,
            "requested_count": len(image_ids),
        }
    except HTTPException:
        await db_session.rollback()
        raise
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error deleting customer face images: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete face images")


@router.post("/customers/{customer_id:int}/face-images/backfill")
async def backfill_customer_face_images(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Placeholder backfill: returns counts without changes to keep UI functional."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    try:
        # Count visits for this customer; do not modify data in this placeholder
        from ..models.database import Visit

        visits_res = await db_session.execute(
            select(func.count(Visit.visit_id)).where(
                and_(
                    Visit.tenant_id == user["tenant_id"],
                    Visit.person_type == "customer",
                    Visit.person_id == customer_id,
                )
            )
        )
        total_visits = int(visits_res.scalar() or 0)
        return {
            "message": "Backfill completed (no-op placeholder)",
            "customer_id": customer_id,
            "visits_processed": 0,
            "total_visits_found": total_visits,
        }
    except Exception as e:
        logger.error(f"Error during backfill placeholder: {e}")
        raise HTTPException(status_code=500, detail="Failed to backfill face images")


@router.post("/customers/reassign-visit")
async def reassign_visit(
    request: dict = Body(
        ..., description="{ visit_id, new_customer_id, update_embeddings?: bool }"
    ),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
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
        raise HTTPException(
            status_code=400, detail="visit_id and new_customer_id are required"
        )

    import json

    from ..core.milvus_client import milvus_client
    from ..models.database import Customer, Visit

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
            raise HTTPException(
                status_code=404, detail="Visit not found or not a customer visit"
            )

        old_customer_id = int(visit.person_id)
        new_customer_id = int(new_customer_id)
        if old_customer_id == new_customer_id:
            return {"message": "No changes: visit already assigned to this customer"}

        # Ensure new customer exists
        new_cust_res = await db_session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == new_customer_id,
                )
            )
        )
        new_customer = new_cust_res.scalar_one_or_none()
        if not new_customer:
            raise HTTPException(status_code=404, detail="New customer not found")

        # Perform reassignment
        await db_session.execute(
            update(Visit)
            .where(
                and_(Visit.tenant_id == user["tenant_id"], Visit.visit_id == visit_id)
            )
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
                .where(
                    and_(
                        Customer.tenant_id == user["tenant_id"],
                        Customer.customer_id == customer_id,
                    )
                )
                .values(
                    visit_count=int(count), first_seen=first_seen, last_seen=last_seen
                )
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
                    await milvus_client.delete_person_embeddings(
                        user["tenant_id"], old_customer_id, "customer"
                    )
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
    db_session: AsyncSession = Depends(get_db_session),
):
    """Reassign a face image record to a different customer.

    Does not directly modify Milvus since gallery images are not used for embedding insertions.
    """
    await db.set_tenant_context(db_session, user["tenant_id"])

    image_id = request.get("image_id")
    new_customer_id = request.get("new_customer_id")
    if not image_id or not new_customer_id:
        raise HTTPException(
            status_code=400, detail="image_id and new_customer_id are required"
        )

    from ..models.database import Customer, CustomerFaceImage

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
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == int(new_customer_id),
                )
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


@router.delete("/customers/{customer_id:int}")
async def delete_customer(
    customer_id: int,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Delete a customer and clean up associated data."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    try:
        # Check if customer exists
        result = await db_session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == customer_id,
                )
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        # Delete associated data first
        from ..models.database import CustomerFaceImage, Visit

        # Delete visits
        visits_result = await db_session.execute(
            select(func.count(Visit.visit_id)).where(
                and_(
                    Visit.tenant_id == user["tenant_id"],
                    Visit.person_type == "customer",
                    Visit.person_id == customer_id,
                )
            )
        )
        visit_count = visits_result.scalar() or 0

        await db_session.execute(
            delete(Visit).where(
                and_(
                    Visit.tenant_id == user["tenant_id"],
                    Visit.person_type == "customer",
                    Visit.person_id == customer_id,
                )
            )
        )

        # Delete face images
        face_images_result = await db_session.execute(
            select(func.count(CustomerFaceImage.image_id)).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id,
                )
            )
        )
        face_image_count = face_images_result.scalar() or 0

        await db_session.execute(
            delete(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id == customer_id,
                )
            )
        )

        # Delete the customer
        await db_session.execute(
            delete(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id == customer_id,
                )
            )
        )

        await db_session.commit()

        # Clean up embeddings from Milvus (best effort)
        try:
            await milvus_client.delete_person_embeddings(
                user["tenant_id"], customer_id, "customer"
            )
            logger.info(f"Deleted embeddings for customer {customer_id}")
        except Exception as e:
            logger.warning(
                f"Failed to delete embeddings for customer {customer_id}: {e}"
            )

        return {
            "message": "Customer deleted successfully",
            "customer_id": customer_id,
            "deleted_visits": visit_count,
            "deleted_face_images": face_image_count,
        }

    except HTTPException:
        await db_session.rollback()
        raise
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error deleting customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete customer")


@router.post("/customers/bulk-merge")
async def bulk_merge_customers(
    request: dict = Body(
        ...,
        description="{ merges: [{ primary_customer_id: int, secondary_customer_ids: List[int] }] }",
    ),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Start asynchronous bulk customer merge operation.

    This endpoint accepts multiple merge operations and processes them in background.
    Each merge operation specifies one primary customer and multiple secondary customers to merge into it.

    Returns job ID immediately for tracking progress.
    Use GET /jobs/{job_id} to check status and results.
    """
    from ..core.database import db
    from ..services.background_jobs import background_job_service

    await db.set_tenant_context(db_session, user["tenant_id"])

    merges = request.get("merges", [])
    if not isinstance(merges, list) or len(merges) == 0:
        raise HTTPException(status_code=400, detail="merges must be a non-empty list")

    # Validate merge structure
    all_customer_ids = set()
    validated_merges = []

    for i, merge_op in enumerate(merges):
        if not isinstance(merge_op, dict):
            raise HTTPException(
                status_code=400, detail=f"Merge operation {i} must be an object"
            )

        primary_id = merge_op.get("primary_customer_id")
        secondary_ids = merge_op.get("secondary_customer_ids", [])

        if not isinstance(primary_id, int):
            raise HTTPException(
                status_code=400,
                detail=f"Merge operation {i}: primary_customer_id must be an integer",
            )

        if not isinstance(secondary_ids, list) or not all(
            isinstance(x, int) for x in secondary_ids
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Merge operation {i}: secondary_customer_ids must be a list of integers",
            )

        if len(secondary_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Merge operation {i}: secondary_customer_ids cannot be empty",
            )

        # Check for conflicts (customer can't be in multiple operations)
        operation_customers = {primary_id} | set(secondary_ids)
        conflicts = operation_customers & all_customer_ids
        if conflicts:
            raise HTTPException(
                status_code=400,
                detail=f"Merge operation {i}: Customer(s) {list(conflicts)} are already included in other merge operations",
            )

        all_customer_ids.update(operation_customers)

        # Check for self-merge
        if primary_id in secondary_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Merge operation {i}: Customer cannot merge with itself",
            )

        validated_merges.append(
            {"primary_customer_id": primary_id, "secondary_customer_ids": secondary_ids}
        )

    # Quick validation that all customers exist
    result = await db_session.execute(
        select(Customer.customer_id).where(
            and_(
                Customer.tenant_id == user["tenant_id"],
                Customer.customer_id.in_(list(all_customer_ids)),
            )
        )
    )
    found_ids = set(row[0] for row in result.fetchall())
    missing_ids = all_customer_ids - found_ids

    if missing_ids:
        raise HTTPException(
            status_code=404, detail=f"Customers not found: {list(missing_ids)}"
        )

    # Create background job
    job_id = await background_job_service.create_job(
        job_type="bulk_merge_customers",
        tenant_id=user["tenant_id"],
        metadata={
            "merges": validated_merges,
            "user_id": user.get("user_id"),
            "total_operations": len(validated_merges),
            "total_customers": len(all_customer_ids),
        },
    )

    # Start the job
    from ..core.database import get_db_session

    await background_job_service.start_job(job_id, get_db_session)

    return {
        "message": f"Bulk customer merge job started for {len(validated_merges)} operations involving {len(all_customer_ids)} customers",
        "job_id": job_id,
        "status": "started",
        "total_operations": len(validated_merges),
        "total_customers": len(all_customer_ids),
        "check_status_url": f"/v1/jobs/{job_id}",
    }


@router.post("/customers/bulk-delete")
async def bulk_delete_customers(
    request: dict = Body(..., description="{ customer_ids: List[int] }"),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Delete multiple customers in a single transaction."""
    await db.set_tenant_context(db_session, user["tenant_id"])

    customer_ids = request.get("customer_ids", [])
    if not isinstance(customer_ids, list) or not all(
        isinstance(x, int) for x in customer_ids
    ):
        raise HTTPException(
            status_code=400, detail="customer_ids must be a list of integers"
        )

    if len(customer_ids) == 0:
        raise HTTPException(status_code=400, detail="customer_ids cannot be empty")

    try:
        # Verify all customers exist and belong to tenant
        result = await db_session.execute(
            select(Customer.customer_id).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id.in_(customer_ids),
                )
            )
        )
        found_ids = [row[0] for row in result.fetchall()]

        if len(found_ids) != len(customer_ids):
            missing_ids = set(customer_ids) - set(found_ids)
            raise HTTPException(
                status_code=404, detail=f"Customers not found: {list(missing_ids)}"
            )

        # Count associated data before deletion
        from ..models.database import CustomerFaceImage, Visit

        visits_result = await db_session.execute(
            select(func.count(Visit.visit_id)).where(
                and_(
                    Visit.tenant_id == user["tenant_id"],
                    Visit.person_type == "customer",
                    Visit.person_id.in_(customer_ids),
                )
            )
        )
        total_visits = visits_result.scalar() or 0

        face_images_result = await db_session.execute(
            select(func.count(CustomerFaceImage.image_id)).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id.in_(customer_ids),
                )
            )
        )
        total_face_images = face_images_result.scalar() or 0

        # Delete associated data
        await db_session.execute(
            delete(Visit).where(
                and_(
                    Visit.tenant_id == user["tenant_id"],
                    Visit.person_type == "customer",
                    Visit.person_id.in_(customer_ids),
                )
            )
        )

        await db_session.execute(
            delete(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == user["tenant_id"],
                    CustomerFaceImage.customer_id.in_(customer_ids),
                )
            )
        )

        # Delete customers
        await db_session.execute(
            delete(Customer).where(
                and_(
                    Customer.tenant_id == user["tenant_id"],
                    Customer.customer_id.in_(customer_ids),
                )
            )
        )

        await db_session.commit()

        # Clean up embeddings from Milvus (best effort)
        failed_embedding_cleanups = []
        for customer_id in customer_ids:
            try:
                await milvus_client.delete_person_embeddings(
                    user["tenant_id"], customer_id, "customer"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to delete embeddings for customer {customer_id}: {e}"
                )
                failed_embedding_cleanups.append(customer_id)

        return {
            "message": "Customers deleted successfully",
            "deleted_customers": len(customer_ids),
            "customer_ids": customer_ids,
            "deleted_visits": total_visits,
            "deleted_face_images": total_face_images,
            "failed_embedding_cleanups": failed_embedding_cleanups,
        }

    except HTTPException:
        await db_session.rollback()
        raise
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error bulk deleting customers {customer_ids}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete customers")


@router.get("/customers/events/stream")
async def stream_customer_events(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """SSE stream for customer-related async events (merge results, etc.)"""
    return await tenant_event_broadcaster.stream(user["tenant_id"], request)
