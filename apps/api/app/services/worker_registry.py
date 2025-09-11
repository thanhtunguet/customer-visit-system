from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from common.enums.worker import WorkerStatus

logger = logging.getLogger(__name__)


class WorkerInfo:
    """In-memory worker information"""

    def __init__(
        self,
        worker_id: str,
        tenant_id: str,
        hostname: str,
        ip_address: str,
        worker_name: str,
        worker_version: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        site_id: Optional[int] = None,
        camera_id: Optional[int] = None,
    ):
        self.worker_id = worker_id
        self.tenant_id = tenant_id
        self.hostname = hostname
        self.ip_address = ip_address
        self.worker_name = worker_name
        self.worker_version = worker_version
        self.capabilities = capabilities or {}
        self.site_id = site_id
        self.camera_id = camera_id

        # Status tracking
        self.status = WorkerStatus.IDLE
        self.last_heartbeat = datetime.utcnow()
        self.registration_time = datetime.utcnow()
        self.last_error: Optional[str] = None
        self.error_count = 0
        self.total_faces_processed = 0

        # For heartbeat tracking
        self.faces_processed_since_heartbeat = 0

    @property
    def is_healthy(self) -> bool:
        """Check if worker is considered healthy"""
        if not self.status.is_active():
            return False

        # Worker unhealthy if no heartbeat for 2 minutes
        stale_threshold = datetime.utcnow() - timedelta(minutes=2)
        return self.last_heartbeat > stale_threshold

    @property
    def uptime_minutes(self) -> int:
        """Calculate worker uptime in minutes"""
        if self.status == WorkerStatus.OFFLINE or not self.is_healthy:
            return 0

        uptime = self.last_heartbeat - self.registration_time
        return int(uptime.total_seconds() / 60)

    def update_heartbeat(
        self,
        status: WorkerStatus,
        faces_processed_count: int = 0,
        error_message: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        current_camera_id: Optional[int] = None,
    ):
        """Update worker heartbeat information"""
        self.status = status
        self.last_heartbeat = datetime.utcnow()

        # Update faces processed
        if faces_processed_count > 0:
            self.total_faces_processed += faces_processed_count

        # Update capabilities if provided
        if capabilities:
            self.capabilities = capabilities

        # Handle camera assignment
        if status == WorkerStatus.PROCESSING and current_camera_id:
            self.camera_id = current_camera_id
        elif status == WorkerStatus.OFFLINE:
            self.camera_id = None

        # Handle errors
        if status == WorkerStatus.ERROR:
            self.error_count += 1
            self.last_error = error_message
        elif status.is_active():
            # Clear error when worker comes back online
            self.last_error = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert worker info to dictionary"""
        return {
            "worker_id": self.worker_id,
            "tenant_id": self.tenant_id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "worker_name": self.worker_name,
            "worker_version": self.worker_version,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "site_id": self.site_id,
            "camera_id": self.camera_id,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "last_error": self.last_error,
            "error_count": self.error_count,
            "total_faces_processed": self.total_faces_processed,
            "uptime_minutes": self.uptime_minutes,
            "registration_time": self.registration_time.isoformat(),
            "is_healthy": self.is_healthy,
        }


class WorkerRegistry:
    """In-memory worker registry with TTL cleanup"""

    def __init__(self):
        self.workers: Dict[str, WorkerInfo] = {}  # worker_id -> WorkerInfo
        self.worker_by_hostname: Dict[str, Dict[str, List[str]]] = (
            {}
        )  # tenant_id -> hostname -> List[worker_id]
        self.cleanup_task: Optional[asyncio.Task] = None
        self.cleanup_interval = 60  # seconds
        self.worker_ttl = 300  # 5 minutes TTL
        self.callbacks: List[callable] = []

    async def start(self):
        """Start the registry cleanup task"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Worker registry cleanup task started")

    async def stop(self):
        """Stop the registry cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
            logger.info("Worker registry cleanup task stopped")

    def add_status_callback(self, callback: callable):
        """Add callback for worker status changes"""
        self.callbacks.append(callback)

    async def _notify_callbacks(self, event_type: str, worker_info: WorkerInfo):
        """Notify all callbacks of worker status change"""
        for callback in self.callbacks:
            try:
                await callback(event_type, worker_info)
            except Exception as e:
                logger.error(f"Error calling worker status callback: {e}")

    async def register_worker(
        self,
        tenant_id: str,
        hostname: str,
        ip_address: str,
        worker_name: str,
        worker_version: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        site_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        db_session=None,
        preferred_worker_id: Optional[str] = None,
    ) -> WorkerInfo:
        """Register a new worker or update existing one"""

        # Check for existing workers on this hostname and update if matching worker ID
        if tenant_id in self.worker_by_hostname:
            if hostname in self.worker_by_hostname[tenant_id]:
                existing_worker_ids = self.worker_by_hostname[tenant_id][hostname]

                # If preferred worker ID is specified, check if it already exists
                if preferred_worker_id and preferred_worker_id in existing_worker_ids:
                    if preferred_worker_id in self.workers:
                        # Update existing worker with same ID
                        worker = self.workers[preferred_worker_id]
                        worker.ip_address = ip_address
                        worker.worker_name = worker_name
                        worker.worker_version = worker_version
                        worker.capabilities = capabilities or {}
                        worker.site_id = site_id
                        worker.camera_id = camera_id
                        worker.status = WorkerStatus.IDLE
                        worker.last_heartbeat = datetime.utcnow()
                        worker.registration_time = (
                            datetime.utcnow()
                        )  # Reset registration time

                        await self._notify_callbacks("worker_updated", worker)
                        logger.info(
                            f"Worker {worker.worker_id} ({hostname}) updated for tenant {tenant_id}"
                        )
                        return worker

                # If no preferred worker ID, update the first worker on this hostname (backward compatibility)
                elif not preferred_worker_id and existing_worker_ids:
                    first_worker_id = existing_worker_ids[0]
                    if first_worker_id in self.workers:
                        worker = self.workers[first_worker_id]
                        worker.ip_address = ip_address
                        worker.worker_name = worker_name
                        worker.worker_version = worker_version
                        worker.capabilities = capabilities or {}
                        worker.site_id = site_id
                        worker.camera_id = camera_id
                        worker.status = WorkerStatus.IDLE
                        worker.last_heartbeat = datetime.utcnow()
                        worker.registration_time = (
                            datetime.utcnow()
                        )  # Reset registration time

                        await self._notify_callbacks("worker_updated", worker)
                        logger.info(
                            f"Worker {worker.worker_id} ({hostname}) updated for tenant {tenant_id}"
                        )
                        return worker

                # Different worker ID requested - allow multiple workers per hostname
                if preferred_worker_id:
                    logger.info(
                        f"Allowing multiple workers per hostname: existing {existing_worker_ids}, new {preferred_worker_id}"
                    )

        # Create new worker with preferred ID if provided
        if preferred_worker_id:
            # Check if preferred ID is already in use
            if preferred_worker_id in self.workers:
                logger.warning(
                    f"Preferred worker ID {preferred_worker_id} already in use, updating existing worker"
                )
                existing_worker = self.workers[preferred_worker_id]
                # Update existing worker with new registration data
                existing_worker.hostname = hostname
                existing_worker.ip_address = ip_address
                existing_worker.worker_name = worker_name
                existing_worker.worker_version = worker_version
                existing_worker.capabilities = capabilities or {}
                existing_worker.site_id = site_id
                existing_worker.camera_id = camera_id
                existing_worker.status = WorkerStatus.IDLE
                existing_worker.last_heartbeat = datetime.utcnow()

                await self._notify_callbacks("worker_reconnected", existing_worker)
                logger.info(
                    f"Worker {preferred_worker_id} ({hostname}) reconnected for tenant {tenant_id}"
                )
                return existing_worker
            else:
                worker_id = preferred_worker_id
                logger.info(f"Using preferred worker ID: {worker_id}")
        else:
            worker_id = str(uuid.uuid4())

        worker = WorkerInfo(
            worker_id=worker_id,
            tenant_id=tenant_id,
            hostname=hostname,
            ip_address=ip_address,
            worker_name=worker_name,
            worker_version=worker_version,
            capabilities=capabilities,
            site_id=site_id,
            camera_id=camera_id,
        )

        # Register worker
        self.workers[worker_id] = worker

        # Index by hostname for faster lookup (support multiple workers per hostname)
        if tenant_id not in self.worker_by_hostname:
            self.worker_by_hostname[tenant_id] = {}
        if hostname not in self.worker_by_hostname[tenant_id]:
            self.worker_by_hostname[tenant_id][hostname] = []
        if worker_id not in self.worker_by_hostname[tenant_id][hostname]:
            self.worker_by_hostname[tenant_id][hostname].append(worker_id)

        # Auto-assign camera if worker has site_id and db_session is available
        if site_id and db_session:
            try:
                logger.info(
                    f"Attempting auto-assignment for worker {worker_id} in site {site_id}"
                )

                # Import here to avoid circular import
                from .camera_delegation_service import \
                    camera_delegation_service

                camera = await camera_delegation_service.assign_camera_to_worker(
                    db=db_session,
                    tenant_id=tenant_id,
                    worker_id=worker_id,
                    site_id=site_id,
                )

                if camera:
                    logger.info(
                        f"Auto-assigned camera {camera.camera_id} ({camera.name}) to new worker {worker_id}"
                    )
                else:
                    logger.info(
                        f"No available cameras in site {site_id} for new worker {worker_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to auto-assign camera to new worker {worker_id}: {e}"
                )
        else:
            logger.info(
                f"Skipping auto-assignment for worker {worker_id}: site_id={site_id}, db_session={db_session is not None}"
            )

        await self._notify_callbacks("worker_registered", worker)
        logger.info(
            f"Worker {worker_id} ({hostname}) registered for tenant {tenant_id}"
        )
        return worker

    async def update_worker_heartbeat(
        self,
        worker_id: str,
        status: WorkerStatus,
        faces_processed_count: int = 0,
        error_message: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        current_camera_id: Optional[int] = None,
        active_camera_streams: Optional[List[str]] = None,
        total_active_streams: Optional[int] = None,
        active_camera_processing: Optional[List[str]] = None,
        total_active_processing: Optional[int] = None,
    ) -> Optional[WorkerInfo]:
        """Update worker heartbeat"""

        worker = self.workers.get(worker_id)
        if not worker:
            logger.warning(f"Heartbeat for unknown worker: {worker_id}")
            return None

        old_status = worker.status
        old_streaming_info = (
            worker.capabilities.get("active_camera_streams", [])
            if worker.capabilities
            else []
        )
        old_processing_info = (
            worker.capabilities.get("active_camera_processing", [])
            if worker.capabilities
            else []
        )

        worker.update_heartbeat(
            status=status,
            faces_processed_count=faces_processed_count,
            error_message=error_message,
            capabilities=capabilities,
            current_camera_id=current_camera_id,
        )

        # Store streaming and processing status in capabilities for frontend access
        streaming_status_changed = False
        processing_status_changed = False

        if active_camera_streams is not None or total_active_streams is not None:
            streaming_info = {
                "active_camera_streams": active_camera_streams or [],
                "total_active_streams": total_active_streams or 0,
                "streaming_status_updated": datetime.utcnow().isoformat(),
            }

            # Check if streaming status changed
            new_streaming_info = streaming_info["active_camera_streams"]
            if set(old_streaming_info) != set(new_streaming_info):
                streaming_status_changed = True

            # Update capabilities with streaming info
            if not worker.capabilities:
                worker.capabilities = {}
            worker.capabilities.update(streaming_info)

            logger.debug(
                f"Updated streaming status for worker {worker_id}: {total_active_streams} active streams"
            )

        if active_camera_processing is not None or total_active_processing is not None:
            processing_info = {
                "active_camera_processing": active_camera_processing or [],
                "total_active_processing": total_active_processing or 0,
                "processing_status_updated": datetime.utcnow().isoformat(),
            }

            # Check if processing status changed
            new_processing_info = processing_info["active_camera_processing"]
            if set(old_processing_info) != set(new_processing_info):
                processing_status_changed = True

            # Update capabilities with processing info
            if not worker.capabilities:
                worker.capabilities = {}
            worker.capabilities.update(processing_info)

            logger.debug(
                f"Updated processing status for worker {worker_id}: {total_active_processing} active processing"
            )

        # Broadcast camera status changes if streaming or processing status changed
        if streaming_status_changed or processing_status_changed:
            # Use task manager with DB task handling to prevent backend lockup
            from ..core.task_manager import create_db_task

            create_db_task(
                self._broadcast_camera_status_changes(
                    worker, active_camera_streams or [], active_camera_processing or []
                ),
                name=f"camera_broadcast_{worker.worker_id}",
                timeout=10.0,  # 10 second timeout for database operations
            )

        # Notify callbacks if status changed or if it's an error
        if old_status != status or status == WorkerStatus.ERROR:
            await self._notify_callbacks("worker_status_changed", worker)

        logger.debug(f"Heartbeat updated for worker {worker_id}: {status}")
        return worker

    async def _broadcast_camera_status_changes(
        self,
        worker: WorkerInfo,
        active_camera_streams: List[str],
        active_camera_processing: List[str] = None,
    ):
        """Broadcast camera status changes to SSE clients"""
        try:
            # Add timeout to prevent hanging database operations
            return await asyncio.wait_for(
                self._do_broadcast_camera_status_changes(
                    worker, active_camera_streams, active_camera_processing
                ),
                timeout=5.0,  # 5 second timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Camera status broadcast timed out for worker {worker.worker_id}"
            )
        except Exception as e:
            logger.error(f"Failed to broadcast camera status changes: {e}")

    async def _do_broadcast_camera_status_changes(
        self,
        worker: WorkerInfo,
        active_camera_streams: List[str],
        active_camera_processing: List[str] = None,
    ):
        """Internal method to perform the actual broadcast"""
        try:
            from sqlalchemy import select

            from ..core.database import get_db_session
            from ..models.database import Camera
            from .camera_status_broadcaster import camera_status_broadcaster

            if active_camera_processing is None:
                active_camera_processing = []

            # Get all unique camera IDs from streaming and processing lists
            all_camera_ids = set(active_camera_streams + active_camera_processing)

            if not all_camera_ids:
                return

            # Get site_id and other info for these cameras from database
            async with get_db_session() as db_session:
                # Convert string IDs to integers
                camera_int_ids = []
                for camera_id_str in all_camera_ids:
                    try:
                        camera_int_ids.append(int(camera_id_str))
                    except ValueError:
                        logger.warning(
                            f"Invalid camera_id in worker capabilities: {camera_id_str}"
                        )
                        continue

                if not camera_int_ids:
                    return

                # Query cameras to get site_id for broadcasting
                result = await db_session.execute(
                    select(Camera.camera_id, Camera.site_id, Camera.tenant_id).where(
                        Camera.camera_id.in_(camera_int_ids)
                    )
                )
                cameras = result.fetchall()

                # Broadcast status for each camera
                for camera_row in cameras:
                    camera_id = camera_row.camera_id
                    site_id = str(camera_row.site_id)
                    camera_id_str = str(camera_id)

                    status_data = {
                        "camera_id": camera_id,
                        "stream_active": camera_id_str in active_camera_streams,
                        "processing_active": camera_id_str in active_camera_processing,
                        "worker_id": worker.worker_id,
                        "worker_status": worker.status.value,
                        "worker_healthy": worker.is_healthy,
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": "worker_heartbeat",
                    }

                    # Broadcast to SSE clients for this site
                    await camera_status_broadcaster.broadcast_camera_status_change(
                        site_id, camera_id, status_data
                    )

                    logger.debug(
                        f"Broadcasted camera status change for camera {camera_id} in site {site_id}"
                    )

        except Exception as e:
            logger.error(f"Failed to do broadcast camera status changes: {e}")

    def _handle_broadcast_task_result(self, task: asyncio.Task):
        """Handle results from broadcast tasks to prevent unhandled exceptions"""
        try:
            if task.exception():
                logger.error(
                    f"Broadcast task failed with exception: {task.exception()}"
                )
            else:
                logger.debug("Broadcast task completed successfully")
        except Exception as e:
            # Fallback error handling in case task.exception() itself fails
            logger.error(f"Error handling broadcast task result: {e}")

    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """Get worker by ID"""
        return self.workers.get(worker_id)

    def get_worker_by_hostname(
        self, tenant_id: str, hostname: str
    ) -> Optional[WorkerInfo]:
        """Get first worker by hostname (for backward compatibility)"""
        if tenant_id not in self.worker_by_hostname:
            return None

        worker_ids = self.worker_by_hostname[tenant_id].get(hostname, [])
        if worker_ids:
            return self.workers.get(worker_ids[0])  # Return first worker
        return None

    def get_workers_by_hostname(
        self, tenant_id: str, hostname: str
    ) -> List[WorkerInfo]:
        """Get all workers by hostname"""
        if tenant_id not in self.worker_by_hostname:
            return []

        worker_ids = self.worker_by_hostname[tenant_id].get(hostname, [])
        workers = []
        for worker_id in worker_ids:
            worker = self.workers.get(worker_id)
            if worker:
                workers.append(worker)
        return workers

    def list_workers(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[WorkerStatus] = None,
        site_id: Optional[int] = None,
        include_offline: bool = True,
    ) -> List[WorkerInfo]:
        """List workers with optional filters"""

        workers = list(self.workers.values())

        # Filter by tenant
        if tenant_id:
            workers = [w for w in workers if w.tenant_id == tenant_id]

        # Filter by status
        if status:
            workers = [w for w in workers if w.status == status]

        # Filter by site
        if site_id:
            workers = [w for w in workers if w.site_id == site_id]

        # Filter offline workers
        if not include_offline:
            workers = [
                w for w in workers if w.status != WorkerStatus.OFFLINE and w.is_healthy
            ]

        # Sort by last heartbeat (most recent first)
        workers.sort(key=lambda w: w.last_heartbeat, reverse=True)

        return workers

    async def remove_worker(self, worker_id: str) -> bool:
        """Remove worker from registry"""

        worker = self.workers.get(worker_id)
        if not worker:
            return False

        # Release camera if assigned
        if worker.camera_id:
            try:
                # Import here to avoid circular import
                from .camera_delegation_service import \
                    camera_delegation_service

                camera_id = camera_delegation_service.release_camera_from_worker(
                    worker_id
                )
                if camera_id:
                    logger.info(
                        f"Released camera {camera_id} from removed worker {worker_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to release camera from removed worker {worker_id}: {e}"
                )

        # Remove from hostname index
        if worker.tenant_id in self.worker_by_hostname:
            for hostname, worker_ids in self.worker_by_hostname[
                worker.tenant_id
            ].items():
                if worker_id in worker_ids:
                    worker_ids.remove(worker_id)

                    # Clean up empty hostname entries
                    if not worker_ids:
                        del self.worker_by_hostname[worker.tenant_id][hostname]
                    break

            # Clean up empty tenant entries
            if not self.worker_by_hostname[worker.tenant_id]:
                del self.worker_by_hostname[worker.tenant_id]

        # Remove from workers
        del self.workers[worker_id]

        await self._notify_callbacks("worker_removed", worker)
        logger.info(f"Worker {worker_id} ({worker.hostname}) removed from registry")
        return True

    async def cleanup_stale_workers(self, ttl_seconds: Optional[int] = None) -> int:
        """Remove stale workers that haven't sent heartbeat within TTL"""

        if ttl_seconds is None:
            ttl_seconds = self.worker_ttl

        threshold = datetime.utcnow() - timedelta(seconds=ttl_seconds)
        stale_workers = []

        for worker_id, worker in self.workers.items():
            if worker.last_heartbeat < threshold:
                stale_workers.append(worker_id)

        # Remove stale workers
        removed_count = 0
        for worker_id in stale_workers:
            if await self.remove_worker(worker_id):
                removed_count += 1

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} stale workers")

        return removed_count

    async def _cleanup_loop(self):
        """Background cleanup task"""

        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_stale_workers()
            except asyncio.CancelledError:
                logger.info("Worker registry cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in worker registry cleanup loop: {e}")

    def get_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get worker registry statistics"""

        workers = self.list_workers(tenant_id=tenant_id, include_offline=True)

        total_count = len(workers)
        online_count = sum(1 for w in workers if w.status.is_active() and w.is_healthy)
        offline_count = sum(
            1 for w in workers if w.status == WorkerStatus.OFFLINE or not w.is_healthy
        )
        error_count = sum(1 for w in workers if w.status == WorkerStatus.ERROR)
        processing_count = sum(
            1 for w in workers if w.status == WorkerStatus.PROCESSING
        )

        return {
            "total_count": total_count,
            "online_count": online_count,
            "offline_count": offline_count,
            "error_count": error_count,
            "processing_count": processing_count,
        }


# Global worker registry instance
worker_registry = WorkerRegistry()
