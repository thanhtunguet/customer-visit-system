from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..enums import WorkerStatus
from ..models.database import Camera, Worker
from .worker_registry import worker_registry, WorkerInfo

logger = logging.getLogger(__name__)


class CameraDelegationService:
    """Service for managing camera assignments to workers"""
    
    def __init__(self):
        self.assignments: Dict[int, str] = {}  # camera_id -> worker_id
        self.worker_cameras: Dict[str, int] = {}  # worker_id -> camera_id
        
    def assign_camera_to_worker(self, db: Session, tenant_id: str, worker_id: str, site_id: int) -> Optional[Camera]:
        """
        Assign an available camera to a worker in the registry system.
        Only one camera per worker, and one worker per camera.
        """
        
        # Get worker info from registry
        worker = worker_registry.get_worker(worker_id)
        if not worker:
            logger.warning(f"Worker {worker_id} not found in registry")
            return None
        
        # Ensure worker belongs to the right tenant
        if worker.tenant_id != tenant_id:
            logger.warning(f"Worker {worker_id} belongs to different tenant")
            return None
        
        # Check if worker already has a camera assigned
        if worker_id in self.worker_cameras:
            current_camera_id = self.worker_cameras[worker_id]
            logger.info(f"Worker {worker_id} already has camera {current_camera_id} assigned")
            # Return the currently assigned camera
            return db.query(Camera).filter(
                and_(
                    Camera.tenant_id == tenant_id,
                    Camera.camera_id == current_camera_id,
                    Camera.is_active == True
                )
            ).first()
        
        # Find available cameras in the site
        available_cameras = db.query(Camera).filter(
            and_(
                Camera.tenant_id == tenant_id,
                Camera.site_id == site_id,
                Camera.is_active == True
            )
        ).all()
        
        if not available_cameras:
            logger.info(f"No cameras available in site {site_id} for tenant {tenant_id}")
            return None
        
        # Find cameras that are not assigned to any worker
        for camera in available_cameras:
            if camera.camera_id not in self.assignments:
                # Assign camera to worker
                self.assignments[camera.camera_id] = worker_id
                self.worker_cameras[worker_id] = camera.camera_id
                
                # Update worker info in registry
                worker.camera_id = camera.camera_id
                
                logger.info(f"Assigned camera {camera.camera_id} to worker {worker_id}")
                return camera
        
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
        """Clean up assignments for workers that are no longer active"""
        cleanup_count = 0
        stale_workers = []
        
        for worker_id in list(self.worker_cameras.keys()):
            worker = worker_registry.get_worker(worker_id)
            if not worker or not worker.is_healthy or worker.status == WorkerStatus.OFFLINE:
                stale_workers.append(worker_id)
        
        for worker_id in stale_workers:
            camera_id = self.release_camera_from_worker(worker_id)
            if camera_id:
                cleanup_count += 1
                logger.info(f"Cleaned up stale assignment: camera {camera_id} from worker {worker_id}")
        
        return cleanup_count
    
    def reassign_cameras_automatically(self, db: Session, tenant_id: str) -> int:
        """Automatically assign cameras to idle workers that don't have assignments"""
        assignments_made = 0
        
        # Get all idle workers without camera assignments
        idle_workers = worker_registry.list_workers(tenant_id=tenant_id, status=WorkerStatus.IDLE)
        unassigned_workers = [w for w in idle_workers if w.worker_id not in self.worker_cameras and w.site_id]
        
        for worker in unassigned_workers:
            camera = self.assign_camera_to_worker(db, tenant_id, worker.worker_id, worker.site_id)
            if camera:
                assignments_made += 1
                logger.info(f"Auto-assigned camera {camera.camera_id} to idle worker {worker.worker_id}")
        
        return assignments_made


# Global camera delegation service
camera_delegation_service = CameraDelegationService()