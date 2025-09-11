"""
Lease Management Endpoints for Camera-Worker Delegation
Implements GPT Plan Section 4.1: /leases/renew and /leases/reclaim endpoints
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.correlation import get_or_create_correlation_id, get_structured_logger
from ..core.database import get_db
from ..models.database import CameraSession
from ..services.assignment_service import assignment_service
from ..services.worker_registry import worker_registry

router = APIRouter(prefix="/leases", tags=["lease-management"])
logger = get_structured_logger(__name__)


# Request/Response Models


class LeaseRenewalItem(BaseModel):
    """Single lease renewal item"""

    camera_id: int
    generation: int


class LeaseRenewalRequest(BaseModel):
    """Request to renew multiple leases"""

    worker_id: str
    renewals: List[LeaseRenewalItem]


class LeaseRenewalResponse(BaseModel):
    """Response for lease renewal"""

    worker_id: str
    total_requested: int
    successful_renewals: int
    failed_renewals: int
    details: List[Dict[str, Any]]


class LeaseReclaimResponse(BaseModel):
    """Response for lease reclaim operation"""

    total_expired: int
    reclaimed_count: int
    errors: List[str]
    reclaimed_leases: List[Dict[str, Any]]


class LeaseStatusResponse(BaseModel):
    """Response for lease status query"""

    active_leases: int
    expired_leases: int
    orphaned_leases: int
    leases: List[Dict[str, Any]]


# Endpoints


@router.post("/renew", response_model=LeaseRenewalResponse)
async def renew_leases(
    request: LeaseRenewalRequest, db: AsyncSession = Depends(get_db)
):
    """
    Renew leases for worker's active cameras

    Based on GPT Plan: POST /leases/renew - extend lease_expires_at for heartbeat tuples
    """
    correlation_id = get_or_create_correlation_id()

    logger.info(
        "lease_renewal_request",
        worker_id=request.worker_id,
        renewal_count=len(request.renewals),
        correlation_id=correlation_id,
    )

    # Validate worker exists
    worker = worker_registry.get_worker(request.worker_id)
    if not worker:
        raise HTTPException(
            status_code=404, detail=f"Worker {request.worker_id} not found"
        )

    # Convert to assignment service format
    renewal_requests = [
        {"camera_id": r.camera_id, "generation": r.generation} for r in request.renewals
    ]

    try:
        result = await assignment_service.renew_lease(
            db=db, worker_id=request.worker_id, renewals=renewal_requests
        )

        # Process results
        successful = len([r for r in result["renewals"] if r["status"] == "renewed"])
        failed = len(request.renewals) - successful

        logger.info(
            "lease_renewal_completed",
            worker_id=request.worker_id,
            successful=successful,
            failed=failed,
            correlation_id=correlation_id,
        )

        return LeaseRenewalResponse(
            worker_id=request.worker_id,
            total_requested=len(request.renewals),
            successful_renewals=successful,
            failed_renewals=failed,
            details=result["renewals"],
        )

    except Exception as e:
        logger.error(
            "lease_renewal_error",
            worker_id=request.worker_id,
            error=str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(status_code=500, detail=f"Lease renewal failed: {str(e)}")


@router.post("/reclaim", response_model=LeaseReclaimResponse)
async def reclaim_expired_leases(
    db: AsyncSession = Depends(get_db), force: bool = False
):
    """
    Reclaim expired leases (>90s as per updated GPT plan)

    Based on GPT Plan: POST /leases/reclaim - cron/scheduler to mark ORPHANED when expired
    """
    correlation_id = get_or_create_correlation_id()

    logger.info("lease_reclaim_request", force=force, correlation_id=correlation_id)

    try:
        result = await assignment_service.reclaim_expired_leases(db)

        logger.info(
            "lease_reclaim_completed",
            reclaimed_count=result["reclaimed_count"],
            correlation_id=correlation_id,
        )

        return LeaseReclaimResponse(
            total_expired=result["reclaimed_count"],  # Same value for now
            reclaimed_count=result["reclaimed_count"],
            errors=[],
            reclaimed_leases=[],  # Could be enhanced to return details
        )

    except Exception as e:
        logger.error("lease_reclaim_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail=f"Lease reclaim failed: {str(e)}")


@router.get("/status", response_model=LeaseStatusResponse)
async def get_lease_status(
    db: AsyncSession = Depends(get_db),
    tenant_id: Optional[str] = None,
    worker_id: Optional[str] = None,
):
    """
    Get current lease status and statistics

    Optional filtering by tenant_id or worker_id
    """
    correlation_id = get_or_create_correlation_id()

    try:
        from sqlalchemy import and_, select

        # Build query with optional filters
        query = select(CameraSession)
        filters = []

        if tenant_id:
            filters.append(CameraSession.tenant_id == tenant_id)
        if worker_id:
            filters.append(CameraSession.worker_id == worker_id)

        if filters:
            query = query.where(and_(*filters))

        result = await db.execute(query)
        sessions = result.scalars().all()

        # Calculate statistics
        now = datetime.utcnow()
        active_count = 0
        expired_count = 0
        orphaned_count = 0

        lease_details = []

        for session in sessions:
            is_expired = session.lease_expires_at and session.lease_expires_at < now

            if session.state == "ACTIVE" and not is_expired:
                active_count += 1
            elif is_expired:
                expired_count += 1
                if session.state == "ORPHANED":
                    orphaned_count += 1

            lease_details.append(
                {
                    "camera_id": session.camera_id,
                    "worker_id": session.worker_id,
                    "state": session.state,
                    "generation": session.generation,
                    "lease_expires_at": (
                        session.lease_expires_at.isoformat()
                        if session.lease_expires_at
                        else None
                    ),
                    "is_expired": is_expired,
                    "updated_at": (
                        session.updated_at.isoformat() if session.updated_at else None
                    ),
                }
            )

        logger.info(
            "lease_status_queried",
            active_count=active_count,
            expired_count=expired_count,
            orphaned_count=orphaned_count,
            tenant_id=tenant_id,
            worker_id=worker_id,
            correlation_id=correlation_id,
        )

        return LeaseStatusResponse(
            active_leases=active_count,
            expired_leases=expired_count,
            orphaned_leases=orphaned_count,
            leases=lease_details,
        )

    except Exception as e:
        logger.error("lease_status_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to get lease status: {str(e)}"
        )


@router.delete("/cleanup")
async def cleanup_terminated_leases(
    db: AsyncSession = Depends(get_db), older_than_hours: int = 24
):
    """
    Clean up old TERMINATED lease records

    Removes lease records that have been in TERMINATED state for more than specified hours
    """
    correlation_id = get_or_create_correlation_id()

    try:
        from sqlalchemy import and_, delete

        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

        result = await db.execute(
            delete(CameraSession).where(
                and_(
                    CameraSession.state == "TERMINATED",
                    CameraSession.updated_at < cutoff_time,
                )
            )
        )

        await db.commit()

        cleaned_count = result.rowcount

        logger.info(
            "lease_cleanup_completed",
            cleaned_count=cleaned_count,
            older_than_hours=older_than_hours,
            correlation_id=correlation_id,
        )

        return {
            "message": f"Cleaned up {cleaned_count} terminated lease records",
            "cleaned_count": cleaned_count,
            "older_than_hours": older_than_hours,
        }

    except Exception as e:
        logger.error("lease_cleanup_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail=f"Lease cleanup failed: {str(e)}")


@router.post("/assign")
async def manual_assign_camera(
    worker_id: str,
    tenant_id: str,
    site_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger camera assignment for a worker

    Based on GPT Plan: POST /assign (internal) - picks a camera for worker_id
    """
    correlation_id = get_or_create_correlation_id()

    logger.info(
        "manual_assignment_request",
        worker_id=worker_id,
        tenant_id=tenant_id,
        site_id=site_id,
        correlation_id=correlation_id,
    )

    # Validate worker
    worker = worker_registry.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")

    if worker.tenant_id != tenant_id:
        raise HTTPException(
            status_code=400, detail="Worker belongs to different tenant"
        )

    try:
        camera = await assignment_service.assign_camera_with_lease(
            db=db, tenant_id=tenant_id, worker_id=worker_id, site_id=site_id
        )

        if camera:
            logger.info(
                "manual_assignment_success",
                worker_id=worker_id,
                camera_id=camera.camera_id,
                correlation_id=correlation_id,
            )

            return {
                "message": f"Camera {camera.camera_id} assigned to worker {worker_id}",
                "camera_id": camera.camera_id,
                "camera_name": camera.name,
                "worker_id": worker_id,
                "assignment_time": datetime.utcnow().isoformat(),
            }
        else:
            logger.warning(
                "manual_assignment_no_cameras",
                worker_id=worker_id,
                tenant_id=tenant_id,
                site_id=site_id,
                correlation_id=correlation_id,
            )

            raise HTTPException(
                status_code=404, detail="No available cameras found for assignment"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "manual_assignment_error",
            worker_id=worker_id,
            error=str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(status_code=500, detail=f"Assignment failed: {str(e)}")
