from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from common.enums.worker import WorkerStatus
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import Camera
from .worker_registry import worker_registry

logger = logging.getLogger(__name__)


class CameraDelegationService:
    """Service for managing camera assignments to workers"""

    def __init__(self):
        self.assignments: Dict[int, str] = {}  # camera_id -> worker_id
        self.worker_cameras: Dict[str, int] = {}  # worker_id -> camera_id
        self.cleanup_task: Optional[asyncio.Task] = None
        self.auto_assign_task: Optional[asyncio.Task] = None
        self.cleanup_interval = 60  # seconds - check every minute
        self.auto_assign_interval = (
            30  # seconds - check for auto-assignments every 30 seconds
        )

    async def assign_camera_to_worker(
        self, db: AsyncSession, tenant_id: str, worker_id: str, site_id: int
    ) -> Optional[Camera]:
        """
        Assign an available camera to a worker in the registry system.
        Only one camera per worker, and one worker per camera.
        """
        # Import structured logging
        from ..core.correlation import (
            get_or_create_correlation_id,
            get_structured_logger,
        )

        struct_logger = get_structured_logger(__name__)
        correlation_id = get_or_create_correlation_id()

        struct_logger.info(
            "assignment_start",
            worker_id=worker_id,
            tenant_id=tenant_id,
            site_id=site_id,
            correlation_id=correlation_id,
        )

        # Get worker info from registry
        worker = worker_registry.get_worker(worker_id)
        if not worker:
            struct_logger.warning(
                "assignment_failed_worker_not_found",
                worker_id=worker_id,
                reason="worker_not_in_registry",
                correlation_id=correlation_id,
            )
            logger.warning(f"Worker {worker_id} not found in registry")
            return None

        struct_logger.info(
            "worker_found",
            worker_id=worker_id,
            worker_status=worker.status.value,
            worker_tenant=worker.tenant_id,
            worker_site=worker.site_id,
            correlation_id=correlation_id,
        )

        # Ensure worker belongs to the right tenant
        if worker.tenant_id != tenant_id:
            struct_logger.warning(
                "assignment_failed_tenant_mismatch",
                worker_id=worker_id,
                worker_tenant=worker.tenant_id,
                expected_tenant=tenant_id,
                reason="tenant_mismatch",
                correlation_id=correlation_id,
            )
            logger.warning(f"Worker {worker_id} belongs to different tenant")
            return None

        # Check if worker already has a camera assigned
        if worker_id in self.worker_cameras:
            current_camera_id = self.worker_cameras[worker_id]
            struct_logger.info(
                "assignment_already_exists",
                worker_id=worker_id,
                camera_id=current_camera_id,
                reason="worker_already_assigned",
                correlation_id=correlation_id,
            )
            logger.info(
                f"Worker {worker_id} already has camera {current_camera_id} assigned"
            )
            # Return the currently assigned camera
            result = await db.execute(
                select(Camera).where(
                    and_(
                        Camera.tenant_id == tenant_id,
                        Camera.camera_id == current_camera_id,
                        Camera.is_active,
                    )
                )
            )
            return result.scalar_one_or_none()

        # Find available cameras in the site
        result = await db.execute(
            select(Camera).where(
                and_(
                    Camera.tenant_id == tenant_id,
                    Camera.site_id == site_id,
                    Camera.is_active,
                )
            )
        )
        available_cameras = result.scalars().all()

        struct_logger.info(
            "cameras_query_result",
            tenant_id=tenant_id,
            site_id=site_id,
            total_cameras=len(available_cameras),
            correlation_id=correlation_id,
        )

        logger.info(
            f"Found {len(available_cameras)} cameras in site {site_id} for tenant {tenant_id}"
        )
        for cam in available_cameras:
            is_assigned = cam.camera_id in self.assignments
            assigned_worker = self.assignments.get(cam.camera_id)
            struct_logger.info(
                "camera_status",
                camera_id=cam.camera_id,
                camera_name=cam.name,
                is_assigned=is_assigned,
                assigned_worker=assigned_worker,
                correlation_id=correlation_id,
            )
            logger.info(
                f"  Camera {cam.camera_id}: {cam.name} (assigned: {is_assigned})"
            )

        if not available_cameras:
            struct_logger.warning(
                "assignment_failed_no_cameras",
                tenant_id=tenant_id,
                site_id=site_id,
                reason="no_cameras_in_site",
                correlation_id=correlation_id,
            )
            logger.info(
                f"No cameras available in site {site_id} for tenant {tenant_id}"
            )
            return None

        # Find cameras that are not assigned to any worker
        for camera in available_cameras:
            if camera.camera_id not in self.assignments:
                # Assign camera to worker
                self.assignments[camera.camera_id] = worker_id
                self.worker_cameras[worker_id] = camera.camera_id

                # Update worker info in registry
                worker.camera_id = camera.camera_id

                struct_logger.info(
                    "assignment_successful",
                    worker_id=worker_id,
                    camera_id=camera.camera_id,
                    camera_name=camera.name,
                    camera_type=(
                        camera.camera_type.value if camera.camera_type else "webcam"
                    ),
                    correlation_id=correlation_id,
                )

                # Send ASSIGN_CAMERA command to worker to start processing
                try:
                    from common.enums.commands import CommandPriority, WorkerCommand

                    from .worker_command_service import worker_command_service

                    command_id = worker_command_service.send_command(
                        worker_id=worker_id,
                        command=WorkerCommand.ASSIGN_CAMERA,
                        parameters={
                            "camera_id": camera.camera_id,
                            "camera_name": camera.name,
                            "rtsp_url": camera.rtsp_url,
                            "device_index": camera.device_index,
                            "camera_type": (
                                camera.camera_type.value
                                if camera.camera_type
                                else "webcam"
                            ),
                            "correlation_id": correlation_id,
                        },
                        priority=CommandPriority.HIGH,
                        requested_by="system_auto_assignment",
                    )

                    struct_logger.info(
                        "command_sent",
                        command_id=command_id,
                        worker_id=worker_id,
                        camera_id=camera.camera_id,
                        command="ASSIGN_CAMERA",
                        correlation_id=correlation_id,
                    )
                    logger.info(
                        f"Sent ASSIGN_CAMERA command {command_id} to worker {worker_id} for camera {camera.camera_id}"
                    )

                    # Broadcast camera status change for immediate frontend update
                    try:
                        from datetime import datetime

                        from .camera_status_broadcaster import camera_status_broadcaster

                        status_data = {
                            "camera_id": camera.camera_id,
                            "stream_active": False,  # Will be updated when worker actually starts
                            "worker_id": worker_id,
                            "worker_status": "assigned",
                            "timestamp": datetime.utcnow().isoformat(),
                            "source": "camera_assignment",
                            "correlation_id": correlation_id,
                        }
                        from ..core.task_manager import create_broadcast_task

                        create_broadcast_task(
                            camera_status_broadcaster.broadcast_camera_status_change(
                                str(camera.site_id), camera.camera_id, status_data
                            ),
                            name=f"camera_status_{camera.camera_id}",
                        )

                        struct_logger.info(
                            "status_broadcast_queued",
                            camera_id=camera.camera_id,
                            worker_id=worker_id,
                            correlation_id=correlation_id,
                        )
                    except Exception as broadcast_error:
                        struct_logger.error(
                            "status_broadcast_failed",
                            camera_id=camera.camera_id,
                            error=str(broadcast_error),
                            correlation_id=correlation_id,
                        )
                        logger.warning(
                            f"Failed to broadcast camera assignment status: {broadcast_error}"
                        )

                except Exception as e:
                    struct_logger.error(
                        "command_send_failed",
                        worker_id=worker_id,
                        camera_id=camera.camera_id,
                        error=str(e),
                        correlation_id=correlation_id,
                    )
                    logger.error(
                        f"Failed to send ASSIGN_CAMERA command to worker {worker_id}: {e}"
                    )

                logger.info(f"Assigned camera {camera.camera_id} to worker {worker_id}")
                return camera

        struct_logger.warning(
            "assignment_failed_all_assigned",
            tenant_id=tenant_id,
            site_id=site_id,
            total_cameras=len(available_cameras),
            reason="all_cameras_assigned",
            correlation_id=correlation_id,
        )
        logger.info(f"All cameras in site {site_id} are already assigned")
        return None

    def release_camera_from_worker(self, worker_id: str) -> Optional[int]:
        """Release camera assignment from a worker"""

        if worker_id not in self.worker_cameras:
            return None

        camera_id = self.worker_cameras[worker_id]

        # Remove assignments
        del self.worker_cameras[worker_id]
        del self.assignments[camera_id]

        # Update worker info in registry
        worker = worker_registry.get_worker(worker_id)
        if worker:
            worker.camera_id = None

        logger.info(f"Released camera {camera_id} from worker {worker_id}")
        return camera_id

    def get_worker_camera(self, worker_id: str) -> Optional[int]:
        """Get camera assigned to a worker"""
        return self.worker_cameras.get(worker_id)

    def get_camera_worker(self, camera_id: int) -> Optional[str]:
        """Get worker assigned to a camera"""
        return self.assignments.get(camera_id)

    def list_assignments(self, tenant_id: Optional[str] = None) -> Dict[str, Dict]:
        """List all current camera-worker assignments"""
        result = {}

        for camera_id, worker_id in self.assignments.items():
            worker = worker_registry.get_worker(worker_id)
            if worker and (tenant_id is None or worker.tenant_id == tenant_id):
                result[str(camera_id)] = {
                    "camera_id": camera_id,
                    "worker_id": worker_id,
                    "worker_name": worker.worker_name,
                    "worker_status": worker.status.value,
                    "is_healthy": worker.is_healthy,
                    "site_id": worker.site_id,
                    "assigned_at": worker.last_heartbeat.isoformat(),
                }

        return result

    def cleanup_stale_assignments(self) -> int:
        """Clean up assignments for workers that are no longer active or healthy (5-minute timeout)"""
        cleanup_count = 0
        stale_workers = []

        # Use 5-minute timeout for camera assignments specifically
        timeout_threshold = datetime.now() - timedelta(minutes=5)

        for worker_id in list(self.worker_cameras.keys()):
            worker = worker_registry.get_worker(worker_id)
            if not worker:
                # Worker no longer exists
                stale_workers.append(worker_id)
            elif worker.status == WorkerStatus.OFFLINE:
                # Worker explicitly offline
                stale_workers.append(worker_id)
            elif worker.last_heartbeat < timeout_threshold:
                # Worker hasn't sent heartbeat in 5 minutes
                stale_workers.append(worker_id)
                logger.info(
                    f"Worker {worker_id} last heartbeat: {worker.last_heartbeat}, threshold: {timeout_threshold}"
                )

        for worker_id in stale_workers:
            camera_id = self.release_camera_from_worker(worker_id)
            if camera_id:
                cleanup_count += 1
                logger.info(
                    f"Cleaned up stale assignment: camera {camera_id} from worker {worker_id}"
                )

        return cleanup_count

    async def reassign_cameras_automatically(
        self, db: AsyncSession, tenant_id: str
    ) -> int:
        """Automatically assign cameras to idle workers that don't have assignments"""
        assignments_made = 0

        # Get all idle workers without camera assignments
        idle_workers = worker_registry.list_workers(
            tenant_id=tenant_id, status=WorkerStatus.IDLE
        )
        unassigned_workers = [
            w
            for w in idle_workers
            if w.worker_id not in self.worker_cameras and w.site_id
        ]

        for worker in unassigned_workers:
            camera = await self.assign_camera_to_worker(
                db, tenant_id, worker.worker_id, worker.site_id
            )
            if camera:
                assignments_made += 1
                logger.info(
                    f"Auto-assigned camera {camera.camera_id} to idle worker {worker.worker_id}"
                )

        return assignments_made

    async def start(self):
        """Start the camera assignment cleanup and auto-assignment tasks"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Camera delegation cleanup task started")

        if self.auto_assign_task is None:
            self.auto_assign_task = asyncio.create_task(self._auto_assign_loop())
            logger.info("Camera delegation auto-assignment task started")

    async def stop(self):
        """Stop the camera assignment cleanup and auto-assignment tasks"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
            logger.info("Camera delegation cleanup task stopped")

        if self.auto_assign_task:
            self.auto_assign_task.cancel()
            try:
                await self.auto_assign_task
            except asyncio.CancelledError:
                pass
            self.auto_assign_task = None
            logger.info("Camera delegation auto-assignment task stopped")

    async def _cleanup_loop(self):
        """Background cleanup task for stale camera assignments"""

        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                cleanup_count = self.cleanup_stale_assignments()
                if cleanup_count > 0:
                    logger.info(
                        f"Automatic cleanup: released {cleanup_count} stale camera assignments"
                    )
            except asyncio.CancelledError:
                logger.info("Camera delegation cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in camera delegation cleanup loop: {e}")

    async def _auto_assign_loop(self):
        """Background auto-assignment task for available workers"""

        while True:
            try:
                await asyncio.sleep(self.auto_assign_interval)

                # Get database session
                from ..core.database import db

                async with db.get_session() as db_session:
                    # Get all unique tenant IDs from active workers
                    active_tenants = set()
                    for worker in worker_registry.workers.values():
                        if (
                            worker.status in [WorkerStatus.IDLE, WorkerStatus.ONLINE]
                            and worker.is_healthy
                        ):
                            active_tenants.add(worker.tenant_id)

                    total_assigned = 0
                    for tenant_id in active_tenants:
                        try:
                            assigned_count = await self.reassign_cameras_automatically(
                                db_session, tenant_id
                            )
                            total_assigned += assigned_count
                            if assigned_count > 0:
                                logger.info(
                                    f"Auto-assigned {assigned_count} cameras for tenant {tenant_id}"
                                )
                        except Exception as e:
                            logger.error(
                                f"Error in auto-assignment for tenant {tenant_id}: {e}"
                            )

                    if total_assigned > 0:
                        logger.info(
                            f"Background auto-assignment: assigned {total_assigned} cameras total"
                        )

            except asyncio.CancelledError:
                logger.info("Camera delegation auto-assignment loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in camera delegation auto-assignment loop: {e}")


# Global camera delegation service
camera_delegation_service = CameraDelegationService()
