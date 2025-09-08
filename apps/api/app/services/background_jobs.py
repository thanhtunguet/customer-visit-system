"""
Background job service for handling long-running operations asynchronously.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundJob:
    """Represents a background job with status tracking"""
    job_id: str
    job_type: str
    status: JobStatus
    tenant_id: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0  # 0-100
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BackgroundJobService:
    """Service for managing background jobs"""
    
    def __init__(self):
        self.jobs: Dict[str, BackgroundJob] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.job_handlers: Dict[str, Callable] = {}
        self._handlers_registered = False
    
    def _register_handlers(self):
        """Register job type handlers - called lazily to avoid circular imports"""
        if not self._handlers_registered:
            # Import here to avoid circular imports
            from .merge_service import merge_service
            
            self.job_handlers = {
                "merge_visits": merge_service.execute_merge_visits_job,
                "cleanup_customer_faces": merge_service.execute_cleanup_customer_faces_job,
                "bulk_delete_visits": merge_service.execute_bulk_delete_visits_job,
            }
            self._handlers_registered = True
    
    async def create_job(
        self, 
        job_type: str, 
        tenant_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new background job and return job ID"""
        job_id = str(uuid.uuid4())
        
        job = BackgroundJob(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            tenant_id=tenant_id,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        self.jobs[job_id] = job
        logger.info(f"Created background job {job_id} of type {job_type} for tenant {tenant_id}")
        
        return job_id
    
    async def start_job(self, job_id: str, db_session_factory) -> bool:
        """Start executing a background job"""
        if job_id not in self.jobs:
            logger.error(f"Job {job_id} not found")
            return False
            
        job = self.jobs[job_id]
        
        if job.status != JobStatus.PENDING:
            logger.error(f"Job {job_id} is not in pending status: {job.status}")
            return False
            
        # Ensure handlers are registered
        self._register_handlers()
            
        if job.job_type not in self.job_handlers:
            logger.error(f"No handler found for job type: {job.job_type}")
            job.status = JobStatus.FAILED
            job.error = f"No handler for job type: {job.job_type}"
            return False
        
        # Start the job in background
        task = asyncio.create_task(
            self._execute_job(job, db_session_factory)
        )
        self.running_tasks[job_id] = task
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.message = "Job started"
        
        logger.info(f"Started background job {job_id}")
        return True
    
    async def _execute_job(self, job: BackgroundJob, db_session_factory):
        """Execute a job in background"""
        try:
            handler = self.job_handlers[job.job_type]
            
            # Create a new database session for the job
            async for db_session in db_session_factory():
                try:
                    # Set tenant context
                    from ..core.database import db
                    await db.set_tenant_context(db_session, job.tenant_id)
                    
                    # Execute the job
                    result = await handler(job, db_session)
                    
                    # Update job status
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now(timezone.utc)
                    job.progress = 100
                    job.result = result
                    job.message = "Job completed successfully"
                    
                    await db_session.commit()
                    logger.info(f"Background job {job.job_id} completed successfully")
                    
                except Exception as e:
                    await db_session.rollback()
                    raise e
                finally:
                    await db_session.close()
                break
                    
        except Exception as e:
            logger.error(f"Background job {job.job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error = str(e)
            job.message = f"Job failed: {str(e)}"
            
        finally:
            # Clean up the running task
            if job.job_id in self.running_tasks:
                del self.running_tasks[job.job_id]
    
    def get_job_status(self, job_id: str) -> Optional[BackgroundJob]:
        """Get job status by ID"""
        return self.jobs.get(job_id)
    
    def get_jobs_for_tenant(self, tenant_id: str) -> List[BackgroundJob]:
        """Get all jobs for a tenant"""
        return [job for job in self.jobs.values() if job.tenant_id == tenant_id]
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        if job_id not in self.jobs:
            return False
            
        job = self.jobs[job_id]
        
        if job.status == JobStatus.RUNNING:
            # Cancel the asyncio task
            if job_id in self.running_tasks:
                task = self.running_tasks[job_id]
                task.cancel()
                del self.running_tasks[job_id]
            
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            job.message = "Job cancelled by user"
            
            logger.info(f"Cancelled background job {job_id}")
            return True
            
        return False
    
    def update_job_progress(self, job_id: str, progress: int, message: str = ""):
        """Update job progress"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            job.progress = min(100, max(0, progress))
            if message:
                job.message = message
            logger.debug(f"Job {job_id} progress: {progress}% - {message}")
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up jobs older than max_age_hours"""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            job_time = job.completed_at or job.created_at
            if job_time.timestamp() < cutoff and job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            logger.debug(f"Cleaned up old job {job_id}")
        
        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")


# Global background job service instance
background_job_service = BackgroundJobService()