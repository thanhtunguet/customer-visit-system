"""
Background job management API endpoints.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..core.security import get_current_user
from ..services.background_jobs import BackgroundJob, JobStatus, background_job_service

router = APIRouter(prefix="/v1", tags=["Background Jobs"])
logger = logging.getLogger(__name__)


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: JobStatus
    tenant_id: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int
    message: str
    result: Optional[dict] = None
    error: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: List[JobStatusResponse]
    total: int


def _job_to_response(job: BackgroundJob) -> JobStatusResponse:
    """Convert BackgroundJob to API response"""
    return JobStatusResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        tenant_id=job.tenant_id,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        progress=job.progress,
        message=job.message,
        result=job.result,
        error=job.error,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, user: dict = Depends(get_current_user)):
    """Get status of a specific background job"""
    job = background_job_service.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Ensure user can only see jobs from their tenant
    if job.tenant_id != user["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this job"
        )

    return _job_to_response(job)


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status_filter: Optional[JobStatus] = None,
    job_type_filter: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List all background jobs for the current tenant"""
    jobs = background_job_service.get_jobs_for_tenant(user["tenant_id"])

    # Apply filters
    if status_filter:
        jobs = [job for job in jobs if job.status == status_filter]

    if job_type_filter:
        jobs = [job for job in jobs if job.job_type == job_type_filter]

    # Sort by created_at descending (newest first)
    jobs.sort(key=lambda x: x.created_at, reverse=True)

    return JobListResponse(
        jobs=[_job_to_response(job) for job in jobs], total=len(jobs)
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user: dict = Depends(get_current_user)):
    """Cancel a running background job"""
    job = background_job_service.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Ensure user can only cancel jobs from their tenant
    if job.tenant_id != user["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this job"
        )

    success = await background_job_service.cancel_job(job_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job cannot be cancelled (not running or already completed)",
        )

    return {"message": f"Job {job_id} cancelled successfully"}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(get_current_user)):
    """Delete a completed background job"""
    job = background_job_service.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Ensure user can only delete jobs from their tenant
    if job.tenant_id != user["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this job"
        )

    # Only allow deletion of completed, failed, or cancelled jobs
    if job.status == JobStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running job. Cancel it first.",
        )

    # Remove from service
    if job_id in background_job_service.jobs:
        del background_job_service.jobs[job_id]

    return {"message": f"Job {job_id} deleted successfully"}


@router.post("/jobs/cleanup")
async def cleanup_old_jobs(
    max_age_hours: int = 24, user: dict = Depends(get_current_user)
):
    """Clean up old completed jobs (admin operation)"""
    # For now, allow any authenticated user to cleanup old jobs
    # In production, you might want to restrict this to admins only

    old_count = len(background_job_service.jobs)
    background_job_service.cleanup_old_jobs(max_age_hours)
    new_count = len(background_job_service.jobs)

    cleaned_count = old_count - new_count

    return {
        "message": f"Cleaned up {cleaned_count} old jobs",
        "cleaned_count": cleaned_count,
        "max_age_hours": max_age_hours,
    }
