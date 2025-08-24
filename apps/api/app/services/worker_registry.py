from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any
import logging

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
        old_status = self.status
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
        self.worker_by_hostname: Dict[str, Dict[str, str]] = {}  # tenant_id -> hostname -> worker_id
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
    ) -> WorkerInfo:
        """Register a new worker or update existing one"""
        
        # Check if worker with same hostname exists for this tenant
        if tenant_id in self.worker_by_hostname:
            if hostname in self.worker_by_hostname[tenant_id]:
                existing_worker_id = self.worker_by_hostname[tenant_id][hostname]
                if existing_worker_id in self.workers:
                    # Update existing worker
                    worker = self.workers[existing_worker_id]
                    worker.ip_address = ip_address
                    worker.worker_name = worker_name
                    worker.worker_version = worker_version
                    worker.capabilities = capabilities or {}
                    worker.site_id = site_id
                    worker.camera_id = camera_id
                    worker.status = WorkerStatus.IDLE
                    worker.last_heartbeat = datetime.utcnow()
                    worker.registration_time = datetime.utcnow()  # Reset registration time
                    
                    await self._notify_callbacks("worker_updated", worker)
                    logger.info(f"Worker {worker.worker_id} ({hostname}) updated for tenant {tenant_id}")
                    return worker
        
        # Create new worker
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
        
        # Index by hostname for faster lookup
        if tenant_id not in self.worker_by_hostname:
            self.worker_by_hostname[tenant_id] = {}
        self.worker_by_hostname[tenant_id][hostname] = worker_id
        
        # Auto-assign camera if worker has site_id and db_session is available
        if site_id and db_session:
            try:
                logger.info(f"Attempting auto-assignment for worker {worker_id} in site {site_id}")
                
                # Import here to avoid circular import
                from .camera_delegation_service import camera_delegation_service
                
                camera = camera_delegation_service.assign_camera_to_worker(
                    db=db_session,
                    tenant_id=tenant_id,
                    worker_id=worker_id,
                    site_id=site_id
                )
                
                if camera:
                    logger.info(f"Auto-assigned camera {camera.camera_id} ({camera.name}) to new worker {worker_id}")
                else:
                    logger.info(f"No available cameras in site {site_id} for new worker {worker_id}")
            except Exception as e:
                logger.error(f"Failed to auto-assign camera to new worker {worker_id}: {e}")
        else:
            logger.info(f"Skipping auto-assignment for worker {worker_id}: site_id={site_id}, db_session={db_session is not None}")
        
        await self._notify_callbacks("worker_registered", worker)
        logger.info(f"Worker {worker_id} ({hostname}) registered for tenant {tenant_id}")
        return worker
    
    async def update_worker_heartbeat(
        self,
        worker_id: str,
        status: WorkerStatus,
        faces_processed_count: int = 0,
        error_message: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        current_camera_id: Optional[int] = None,
    ) -> Optional[WorkerInfo]:
        """Update worker heartbeat"""
        
        worker = self.workers.get(worker_id)
        if not worker:
            logger.warning(f"Heartbeat for unknown worker: {worker_id}")
            return None
        
        old_status = worker.status
        worker.update_heartbeat(
            status=status,
            faces_processed_count=faces_processed_count,
            error_message=error_message,
            capabilities=capabilities,
            current_camera_id=current_camera_id,
        )
        
        # Notify callbacks if status changed or if it's an error
        if old_status != status or status == WorkerStatus.ERROR:
            await self._notify_callbacks("worker_status_changed", worker)
        
        logger.debug(f"Heartbeat updated for worker {worker_id}: {status}")
        return worker
    
    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """Get worker by ID"""
        return self.workers.get(worker_id)
    
    def get_worker_by_hostname(self, tenant_id: str, hostname: str) -> Optional[WorkerInfo]:
        """Get worker by hostname"""
        if tenant_id not in self.worker_by_hostname:
            return None
        
        worker_id = self.worker_by_hostname[tenant_id].get(hostname)
        if worker_id:
            return self.workers.get(worker_id)
        return None
    
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
            workers = [w for w in workers if w.status != WorkerStatus.OFFLINE and w.is_healthy]
        
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
                from .camera_delegation_service import camera_delegation_service
                
                camera_id = camera_delegation_service.release_camera_from_worker(worker_id)
                if camera_id:
                    logger.info(f"Released camera {camera_id} from removed worker {worker_id}")
            except Exception as e:
                logger.error(f"Failed to release camera from removed worker {worker_id}: {e}")
        
        # Remove from hostname index
        if worker.tenant_id in self.worker_by_hostname:
            hostname_to_remove = None
            for hostname, wid in self.worker_by_hostname[worker.tenant_id].items():
                if wid == worker_id:
                    hostname_to_remove = hostname
                    break
            
            if hostname_to_remove:
                del self.worker_by_hostname[worker.tenant_id][hostname_to_remove]
                
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
        offline_count = sum(1 for w in workers if w.status == WorkerStatus.OFFLINE or not w.is_healthy)
        error_count = sum(1 for w in workers if w.status == WorkerStatus.ERROR)
        processing_count = sum(1 for w in workers if w.status == WorkerStatus.PROCESSING)
        
        return {
            "total_count": total_count,
            "online_count": online_count,
            "offline_count": offline_count,
            "error_count": error_count,
            "processing_count": processing_count,
        }


# Global worker registry instance
worker_registry = WorkerRegistry()