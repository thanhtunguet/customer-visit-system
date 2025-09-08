"""
Service for handling visit merge operations asynchronously.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import Visit, Customer, CustomerFaceImage
from .background_jobs import BackgroundJob

logger = logging.getLogger(__name__)


class MergeService:
    """Service for handling visit merge operations"""
    
    def _update_job_progress(self, job_id: str, progress: int, message: str = ""):
        """Update job progress - imports here to avoid circular import"""
        from .background_jobs import background_job_service
        background_job_service.update_job_progress(job_id, progress, message)
    
    async def execute_merge_visits_job(
        self, 
        job: BackgroundJob, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Execute visit merge operation in background"""
        try:
            metadata = job.metadata or {}
            visit_ids = metadata.get("visit_ids", [])
            primary_visit_id = metadata.get("primary_visit_id")
            user_id = metadata.get("user_id")
            
            if not visit_ids or len(visit_ids) < 2:
                raise ValueError("At least two visit IDs required for merge")
            
            self._update_job_progress(job.job_id, 10, "Loading visits to merge")
            
            # Load visits
            result = await db_session.execute(
                select(Visit).where(
                    and_(Visit.tenant_id == job.tenant_id, Visit.visit_id.in_(visit_ids))
                )
            )
            visits = result.scalars().all()
            
            if len(visits) != len(set(visit_ids)):
                found_ids = {v.visit_id for v in visits}
                missing = [vid for vid in visit_ids if vid not in found_ids]
                raise ValueError(f"Visit(s) not found: {missing}")
            
            self._update_job_progress(job.job_id, 20, "Validating visit data")
            
            # Validate same person and type
            person_ids = {int(v.person_id) for v in visits}
            person_types = {v.person_type for v in visits}
            site_ids = {int(v.site_id) for v in visits}
            
            if len(person_ids) != 1 or len(person_types) != 1:
                raise ValueError("All visits must reference the same person and type")
            if len(site_ids) != 1:
                raise ValueError("All visits must belong to the same site")
            
            person_id = person_ids.pop()
            person_type = person_types.pop()
            site_id = site_ids.pop()
            camera_ids = sorted({int(v.camera_id) for v in visits})
            
            self._update_job_progress(job.job_id, 30, "Selecting primary visit")
            
            # Determine primary visit
            primary = None
            if primary_visit_id:
                primary = next((v for v in visits if v.visit_id == primary_visit_id), None)
                if not primary:
                    raise ValueError("primary_visit_id must be in visit_ids")
            else:
                # Choose by highest confidence, then earliest first_seen
                def _score(v: Visit):
                    return (float(v.highest_confidence or v.confidence_score or 0.0), -v.first_seen.timestamp())
                primary = sorted(visits, key=_score, reverse=True)[0]
            
            self._update_job_progress(job.job_id, 40, "Calculating aggregated data")
            
            # Aggregations
            first_seen = min(v.first_seen for v in visits)
            last_seen = max(v.last_seen for v in visits)
            visit_duration_seconds = int((last_seen - first_seen).total_seconds()) if last_seen and first_seen else 0
            detection_count = sum(int(v.detection_count or 0) for v in visits)
            highest_confidence = max(float(v.highest_confidence or v.confidence_score or 0.0) for v in visits)
            
            # Choose best image/bbox/embedding from the best-confidence visit that has an image
            best_with_image = None
            for v in sorted(visits, key=lambda x: float(x.highest_confidence or x.confidence_score or 0.0), reverse=True):
                if v.image_path:
                    best_with_image = v
                    break
            
            self._update_job_progress(job.job_id, 50, "Updating primary visit")
            
            # Update primary visit
            primary.first_seen = first_seen
            primary.last_seen = last_seen
            primary.visit_duration_seconds = visit_duration_seconds
            primary.detection_count = detection_count
            primary.highest_confidence = highest_confidence
            primary.confidence_score = highest_confidence
            
            if best_with_image:
                primary.image_path = best_with_image.image_path
                primary.bbox_x = best_with_image.bbox_x
                primary.bbox_y = best_with_image.bbox_y
                primary.bbox_w = best_with_image.bbox_w
                primary.bbox_h = best_with_image.bbox_h
                primary.face_embedding = best_with_image.face_embedding
            
            self._update_job_progress(job.job_id, 60, "Reassigning customer face images")
            
            # Reassign CustomerFaceImage.visit_id to primary visit
            non_primary_visits = [v for v in visits if v.visit_id != primary.visit_id]
            if non_primary_visits:
                await db_session.execute(
                    update(CustomerFaceImage)
                    .where(
                        and_(
                            CustomerFaceImage.tenant_id == job.tenant_id,
                            CustomerFaceImage.visit_id.in_([v.visit_id for v in non_primary_visits])
                        )
                    )
                    .values(visit_id=primary.visit_id)
                )
            
            self._update_job_progress(job.job_id, 70, "Deleting merged visits")
            
            # Collect image paths for cleanup before deletion
            non_primary_with_images: List[Tuple[str, Optional[str]]] = [
                (v.visit_id, v.image_path) for v in non_primary_visits
            ]
            
            # Delete non-primary visits
            if non_primary_visits:
                await db_session.execute(
                    delete(Visit).where(
                        and_(
                            Visit.tenant_id == job.tenant_id,
                            Visit.visit_id.in_([v.visit_id for v in non_primary_visits])
                        )
                    )
                )
            
            # Commit database changes before external cleanup
            await db_session.commit()
            
            self._update_job_progress(job.job_id, 80, "Cleaning up images")
            
            # MinIO cleanup (async, non-blocking)
            images_cleaned = await self._cleanup_minio_images_async(non_primary_with_images)
            
            self._update_job_progress(job.job_id, 90, "Updating customer statistics")
            
            # Recompute customer stats if needed
            if person_type == "customer":
                await self._recompute_customer_stats(db_session, job.tenant_id, person_id)
                await db_session.commit()
            
            self._update_job_progress(job.job_id, 100, "Merge completed successfully")
            
            # Return result
            return {
                "message": f"Merged {len(visit_ids)} visits into {primary.visit_id}",
                "primary_visit_id": primary.visit_id,
                "merged_visit_ids": [v.visit_id for v in non_primary_visits],
                "person_id": person_id,
                "person_type": person_type,
                "site_id": site_id,
                "camera_ids": camera_ids,
                "first_seen": first_seen.isoformat(),
                "last_seen": last_seen.isoformat(),
                "visit_duration_seconds": visit_duration_seconds,
                "detection_count": detection_count,
                "highest_confidence": highest_confidence,
                "images_cleaned": images_cleaned
            }
            
        except Exception as e:
            logger.error(f"Merge visits job {job.job_id} failed: {e}")
            raise
    
    async def execute_cleanup_customer_faces_job(
        self, 
        job: BackgroundJob, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Execute customer face cleanup operation in background"""
        try:
            metadata = job.metadata or {}
            customer_id = metadata.get("customer_id")
            min_confidence = metadata.get("min_confidence", 0.7)
            max_to_remove = metadata.get("max_to_remove", 10)
            
            self._update_job_progress(job.job_id, 20, "Finding low-confidence visits")
            
            # Find low-confidence visits for this customer
            low_confidence_visits_result = await db_session.execute(
                select(Visit.visit_id, Visit.image_path).where(
                    and_(
                        Visit.tenant_id == job.tenant_id,
                        Visit.person_id == customer_id,
                        Visit.person_type == "customer",
                        Visit.confidence_score < min_confidence
                    )
                ).order_by(Visit.confidence_score.asc()).limit(max_to_remove)
            )
            
            visits_to_cleanup = list(low_confidence_visits_result.fetchall())
            visit_ids_to_remove = [row[0] for row in visits_to_cleanup]
            
            if not visit_ids_to_remove:
                return {
                    "message": f"No low-confidence visits found below threshold {min_confidence}",
                    "customer_id": customer_id,
                    "removed_count": 0
                }
            
            self._update_job_progress(job.job_id, 50, f"Removing {len(visit_ids_to_remove)} visits")
            
            # Use bulk delete functionality
            result = await self._bulk_delete_visits(
                db_session, job.tenant_id, visit_ids_to_remove
            )
            
            self._update_job_progress(job.job_id, 100, "Cleanup completed")
            
            return {
                "message": f"Removed {len(visit_ids_to_remove)} low-confidence face detections",
                "customer_id": customer_id,
                "removed_count": len(visit_ids_to_remove),
                "min_confidence_threshold": min_confidence,
                "images_cleaned": result.get("images_cleaned", 0)
            }
            
        except Exception as e:
            logger.error(f"Cleanup customer faces job {job.job_id} failed: {e}")
            raise
    
    async def execute_bulk_delete_visits_job(
        self, 
        job: BackgroundJob, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Execute bulk visit deletion in background"""
        try:
            metadata = job.metadata or {}
            visit_ids = metadata.get("visit_ids", [])
            
            if not visit_ids:
                raise ValueError("No visit IDs provided for deletion")
            
            self._update_job_progress(job.job_id, 20, f"Deleting {len(visit_ids)} visits")
            
            result = await self._bulk_delete_visits(db_session, job.tenant_id, visit_ids)
            
            self._update_job_progress(job.job_id, 100, "Bulk deletion completed")
            
            return result
            
        except Exception as e:
            logger.error(f"Bulk delete visits job {job.job_id} failed: {e}")
            raise
    
    async def execute_bulk_merge_customers_job(
        self, 
        job: BackgroundJob, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Execute bulk customer merge operation in background"""
        try:
            metadata = job.metadata or {}
            merges = metadata.get("merges", [])
            
            if not merges:
                raise ValueError("No merge operations provided")
            
            self._update_job_progress(job.job_id, 10, "Starting bulk customer merge")
            
            total_operations = len(merges)
            completed_merges = []
            failed_merges = []
            
            for i, merge_op in enumerate(merges):
                try:
                    primary_id = merge_op["primary_customer_id"]
                    secondary_ids = merge_op["secondary_customer_ids"]
                    
                    progress = 10 + int((i / total_operations) * 80)  # 10-90% range
                    self._update_job_progress(
                        job.job_id, 
                        progress, 
                        f"Processing merge {i+1}/{total_operations}: merging {len(secondary_ids)} customers into {primary_id}"
                    )
                    
                    # Execute merges for each secondary customer
                    merge_results = []
                    for secondary_id in secondary_ids:
                        try:
                            result = await self._execute_single_customer_merge(
                                db_session, job.tenant_id, primary_id, secondary_id
                            )
                            merge_results.append({
                                "primary_id": primary_id,
                                "secondary_id": secondary_id,
                                "status": "success",
                                "details": result
                            })
                        except Exception as merge_error:
                            logger.error(f"Failed to merge customer {secondary_id} into {primary_id}: {merge_error}")
                            merge_results.append({
                                "primary_id": primary_id,
                                "secondary_id": secondary_id,
                                "status": "failed",
                                "error": str(merge_error)
                            })
                    
                    completed_merges.append({
                        "operation_index": i,
                        "primary_customer_id": primary_id,
                        "secondary_customer_ids": secondary_ids,
                        "merge_results": merge_results,
                        "successful_merges": len([r for r in merge_results if r["status"] == "success"]),
                        "failed_merges": len([r for r in merge_results if r["status"] == "failed"])
                    })
                    
                except Exception as op_error:
                    logger.error(f"Failed merge operation {i}: {op_error}")
                    failed_merges.append({
                        "operation_index": i,
                        "merge_operation": merge_op,
                        "error": str(op_error)
                    })
            
            self._update_job_progress(job.job_id, 100, "Bulk customer merge completed")
            
            # Calculate summary statistics
            total_successful_merges = sum(op.get("successful_merges", 0) for op in completed_merges)
            total_failed_merges = sum(op.get("failed_merges", 0) for op in completed_merges) + len(failed_merges)
            
            return {
                "message": f"Bulk customer merge completed: {total_successful_merges} successful, {total_failed_merges} failed",
                "total_operations": total_operations,
                "completed_operations": len(completed_merges),
                "failed_operations": len(failed_merges),
                "total_successful_merges": total_successful_merges,
                "total_failed_merges": total_failed_merges,
                "completed_merges": completed_merges,
                "failed_operations": failed_merges
            }
            
        except Exception as e:
            logger.error(f"Bulk merge customers job {job.job_id} failed: {e}")
            raise
    
    async def _bulk_delete_visits(
        self, 
        db_session: AsyncSession, 
        tenant_id: str, 
        visit_ids: List[str]
    ) -> Dict[str, Any]:
        """Helper method for bulk visit deletion"""
        
        # Get visits with their image paths for cleanup
        visits_with_images_query = select(Visit.visit_id, Visit.image_path).where(
            and_(
                Visit.tenant_id == tenant_id,
                Visit.visit_id.in_(visit_ids)
            )
        )
        result = await db_session.execute(visits_with_images_query)
        visits_with_images = result.all()
        
        # Get associated customer face images
        customer_face_images_query = select(CustomerFaceImage.image_path).where(
            and_(
                CustomerFaceImage.tenant_id == tenant_id,
                CustomerFaceImage.visit_id.in_(visit_ids)
            )
        )
        result = await db_session.execute(customer_face_images_query)
        customer_face_image_paths = [row[0] for row in result.all()]
        
        # Delete customer face images first
        await db_session.execute(
            delete(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.visit_id.in_(visit_ids)
                )
            )
        )
        
        # Delete visits
        delete_result = await db_session.execute(
            delete(Visit).where(
                and_(
                    Visit.tenant_id == tenant_id,
                    Visit.visit_id.in_(visit_ids)
                )
            )
        )
        
        await db_session.commit()
        
        # Cleanup images (async, non-blocking)
        visit_image_paths = [(vid, img_path) for vid, img_path in visits_with_images if img_path]
        customer_image_tuples = [("customer_face", path) for path in customer_face_image_paths if path]
        
        all_image_paths = visit_image_paths + customer_image_tuples
        images_cleaned = await self._cleanup_minio_images_async(all_image_paths)
        
        return {
            "message": f"Successfully deleted {delete_result.rowcount} visit(s)",
            "deleted_count": delete_result.rowcount,
            "deleted_visit_ids": visit_ids,
            "images_cleaned": images_cleaned
        }
    
    async def _cleanup_minio_images_async(
        self, 
        image_paths: List[Tuple[str, Optional[str]]]
    ) -> int:
        """Cleanup MinIO images asynchronously without blocking"""
        images_cleaned = 0
        
        if not image_paths:
            return images_cleaned
        
        try:
            from ..core.minio_client import minio_client
            
            # Process images in small batches to avoid overwhelming MinIO
            batch_size = 10
            for i in range(0, len(image_paths), batch_size):
                batch = image_paths[i:i + batch_size]
                
                # Run each batch concurrently
                tasks = []
                for item_id, image_path in batch:
                    if image_path:
                        task = asyncio.create_task(
                            self._delete_single_image(minio_client, image_path)
                        )
                        tasks.append(task)
                
                # Wait for batch completion
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    images_cleaned += sum(1 for result in results if result is True)
                
                # Small delay between batches to be nice to MinIO
                if i + batch_size < len(image_paths):
                    await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error during async image cleanup: {e}")
        
        return images_cleaned
    
    async def _delete_single_image(self, minio_client, image_path: str) -> bool:
        """Delete a single image from MinIO"""
        try:
            if image_path.startswith('s3://'):
                # Extract bucket and object name from s3://bucket/object format
                path_parts = image_path[5:].split('/', 1)
                if len(path_parts) == 2:
                    bucket, object_name = path_parts
                    minio_client.delete_file(bucket, object_name)
                    return True
            elif image_path.startswith('visits-faces/'):
                # API-generated face crops are in faces-derived bucket
                object_path = image_path.replace('visits-faces/', '')
                minio_client.delete_file('faces-derived', object_path)
                return True
            elif image_path.startswith('customer-faces/'):
                # Legacy format - remove the prefix
                object_path = image_path.replace('customer-faces/', '')
                minio_client.delete_file('faces-derived', object_path)
                return True
            elif not image_path.startswith('http'):
                # Assume it's a path in the faces-raw bucket
                minio_client.delete_file('faces-raw', image_path)
                return True
                
        except Exception as e:
            logger.warning(f"Failed to delete image {image_path}: {e}")
        
        return False
    
    async def _recompute_customer_stats(
        self, 
        db_session: AsyncSession, 
        tenant_id: str, 
        customer_id: int
    ):
        """Recompute customer visit statistics"""
        stats_res = await db_session.execute(
            select(
                func.count(Visit.visit_id),
                func.min(Visit.first_seen),
                func.max(Visit.last_seen),
            ).where(
                and_(
                    Visit.tenant_id == tenant_id,
                    Visit.person_type == "customer",
                    Visit.person_id == customer_id,
                )
            )
        )
        count, c_first, c_last = stats_res.first() or (0, None, None)
        
        await db_session.execute(
            update(Customer)
            .where(and_(Customer.tenant_id == tenant_id, Customer.customer_id == customer_id))
            .values(visit_count=int(count or 0), first_seen=c_first, last_seen=c_last)
        )
    
    async def _execute_single_customer_merge(
        self,
        db_session: AsyncSession,
        tenant_id: str,
        primary_customer_id: int,
        secondary_customer_id: int
    ) -> Dict[str, Any]:
        """Execute a single customer merge operation"""
        from ..models.database import Customer, Visit, CustomerFaceImage
        from ..core.milvus_client import milvus_client
        import json
        import hashlib
        from datetime import datetime
        
        # Validate both customers exist
        result = await db_session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == tenant_id,
                    Customer.customer_id.in_([primary_customer_id, secondary_customer_id])
                )
            )
        )
        customers = {c.customer_id: c for c in result.scalars().all()}
        
        if primary_customer_id not in customers:
            raise ValueError(f"Primary customer {primary_customer_id} not found")
        if secondary_customer_id not in customers:
            # Already merged or deleted - return success
            return {
                "message": f"Secondary customer {secondary_customer_id} already merged or deleted",
                "status": "already_merged"
            }
        
        primary_customer = customers[primary_customer_id]
        secondary_customer = customers[secondary_customer_id]
        
        # Count data to be merged
        visits_result = await db_session.execute(
            select(func.count(Visit.visit_id)).where(
                and_(
                    Visit.tenant_id == tenant_id,
                    Visit.person_type == "customer",
                    Visit.person_id == secondary_customer_id
                )
            )
        )
        visits_to_merge = visits_result.scalar() or 0
        
        face_images_result = await db_session.execute(
            select(func.count(CustomerFaceImage.image_id)).where(
                and_(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.customer_id == secondary_customer_id
                )
            )
        )
        face_images_to_merge = face_images_result.scalar() or 0
        
        # 1. Reassign visits
        if visits_to_merge > 0:
            await db_session.execute(
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
        
        # 2. Reassign face images
        if face_images_to_merge > 0:
            await db_session.execute(
                update(CustomerFaceImage)
                .where(
                    and_(
                        CustomerFaceImage.tenant_id == tenant_id,
                        CustomerFaceImage.customer_id == secondary_customer_id,
                    )
                )
                .values(customer_id=primary_customer_id)
            )
        
        # 3. Deduplicate face images by hash (keep highest quality)
        dedup_count = await self._deduplicate_customer_face_images(
            db_session, tenant_id, primary_customer_id
        )
        
        # 4. Copy missing attributes from secondary to primary
        updates = {}
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
        
        # 5. Recompute primary customer stats
        await self._recompute_customer_stats(db_session, tenant_id, primary_customer_id)
        
        # Apply attribute updates if any
        if updates:
            await db_session.execute(
                update(Customer)
                .where(and_(Customer.tenant_id == tenant_id, Customer.customer_id == primary_customer_id))
                .values(**updates)
            )
        
        # 6. Delete secondary customer
        await db_session.execute(
            delete(Customer).where(
                and_(Customer.tenant_id == tenant_id, Customer.customer_id == secondary_customer_id)
            )
        )
        
        # 7. Handle embeddings (best effort)
        embeddings_updated = False
        try:
            # Delete old embeddings for both customers
            await milvus_client.delete_person_embeddings(tenant_id, secondary_customer_id, "customer")
            await milvus_client.delete_person_embeddings(tenant_id, primary_customer_id, "customer")
            
            # Rebuild embeddings for primary customer from gallery and visits
            embeddings_count = await self._rebuild_customer_embeddings(
                db_session, tenant_id, primary_customer_id
            )
            embeddings_updated = True
            
        except Exception as e:
            logger.warning(f"Embedding maintenance failed during merge {primary_customer_id}<-{secondary_customer_id}: {e}")
        
        return {
            "message": f"Successfully merged customer {secondary_customer_id} into {primary_customer_id}",
            "primary_customer_id": primary_customer_id,
            "secondary_customer_id": secondary_customer_id,
            "visits_merged": visits_to_merge,
            "face_images_merged": face_images_to_merge,
            "face_images_deduplicated": dedup_count,
            "attributes_copied": list(updates.keys()),
            "embeddings_updated": embeddings_updated
        }
    
    async def _deduplicate_customer_face_images(
        self,
        db_session: AsyncSession,
        tenant_id: str,
        customer_id: int
    ) -> int:
        """Remove duplicate face images based on hash, keeping highest quality"""
        from ..models.database import CustomerFaceImage
        
        # Get all images with hashes for this customer
        images_result = await db_session.execute(
            select(CustomerFaceImage).where(
                and_(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.customer_id == customer_id,
                    CustomerFaceImage.image_hash.is_not(None),
                )
            )
        )
        
        images = images_result.scalars().all()
        if len(images) <= 1:
            return 0
        
        # Group by hash and find duplicates
        by_hash = {}
        to_delete = []
        
        def quality_score(img):
            return float((img.confidence_score or 0.0) + (img.quality_score or 0.5))
        
        for img in images:
            if not img.image_hash:
                continue
                
            existing = by_hash.get(img.image_hash)
            if not existing:
                by_hash[img.image_hash] = img
            else:
                # Keep the higher quality image
                if quality_score(img) > quality_score(existing):
                    to_delete.append(int(existing.image_id))
                    by_hash[img.image_hash] = img
                else:
                    to_delete.append(int(img.image_id))
        
        # Delete duplicates
        if to_delete:
            await db_session.execute(
                delete(CustomerFaceImage).where(
                    and_(
                        CustomerFaceImage.tenant_id == tenant_id,
                        CustomerFaceImage.customer_id == customer_id,
                        CustomerFaceImage.image_id.in_(to_delete),
                    )
                )
            )
        
        return len(to_delete)
    
    async def _rebuild_customer_embeddings(
        self,
        db_session: AsyncSession,
        tenant_id: str,
        customer_id: int
    ) -> int:
        """Rebuild embeddings for a customer from gallery and visits"""
        from ..models.database import CustomerFaceImage, Visit
        from ..core.milvus_client import milvus_client
        from datetime import datetime
        import json
        import hashlib
        
        aggregated = []
        inserted_keys = set()
        
        # Get embeddings from gallery
        gallery_result = await db_session.execute(
            select(CustomerFaceImage.embedding, CustomerFaceImage.created_at, CustomerFaceImage.image_hash)
            .where(
                and_(
                    CustomerFaceImage.tenant_id == tenant_id,
                    CustomerFaceImage.customer_id == customer_id,
                    CustomerFaceImage.embedding.is_not(None),
                )
            )
        )
        
        for emb, created_at, img_hash in gallery_result.all():
            if not emb or not isinstance(emb, list) or len(emb) != 512:
                continue
            
            key = f"img:{img_hash}" if img_hash else f"vec:{hashlib.sha256(str(emb).encode()).hexdigest()}"
            if key in inserted_keys:
                continue
                
            inserted_keys.add(key)
            timestamp = int((created_at or datetime.utcnow()).timestamp())
            aggregated.append((emb, timestamp))
        
        # Get embeddings from visits
        visits_result = await db_session.execute(
            select(Visit.face_embedding, Visit.timestamp)
            .where(
                and_(
                    Visit.tenant_id == tenant_id,
                    Visit.person_type == "customer",
                    Visit.person_id == customer_id,
                    Visit.face_embedding.is_not(None),
                )
            )
        )
        
        for emb_text, timestamp_dt in visits_result.all():
            if not emb_text:
                continue
                
            try:
                emb = json.loads(emb_text)
            except Exception:
                continue
                
            if not isinstance(emb, list) or len(emb) != 512:
                continue
                
            key = f"vis:{hashlib.sha256(str(emb).encode()).hexdigest()}"
            if key in inserted_keys:
                continue
                
            inserted_keys.add(key)
            timestamp = int((timestamp_dt or datetime.utcnow()).timestamp())
            aggregated.append((emb, timestamp))
        
        # Insert into Milvus
        inserted_count = 0
        for emb, timestamp in aggregated:
            try:
                await milvus_client.insert_embedding(
                    tenant_id, customer_id, "customer", emb, timestamp
                )
                inserted_count += 1
            except Exception as e:
                logger.warning(f"Failed to insert embedding for customer {customer_id}: {e}")
        
        return inserted_count


# Create service instance
merge_service = MergeService()