"""
Worker monitoring service for real-time status tracking and cleanup.
This service runs as a background task to monitor worker health and update status.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set

from sqlalchemy import and_

from ..models.database import Worker

logger = logging.getLogger(__name__)


def _log_db_connection_error(log: logging.Logger, e: Exception, context: str) -> None:
    """Log DB connection/DNS errors with a clear hint."""
    if "Name or service not known" in str(e) or "nodename nor servname" in str(e):
        log.warning(
            "Database host unreachable for %s (check DB_HOST / DATABASE_URL): %s",
            context,
            e,
        )
    else:
        log.error("Error during %s: %s", context, e)


class WorkerMonitorService:
    """Service to monitor worker health and automatically update status"""

    def __init__(self):
        self.monitor_task: asyncio.Task = None
        self.is_running = False
        self.check_interval = 30  # Check every 30 seconds
        self.stale_threshold_minutes = 2  # Workers stale after 2 minutes
        self.offline_threshold_minutes = 5  # Workers offline after 5 minutes

    async def start(self):
        """Start the worker monitoring service"""
        if self.monitor_task and not self.monitor_task.done():
            logger.warning("Worker monitor service is already running")
            return

        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Worker monitor service started")

    async def stop(self):
        """Stop the worker monitoring service"""
        self.is_running = False

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Worker monitor service stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self._check_worker_health()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info("Worker monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in worker monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def _check_worker_health(self):
        """Check health of all workers and update their status"""
        from ..core.database import db

        try:
            async with db.get_session() as db_session:
                # Get all workers that might need status updates
                current_time = datetime.utcnow()
                stale_threshold = current_time - timedelta(
                    minutes=self.stale_threshold_minutes
                )
                offline_threshold = current_time - timedelta(
                    minutes=self.offline_threshold_minutes
                )

                # Find workers that should be marked as stale or offline
                from sqlalchemy import select

                result = await db_session.execute(
                    select(Worker).where(
                        Worker.status.in_(["idle", "processing", "online"])
                    )
                )
                workers = result.scalars().all()

                updates_made = 0
                workers_by_tenant: Dict[str, Set[str]] = {}

                for worker in workers:
                    old_status = worker.status
                    new_status = None

                    # Determine new status based on last heartbeat
                    if not worker.last_heartbeat:
                        new_status = "offline"
                    elif worker.last_heartbeat < offline_threshold:
                        new_status = "offline"
                    elif worker.last_heartbeat < stale_threshold and worker.status in [
                        "idle",
                        "processing",
                    ]:
                        # Worker is stale but not fully offline yet
                        logger.warning(
                            f"Worker {worker.worker_id} ({worker.hostname}) is stale - last heartbeat: {worker.last_heartbeat}"
                        )
                        continue  # Don't change status yet, give it more time

                    if new_status and new_status != old_status:
                        # Update worker status
                        worker.status = new_status
                        worker.updated_at = current_time

                        # Release camera assignment if going offline
                        if new_status == "offline" and worker.camera_id:
                            logger.info(
                                f"Releasing camera {worker.camera_id} from offline worker {worker.worker_id}"
                            )
                            worker.camera_id = None

                        updates_made += 1

                        # Track tenants that need WebSocket updates
                        if worker.tenant_id not in workers_by_tenant:
                            workers_by_tenant[worker.tenant_id] = set()
                        workers_by_tenant[worker.tenant_id].add(worker.worker_id)

                        logger.info(
                            f"Worker {worker.worker_id} ({worker.hostname}) status changed: {old_status} -> {new_status}"
                        )

                if updates_made > 0:
                    await db_session.commit()
                    logger.info(f"Updated status for {updates_made} workers")

                    # Trigger WebSocket updates for affected tenants
                    await self._broadcast_worker_updates(workers_by_tenant, db_session)

        except OSError as e:
            _log_db_connection_error(logger, e, "worker health")
        except Exception as e:
            if "Name or service not known" in str(e) or "nodename nor servname" in str(e):
                _log_db_connection_error(logger, e, "worker health")
            else:
                logger.error("Error checking worker health: %s", e)

    async def _broadcast_worker_updates(
        self, workers_by_tenant: Dict[str, Set[str]], db_session
    ):
        """Broadcast worker status updates via WebSocket"""
        try:
            # Import here to avoid circular imports
            import json

            from ..routers.workers import (calculate_uptime_minutes,
                                           connection_manager,
                                           is_worker_healthy)

            for tenant_id, worker_ids in workers_by_tenant.items():
                # Get updated worker data
                from sqlalchemy import select

                result = await db_session.execute(
                    select(Worker).where(
                        and_(
                            Worker.tenant_id == tenant_id,
                            Worker.worker_id.in_(worker_ids),
                        )
                    )
                )
                workers = result.scalars().all()

                for worker in workers:
                    # Parse capabilities
                    capabilities = None
                    if worker.capabilities:
                        try:
                            capabilities = json.loads(worker.capabilities)
                        except json.JSONDecodeError:
                            capabilities = None

                    worker_data = {
                        "worker_id": worker.worker_id,
                        "tenant_id": worker.tenant_id,
                        "hostname": worker.hostname,
                        "ip_address": worker.ip_address,
                        "worker_name": worker.worker_name,
                        "worker_version": worker.worker_version,
                        "capabilities": capabilities,
                        "status": worker.status,
                        "site_id": worker.site_id,
                        "camera_id": worker.camera_id,
                        "last_heartbeat": (
                            worker.last_heartbeat.isoformat()
                            if worker.last_heartbeat
                            else None
                        ),
                        "last_error": worker.last_error,
                        "error_count": worker.error_count,
                        "total_faces_processed": worker.total_faces_processed,
                        "uptime_minutes": calculate_uptime_minutes(worker),
                        "registration_time": (
                            worker.registration_time.isoformat()
                            if worker.registration_time
                            else None
                        ),
                        "is_healthy": is_worker_healthy(worker),
                    }

                    # Broadcast update
                    await connection_manager.broadcast_worker_update(
                        tenant_id, worker_data
                    )

        except Exception as e:
            logger.error(f"Error broadcasting worker updates: {e}")

    async def cleanup_stale_workers(self, minutes_threshold: int = 10):
        """Manually cleanup workers that haven't sent heartbeat for specified minutes"""
        from ..core.database import db

        async with db.get_session() as db_session:
            try:
                threshold_time = datetime.utcnow() - timedelta(
                    minutes=minutes_threshold
                )

                updated_count = 0
                from sqlalchemy import and_, select

                result = await db_session.execute(
                    select(Worker).where(
                        and_(
                            Worker.status.in_(["idle", "processing", "online"]),
                            Worker.last_heartbeat < threshold_time,
                        )
                    )
                )
                workers = result.scalars().all()

                for worker in workers:
                    worker.status = "offline"
                    worker.camera_id = None  # Release camera
                    worker.updated_at = datetime.utcnow()
                    updated_count += 1
                    logger.info(
                        f"Cleaned up stale worker: {worker.worker_id} ({worker.hostname})"
                    )

                if updated_count > 0:
                    await db_session.commit()
                    logger.info(f"Cleaned up {updated_count} stale workers")

                return updated_count

            except Exception as e:
                logger.error(f"Error cleaning up stale workers: {e}")
                await db_session.rollback()
                return 0


# Global instance
worker_monitor_service = WorkerMonitorService()
