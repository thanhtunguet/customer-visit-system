"""
Lease-based Assignment Service for Camera-Worker Delegation
Implements the GPT plan's optimistic concurrency control and capacity-aware assignment
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, text
from sqlalchemy.exc import IntegrityError
from uuid import uuid4

from ..models.database import Camera, Worker, CameraSession
from ..core.correlation import get_structured_logger, get_or_create_correlation_id
from .worker_registry import worker_registry, WorkerInfo, WorkerStatus

logger = get_structured_logger(__name__)


class SessionState:
    """Camera session states as per GPT plan"""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ORPHANED = "ORPHANED"
    TERMINATED = "TERMINATED"


class AssignmentService:
    """
    Lease-based camera assignment service with optimistic concurrency control
    
    Key features:
    - Site-aware filtering
    - Capacity-aware assignment (least slots used)
    - Optimistic concurrency with generation tracking
    - 90s lease TTL with automatic reclaim
    """
    
    def __init__(self):
        self.lease_ttl = timedelta(seconds=90)  # 90s as per updated plan
        self.cleanup_task: Optional[asyncio.Task] = None
        self.cleanup_interval = 30  # Check every 30s for expired leases
        
    async def assign_camera_with_lease(
        self, 
        db: AsyncSession, 
        tenant_id: str, 
        worker_id: str, 
        site_id: int
    ) -> Optional[Camera]:
        """
        Assign an available camera to a worker using lease-based coordination
        
        Implementation follows GPT plan's optimistic concurrency algorithm:
        1. Find candidate cameras (site-aware + capacity-aware)
        2. Try to acquire lease with optimistic locking
        3. Retry with next candidate if conflict
        """
        correlation_id = get_or_create_correlation_id()
        
        logger.info(
            "lease_assignment_start",
            worker_id=worker_id,
            tenant_id=tenant_id,
            site_id=site_id,
            correlation_id=correlation_id
        )
        
        # Get worker info and validate capacity
        worker = worker_registry.get_worker(worker_id)
        if not worker:
            logger.warning(
                "lease_assignment_failed",
                reason="worker_not_found",
                worker_id=worker_id,
                correlation_id=correlation_id
            )
            return None
            
        if worker.tenant_id != tenant_id:
            logger.warning(
                "lease_assignment_failed", 
                reason="tenant_mismatch",
                worker_id=worker_id,
                worker_tenant=worker.tenant_id,
                expected_tenant=tenant_id,
                correlation_id=correlation_id
            )
            return None
        
        # Find candidate cameras in priority order (capacity-aware)
        candidates = await self._find_available_cameras(db, tenant_id, site_id)
        
        logger.info(
            "lease_candidates_found",
            candidate_count=len(candidates),
            tenant_id=tenant_id,
            site_id=site_id,
            correlation_id=correlation_id
        )
        
        # Try to acquire lease for each candidate
        for camera in candidates:
            session = await self._try_acquire_lease(
                db, camera.camera_id, worker_id, correlation_id
            )
            if session:
                # Update worker registry
                worker.camera_id = camera.camera_id
                worker.status = WorkerStatus.PROCESSING
                
                logger.info(
                    "lease_acquired_successfully",
                    camera_id=camera.camera_id,
                    worker_id=worker_id,
                    generation=session.generation,
                    lease_expires_at=session.lease_expires_at.isoformat(),
                    correlation_id=correlation_id
                )
                
                # Send START command to worker
                await self._send_start_command(
                    worker_id, camera, session.generation, correlation_id
                )
                
                return camera
        
        logger.warning(
            "lease_assignment_failed",
            reason="no_available_cameras",
            candidate_count=len(candidates),
            tenant_id=tenant_id,
            site_id=site_id,
            correlation_id=correlation_id
        )
        return None
    
    async def _find_available_cameras(
        self, 
        db: AsyncSession, 
        tenant_id: str, 
        site_id: int
    ) -> List[Camera]:
        """
        Find available cameras with site filtering
        TODO: Add capacity-aware sorting
        """
        result = await db.execute(
            select(Camera).where(
                and_(
                    Camera.tenant_id == tenant_id,
                    Camera.site_id == site_id,
                    Camera.is_active == True
                )
            )
        )
        return list(result.scalars().all())
    
    async def _try_acquire_lease(
        self, 
        db: AsyncSession, 
        camera_id: int, 
        worker_id: str,
        correlation_id: str
    ) -> Optional[CameraSession]:
        """
        Try to acquire lease using optimistic concurrency control
        
        Based on GPT plan's SQL pattern:
        UPDATE camera_sessions
          SET worker_id=:wid, lease_expires_at=now()+:ttl, state='ACTIVE', 
              generation=generation+1, updated_at=now()
          WHERE camera_id=:cid AND (worker_id IS NULL OR lease_expires_at < now()) 
              AND generation=:expected_gen;
        """
        try:
            # Get or create session
            session = await self._get_or_create_session(db, camera_id)
            expected_generation = session.generation
            
            # Try optimistic update
            lease_expires_at = datetime.utcnow() + self.lease_ttl
            
            result = await db.execute(
                update(CameraSession)
                .where(
                    and_(
                        CameraSession.camera_id == camera_id,
                        CameraSession.generation == expected_generation,
                        # Available if no worker or lease expired
                        (
                            (CameraSession.worker_id.is_(None)) |
                            (CameraSession.lease_expires_at < datetime.utcnow())
                        )
                    )
                )
                .values(
                    worker_id=worker_id,
                    lease_expires_at=lease_expires_at,
                    state=SessionState.ACTIVE,
                    generation=CameraSession.generation + 1,
                    updated_at=datetime.utcnow()
                )
            )
            
            if result.rowcount == 0:
                logger.debug(
                    "lease_acquisition_conflict",
                    camera_id=camera_id,
                    expected_generation=expected_generation,
                    correlation_id=correlation_id
                )
                return None
            
            # Fetch updated session
            result = await db.execute(
                select(CameraSession).where(CameraSession.camera_id == camera_id)
            )
            updated_session = result.scalar_one_or_none()
            
            await db.commit()
            
            logger.info(
                "lease_acquired",
                camera_id=camera_id,
                worker_id=worker_id,
                generation=updated_session.generation,
                lease_expires_at=lease_expires_at.isoformat(),
                correlation_id=correlation_id
            )
            
            return updated_session
            
        except Exception as e:
            await db.rollback()
            logger.error(
                "lease_acquisition_error",
                camera_id=camera_id,
                worker_id=worker_id,
                error=str(e),
                correlation_id=correlation_id
            )
            return None
    
    async def _get_or_create_session(
        self, 
        db: AsyncSession, 
        camera_id: int
    ) -> CameraSession:
        """Get existing session or create new one"""
        result = await db.execute(
            select(CameraSession).where(CameraSession.camera_id == camera_id)
        )
        session = result.scalar_one_or_none()
        
        if session is None:
            # Get camera info for tenant/site
            camera_result = await db.execute(
                select(Camera).where(Camera.camera_id == camera_id)
            )
            camera = camera_result.scalar_one()
            
            # Create new session
            session = CameraSession(
                camera_id=camera_id,
                tenant_id=camera.tenant_id,
                site_id=camera.site_id,
                generation=0,
                state=SessionState.PENDING
            )
            db.add(session)
            await db.commit()
            
        return session
    
    async def _send_start_command(
        self,
        worker_id: str,
        camera: Camera,
        generation: int,
        correlation_id: str
    ):
        """Send START command to worker with intent tracking"""
        try:
            from .worker_command_service import worker_command_service
            from common.enums.commands import WorkerCommand, CommandPriority
            
            intent_id = str(uuid4())
            
            command_id = worker_command_service.send_command(
                worker_id=worker_id,
                command=WorkerCommand.ASSIGN_CAMERA,
                parameters={
                    "intent_id": intent_id,
                    "camera_id": camera.camera_id,
                    "generation": generation,
                    "camera_name": camera.name,
                    "source": {
                        "type": camera.camera_type.value if camera.camera_type else "webcam",
                        "rtsp_url": camera.rtsp_url,
                        "device_index": camera.device_index
                    },
                    "correlation_id": correlation_id
                },
                priority=CommandPriority.HIGH,
                requested_by="lease_assignment_service"
            )
            
            logger.info(
                "start_command_sent",
                intent_id=intent_id,
                command_id=command_id,
                worker_id=worker_id,
                camera_id=camera.camera_id,
                generation=generation,
                correlation_id=correlation_id
            )
            
        except Exception as e:
            logger.error(
                "start_command_failed",
                worker_id=worker_id,
                camera_id=camera.camera_id,
                error=str(e),
                correlation_id=correlation_id
            )
    
    async def renew_lease(
        self, 
        db: AsyncSession, 
        worker_id: str, 
        renewals: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Renew leases for worker's active cameras
        
        renewals format: [{"camera_id": int, "generation": int}, ...]
        """
        correlation_id = get_or_create_correlation_id()
        results = []
        
        for renewal in renewals:
            camera_id = renewal["camera_id"]
            generation = renewal["generation"]
            
            try:
                new_expires_at = datetime.utcnow() + self.lease_ttl
                
                result = await db.execute(
                    update(CameraSession)
                    .where(
                        and_(
                            CameraSession.camera_id == camera_id,
                            CameraSession.worker_id == worker_id,
                            CameraSession.generation == generation
                        )
                    )
                    .values(
                        lease_expires_at=new_expires_at,
                        updated_at=datetime.utcnow()
                    )
                )
                
                if result.rowcount > 0:
                    results.append({
                        "camera_id": camera_id,
                        "status": "renewed",
                        "lease_expires_at": new_expires_at.isoformat()
                    })
                    logger.debug(
                        "lease_renewed",
                        camera_id=camera_id,
                        worker_id=worker_id,
                        generation=generation,
                        new_expires_at=new_expires_at.isoformat(),
                        correlation_id=correlation_id
                    )
                else:
                    results.append({
                        "camera_id": camera_id,
                        "status": "conflict",
                        "reason": "generation_mismatch_or_not_assigned"
                    })
                    
            except Exception as e:
                results.append({
                    "camera_id": camera_id,
                    "status": "error",
                    "error": str(e)
                })
                logger.error(
                    "lease_renewal_error",
                    camera_id=camera_id,
                    worker_id=worker_id,
                    error=str(e),
                    correlation_id=correlation_id
                )
        
        await db.commit()
        return {"renewals": results}
    
    async def reclaim_expired_leases(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Reclaim expired leases (>90s as per updated plan)
        Mark as ORPHANED and available for reassignment
        """
        correlation_id = get_or_create_correlation_id()
        
        # Find expired leases
        expired_threshold = datetime.utcnow()
        result = await db.execute(
            select(CameraSession).where(
                and_(
                    CameraSession.lease_expires_at < expired_threshold,
                    CameraSession.state == SessionState.ACTIVE
                )
            )
        )
        expired_sessions = result.scalars().all()
        
        reclaimed_count = 0
        for session in expired_sessions:
            # Mark as terminated and clear worker assignment
            await db.execute(
                update(CameraSession)
                .where(CameraSession.camera_id == session.camera_id)
                .values(
                    state=SessionState.TERMINATED,
                    worker_id=None,
                    reason=f"lease_expired_at_{session.lease_expires_at}",
                    updated_at=datetime.utcnow()
                )
            )
            
            # Update worker registry
            if session.worker_id:
                worker = worker_registry.get_worker(session.worker_id)
                if worker and worker.camera_id == session.camera_id:
                    worker.camera_id = None
                    worker.status = WorkerStatus.IDLE
            
            reclaimed_count += 1
            
            logger.info(
                "lease_reclaimed",
                camera_id=session.camera_id,
                worker_id=session.worker_id,
                expired_at=session.lease_expires_at.isoformat(),
                correlation_id=correlation_id
            )
        
        await db.commit()
        
        logger.info(
            "lease_reclaim_completed",
            reclaimed_count=reclaimed_count,
            correlation_id=correlation_id
        )
        
        return {"reclaimed_count": reclaimed_count}
    
    async def start(self):
        """Start background lease cleanup task"""
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("assignment_service_started")
    
    async def stop(self):
        """Stop background tasks"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("assignment_service_stopped")
    
    async def _cleanup_loop(self):
        """Background loop to reclaim expired leases"""
        while True:
            try:
                # Use the database's async context manager directly
                from ..core.database import db
                async with db.get_session() as session:
                    await self.reclaim_expired_leases(session)
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "lease_cleanup_error",
                    error=str(e)
                )
                await asyncio.sleep(5)  # Short delay on error  # Short delay on error


# Global instance
assignment_service = AssignmentService()